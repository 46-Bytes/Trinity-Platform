"""
The in-process Drive sync scheduler.

Deliberately no Celery, no broker and no scheduler process: one asyncio task
started with the API. The things worth testing are the ones that make that
safe rather than reckless - that a pass cannot run on the event loop, that
two API instances cannot sync at once, and that the loop survives anything
thrown at it, because a loop that dies stops syncing silently and for good.
"""
import asyncio
import threading

import pytest
from sqlalchemy import text

from app.database import engine
from app.models.user import UserRole
from app.services import drive_scheduler
from app.services.drive_client import DriveRateLimited, DriveUnavailable

_NEEDS_MIGRATION = (
    "Drive data room schema is missing. Migrate first:\n"
    "    cd backend && alembic upgrade head"
)


@pytest.fixture(autouse=True)
def drive_schema(db_session):
    try:
        db_session.execute(text("SELECT 1 FROM drive_integration LIMIT 0"))
    except Exception:
        pytest.skip(_NEEDS_MIGRATION, allow_module_level=True)


@pytest.fixture(autouse=True)
def fast_scheduler(monkeypatch):
    """Milliseconds, not minutes. Without this every test waits 30 seconds."""
    monkeypatch.setattr(drive_scheduler, "INITIAL_DELAY_SECONDS", 0)
    monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_SYNC_ENABLED", True)


@pytest.fixture(autouse=True)
def _no_task_left_running():
    """
    A leaked task would run against a torn-down database.

    Each test stops its own loop inside its own asyncio.run block; by the
    time this runs the loop is closed, so the module global is simply
    cleared rather than awaited.
    """
    yield
    drive_scheduler._task = None


def _run(coro_fn):
    """
    Drive one coroutine to completion on a private event loop.

    pytest-asyncio is not installed, and 24 async tests elsewhere in this
    suite are silently skipped because of it. Rather than add a dependency
    for this file alone, the loop is driven by hand.
    """
    return asyncio.run(coro_fn())


# ======================================================================
# Exclusion between instances
# ======================================================================
class TestAdvisoryLock:
    """
    Several API instances all run the loop; exactly one may sync per tick.

    A Postgres advisory lock rather than Redis, because Postgres is the one
    piece of infrastructure that exists in every environment - Redis is not
    provisioned in production on any merged branch.
    """

    def test_a_second_runner_is_refused_while_the_first_holds_the_lock(self, monkeypatch):
        started = threading.Event()
        release = threading.Event()
        outcomes = {}

        def slow_sync():
            started.set()
            release.wait(timeout=5)
            return {"added": 1}

        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr(drive_scheduler, "SessionLocal", _FakeSessionFactory(slow_sync))

        first = threading.Thread(target=lambda: outcomes.__setitem__("first", drive_scheduler.run_one_pass()))
        first.start()
        assert started.wait(timeout=5), "the first pass never started"

        # While the first holds the lock, a second must decline rather than
        # queue or double-apply.
        outcomes["second"] = drive_scheduler.run_one_pass()
        release.set()
        first.join(timeout=5)

        assert outcomes["second"] is None
        assert outcomes["first"] == {"added": 1}

    def test_the_lock_is_released_after_a_pass(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr(drive_scheduler, "SessionLocal", _FakeSessionFactory(lambda: {"added": 0}))

        drive_scheduler.run_one_pass()
        # A transaction-scoped lock is gone the moment the transaction ends,
        # so a fresh connection can take it. The session-scoped variant would
        # have leaked onto the pooled connection instead.
        with engine.connect() as c:
            got = c.execute(
                text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": drive_scheduler.ADVISORY_LOCK_KEY},
            ).scalar()
            assert got is True

    def test_the_lock_is_released_when_a_pass_raises(self, monkeypatch):
        def boom():
            raise RuntimeError("kaboom")

        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr(drive_scheduler, "SessionLocal", _FakeSessionFactory(boom))

        with pytest.raises(RuntimeError):
            drive_scheduler.run_one_pass()
        with engine.connect() as c:
            assert c.execute(
                text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": drive_scheduler.ADVISORY_LOCK_KEY},
            ).scalar() is True


# ======================================================================
# The pass never blocks the API
# ======================================================================
class TestPassRunsOffTheEventLoop:
    def test_the_pass_runs_in_a_worker_thread(self, monkeypatch):
        """
        sync() is blocking. Run on the event loop it would freeze every
        request for the length of a Drive round trip.
        """
        loop_thread = threading.get_ident()
        seen = {}

        monkeypatch.setattr(drive_scheduler, "run_one_pass",
                            lambda: seen.setdefault("thread", threading.get_ident()))
        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)

        async def scenario():
            drive_scheduler.start()
            await asyncio.sleep(0.15)
            await drive_scheduler.stop()

        _run(scenario)

        assert "thread" in seen, "the pass never ran"
        assert seen["thread"] != loop_thread, "the pass ran on the event loop"


# ======================================================================
# The loop outlives failures
# ======================================================================
class TestLoopResilience:
    def test_an_exception_does_not_end_the_loop(self, monkeypatch):
        """A loop that dies stops syncing for the life of the process."""
        calls = {"n": 0}
        state = {}

        def sometimes_explodes():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first pass fails")
            return {"added": 0}

        monkeypatch.setattr(drive_scheduler, "run_one_pass", sometimes_explodes)
        monkeypatch.setattr(drive_scheduler, "MAX_BACKOFF_SECONDS", 0.01)

        async def scenario():
            drive_scheduler.start()
            await asyncio.sleep(0.3)
            state["running"] = drive_scheduler.is_running()
            await drive_scheduler.stop()

        _run(scenario)

        assert calls["n"] >= 2, "the loop stopped after the first failure"
        assert state["running"] is True

    def test_the_loop_waits_longer_after_each_consecutive_failure(self, monkeypatch):
        """
        A broken Drive must not be hammered at full rate for hours.

        Asserted against the arithmetic rather than by running the scheduler
        and watching the clock. The previous version raced a real threadpool:
        it started the loop, yielded to the event loop a fixed number of
        times, and assumed enough passes had completed. Under a loaded suite
        they had not, and it failed intermittently.
        """
        monkeypatch.setattr(drive_scheduler.settings,
                            "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 300)
        monkeypatch.setattr(drive_scheduler, "MAX_BACKOFF_SECONDS", 100_000)

        delays = [drive_scheduler._backoff_delay(n) for n in range(1, 5)]
        assert delays == [600, 1200, 2400, 4800], delays
        assert all(b > a for a, b in zip(delays, delays[1:]))

    def test_a_healthy_pass_waits_the_normal_interval(self, monkeypatch):
        """Zero failures means no backoff at all."""
        monkeypatch.setattr(drive_scheduler.settings,
                            "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 300)
        assert drive_scheduler._backoff_delay(0) == 300

    def test_backoff_is_capped(self, monkeypatch):
        """However long the outage, the gap stops widening."""
        monkeypatch.setattr(drive_scheduler.settings,
                            "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 300)
        monkeypatch.setattr(drive_scheduler, "MAX_BACKOFF_SECONDS", 1800)

        assert drive_scheduler._backoff_delay(50) == 1800
        assert all(drive_scheduler._backoff_delay(n) <= 1800 for n in range(0, 60))

    def test_the_loop_actually_applies_the_backoff(self, monkeypatch):
        """
        The arithmetic above is only worth anything if the loop uses it.

        asyncio.to_thread is replaced with an inline shim so each pass
        completes on the event loop: progress then depends on yields alone,
        not on OS thread scheduling. The real threadpool hop stays covered by
        TestPassRunsOffTheEventLoop.
        """
        delays = []
        real_sleep = asyncio.sleep

        async def record(seconds):
            delays.append(seconds)
            await real_sleep(0)

        async def inline(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(drive_scheduler, "run_one_pass",
                            lambda: (_ for _ in ()).throw(RuntimeError("always fails")))
        monkeypatch.setattr(drive_scheduler.asyncio, "to_thread", inline)
        monkeypatch.setattr(drive_scheduler.asyncio, "sleep", record)
        monkeypatch.setattr(drive_scheduler.settings,
                            "GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS", 300)
        monkeypatch.setattr(drive_scheduler, "MAX_BACKOFF_SECONDS", 100_000)

        async def scenario():
            task = asyncio.ensure_future(drive_scheduler._loop())
            # Each iteration now needs one yield, so four is enough for the
            # initial delay plus three failing passes - deterministically.
            while len(delays) < 4:
                await real_sleep(0)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        _run(scenario)

        # delays[0] is the initial delay; the rest are backoff, jittered +-10%.
        assert delays[2] > delays[1] and delays[3] > delays[2], delays
        for failures, actual in enumerate(delays[1:4], start=1):
            expected = drive_scheduler._backoff_delay(failures)
            assert expected * 0.9 <= actual <= expected * 1.1, (failures, actual, expected)

    def test_a_drive_outage_is_reported_not_raised(self, monkeypatch):
        """DriveUnavailable is expected; it must not count as a loop failure."""
        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr(
            drive_scheduler, "SessionLocal",
            _FakeSessionFactory(lambda: (_ for _ in ()).throw(DriveUnavailable("no token"))),
        )
        assert drive_scheduler.run_one_pass() == {"error": "no token"}

    def test_throttling_is_reported_not_raised(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr(
            drive_scheduler, "SessionLocal",
            _FakeSessionFactory(lambda: (_ for _ in ()).throw(DriveRateLimited("slow down"))),
        )
        assert drive_scheduler.run_one_pass() == {"skipped": "rate limited"}


# ======================================================================
# Lifecycle
# ======================================================================
class TestLifecycle:
    def test_stop_cancels_promptly(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler, "run_one_pass", lambda: None)
        state = {}

        async def scenario():
            drive_scheduler.start()
            state["running"] = drive_scheduler.is_running()
            await drive_scheduler.stop()
            state["stopped"] = not drive_scheduler.is_running()

        _run(scenario)
        assert state == {"running": True, "stopped": True}

    def test_starting_twice_does_not_make_two_loops(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler, "run_one_pass", lambda: None)
        state = {}

        async def scenario():
            drive_scheduler.start()
            first = drive_scheduler._task
            drive_scheduler.start()
            state["same"] = drive_scheduler._task is first
            await drive_scheduler.stop()

        _run(scenario)
        assert state["same"] is True

    def test_stop_is_safe_when_never_started(self):
        async def scenario():
            await drive_scheduler.stop()

        _run(scenario)
        assert not drive_scheduler.is_running()

    def test_the_kill_switch_prevents_the_loop_from_starting(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_SYNC_ENABLED", False)
        drive_scheduler.start()
        assert not drive_scheduler.is_running()


# ======================================================================
# Guards
# ======================================================================
class TestGuards:
    def test_a_pass_is_a_no_op_when_drive_is_off(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_ENABLED", False)
        assert drive_scheduler.should_run() is False
        assert drive_scheduler.run_one_pass() is None

    def test_a_pass_is_a_no_op_when_the_sync_is_switched_off(self, monkeypatch):
        monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_SYNC_ENABLED", False)
        assert drive_scheduler.should_run() is False
        assert drive_scheduler.run_one_pass() is None

    def test_a_pass_is_a_no_op_when_drive_was_never_connected(self, monkeypatch, db_session):
        """No integration row means nothing to sync, not an error."""
        monkeypatch.setattr(drive_scheduler, "should_run", lambda: True)
        monkeypatch.setattr("app.services.drive_folder_service.get_integration", lambda db: None)
        monkeypatch.setattr(drive_scheduler, "SessionLocal", _FakeSessionFactory(lambda: {"added": 9}))
        assert drive_scheduler.run_one_pass() is None

    def test_jitter_stays_within_ten_percent(self):
        for _ in range(200):
            value = drive_scheduler._jittered(100)
            assert 90 <= value <= 110


# ======================================================================
# The manual endpoint
# ======================================================================
class TestManualSyncEndpoint:
    def test_a_buyer_is_refused(self, api, db_session, make_user):
        from app.models.buyer import EngagementBuyer
        from app.models.engagement import Engagement

        advisor = make_user(UserRole.ADVISOR)
        owner = make_user(UserRole.CLIENT)
        eng = Engagement(engagement_name="x", primary_advisor_id=advisor.id, client_id=owner.id,
                         client_ids=[owner.id], tool="sale_ready", status="active")
        db_session.add(eng)
        db_session.flush()
        buyer = make_user(UserRole.BUYER)
        db_session.add(EngagementBuyer(engagement_id=eng.id, user_id=buyer.id, status="active"))
        db_session.flush()

        assert api.as_user(buyer).post("/api/drive/sync").status_code == 403

    def test_an_advisor_is_refused(self, api, make_user):
        """Admin only, like every other Drive connection control."""
        assert api.as_user(make_user(UserRole.ADVISOR)).post("/api/drive/sync").status_code == 403

    def test_an_admin_gets_a_clear_answer_when_the_sync_is_off(self, api, make_user, monkeypatch):
        monkeypatch.setattr(drive_scheduler.settings, "GOOGLE_DRIVE_SYNC_ENABLED", False)
        resp = api.as_user(make_user(UserRole.ADMIN)).post("/api/drive/sync")
        assert resp.status_code == 400
        assert "switched off" in resp.json()["detail"]


# ----------------------------------------------------------------------
# A Session stand-in whose sync() is whatever the test supplies
# ----------------------------------------------------------------------
class _FakeSessionFactory:
    """
    Replaces SessionLocal so a pass needs no real Drive and no real session.

    run_one_pass builds its own session inside the worker thread - sessions
    are not thread safe - so the seam has to be the factory, not a session.
    """

    def __init__(self, behaviour):
        self._behaviour = behaviour

    def __call__(self):
        return _FakeSession(self._behaviour)


class _FakeSession:
    def __init__(self, behaviour):
        self._behaviour = behaviour
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _fake_sync(monkeypatch):
    """Route get_drive_sync_service at whatever the fake session was given."""
    class _Service:
        def __init__(self, db):
            self._db = db

        def sync(self):
            return _Result(self._db._behaviour())

    class _Result:
        def __init__(self, value):
            self._value = value

        def as_dict(self):
            return self._value

    monkeypatch.setattr("app.services.drive_sync_service.get_drive_sync_service",
                        lambda db: _Service(db))
    monkeypatch.setattr("app.services.drive_folder_service.get_integration",
                        lambda db: object())
