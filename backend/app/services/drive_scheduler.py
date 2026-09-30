"""
The clock behind the Drive data room sync.

One asyncio task, started with the API and cancelled with it, running
DriveSyncService.sync() every few minutes. No Celery, no broker, no scheduler
process - the API is the whole deployment, which is what this codebase
actually runs today.

Three things here are not obvious and are the reason this file exists rather
than a two-line asyncio.sleep loop:

  - sync() is blocking. SQLAlchemy and googleapiclient both block, so a pass
    run directly on the event loop would freeze every request for its whole
    duration. Each pass goes through a worker thread, and the session is
    created inside that thread because Sessions are not thread safe;

  - more than one API instance may be running. Exclusion uses a Postgres
    advisory lock rather than Redis: Postgres is the one piece of
    infrastructure that certainly exists in every environment, and Redis is
    not provisioned in production on any merged branch;

  - the loop must outlive anything that goes wrong inside it. An unhandled
    error here would stop syncing silently and for good, so the pass is
    wrapped and failures back off instead of repeating at full rate.
"""
import asyncio
import logging
import random
from typing import Optional

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, engine
from app.services.drive_client import DriveRateLimited, DriveUnavailable, drive_enabled

logger = logging.getLogger(__name__)

# Any constant will do; it only has to be the same in every instance. Chosen
# from a range nothing else in Trinity uses.
ADVISORY_LOCK_KEY = 918_273_645

# Long enough that a rolling restart does not have every replica hit Drive at
# once, and that `uvicorn --reload` does not fire a pass on every code save.
INITIAL_DELAY_SECONDS = 30

# Consecutive failures widen the gap rather than hammering a broken Drive.
MAX_BACKOFF_SECONDS = 1800

_task: Optional[asyncio.Task] = None


def _interval() -> float:
    return float(settings.GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS)


def _jittered(seconds: float) -> float:
    """
    Plus or minus 10%.

    Without it, replicas that started together tick together forever, and
    every pass contends for the same lock at the same instant.
    """
    return seconds * random.uniform(0.9, 1.1)


def _backoff_delay(failures: int) -> float:
    """
    How long to wait after `failures` consecutive failed passes.

    Doubles each time from the normal interval and stops at
    MAX_BACKOFF_SECONDS, so a Drive outage is retried at a widening interval
    instead of every five minutes for hours. Zero failures means the normal
    interval.

    Pure and separate from the loop so it can be tested for what it is -
    arithmetic - rather than by running the scheduler and watching the clock.
    """
    if failures <= 0:
        return _interval()
    return min(_interval() * (2 ** failures), MAX_BACKOFF_SECONDS)


def should_run() -> bool:
    """Whether a periodic pass is wanted at all. Cheap, no I/O."""
    return bool(settings.GOOGLE_DRIVE_SYNC_ENABLED) and drive_enabled()


def run_one_pass() -> Optional[dict]:
    """
    One sync, guarded by the advisory lock. Blocking - call it in a thread.

    Returns the pass result, or None when another instance holds the lock or
    there is nothing to do. Never raises for the ordinary Drive failures;
    anything else is left to the caller to log.
    """
    if not should_run():
        return None

    # A transaction-scoped lock, deliberately. The session-scoped variant
    # lives on the backend connection, and SQLAlchemy pools connections - a
    # missed unlock would hand the lock to whatever borrows that connection
    # next. This one is released when the transaction ends, including when
    # the process dies mid-pass.
    with engine.connect() as lock_connection:
        with lock_connection.begin():
            acquired = lock_connection.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY},
            ).scalar()
            if not acquired:
                logger.debug("Drive sync skipped: another instance holds the lock")
                return None

            db = SessionLocal()
            try:
                from app.services.drive_folder_service import get_integration
                from app.services.drive_sync_service import get_drive_sync_service

                if get_integration(db) is None:
                    return None
                return get_drive_sync_service(db).sync().as_dict()
            except DriveRateLimited as exc:
                # Throttling says nothing about the connection's health, so
                # nothing is recorded against it. The next tick tries again.
                logger.info("Drive sync throttled: %s", exc)
                return {"skipped": "rate limited"}
            except DriveUnavailable as exc:
                # Expected while Drive is unconfigured, unreachable or the
                # token has been revoked. sync() has already recorded it on
                # the connection for the admin screen.
                logger.warning("Drive sync unavailable: %s", exc)
                return {"error": str(exc)}
            finally:
                db.close()


async def _loop() -> None:
    """
    Tick forever.

    The first pass waits, so a rolling restart does not stampede Drive and a
    developer saving a file does not trigger a sync.
    """
    try:
        await asyncio.sleep(_jittered(INITIAL_DELAY_SECONDS))
    except asyncio.CancelledError:
        return

    failures = 0
    while True:
        try:
            result = await asyncio.to_thread(run_one_pass)
            failures = 0
            if result:
                logger.info("Drive sync pass: %s", result)
        except asyncio.CancelledError:
            # Shutdown. Re-raised so the task ends rather than looping.
            raise
        except BaseException:
            # Deliberately broad. An unhandled error escaping here would end
            # the task and stop syncing for the lifetime of the process, with
            # nothing to say so - exactly the silent failure this guards.
            failures += 1
            logger.exception("Drive sync pass failed (%d in a row); next attempt in %.0fs",
                             failures, _backoff_delay(failures))
        delay = _backoff_delay(failures)

        try:
            await asyncio.sleep(_jittered(delay))
        except asyncio.CancelledError:
            raise


def start() -> None:
    """Begin ticking. Safe to call twice; the second call is ignored."""
    global _task
    if _task is not None and not _task.done():
        return
    if not settings.GOOGLE_DRIVE_SYNC_ENABLED:
        logger.info("Drive sync scheduler is switched off (GOOGLE_DRIVE_SYNC_ENABLED)")
        return
    _task = asyncio.create_task(_loop(), name="drive-sync-scheduler")
    logger.info("Drive sync scheduler started; every %.0fs after a %ds delay",
                _interval(), INITIAL_DELAY_SECONDS)


async def stop() -> None:
    """Cancel and wait. Called on shutdown so a pass does not outlive the app."""
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Drive sync scheduler did not stop cleanly")
    finally:
        _task = None
        logger.info("Drive sync scheduler stopped")


def is_running() -> bool:
    """For tests and the admin status endpoint."""
    return _task is not None and not _task.done()
