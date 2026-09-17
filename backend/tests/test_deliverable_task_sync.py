"""
Tests for tasks feeding back into deliverable completion.

Completion syncs both ways, so the same work is never ticked off twice: closing
the last task generated from a deliverable completes the deliverable, and
completing a deliverable closes those tasks. Three properties carry the whole
feature and each is easy to break by accident:

- each direction only ever CLOSES things. Reopening a task must not un-complete
  a deliverable, and un-completing a deliverable must not reopen its tasks.
  That is also what stops the two halves chasing each other;
- it never fires on nothing. A deliverable with no tasks must not complete
  vacuously, and tasks that belong to no deliverable must not reach one;
- cancelled is ignored in both directions. A cancelled task does not hold its
  deliverable open, and completing a deliverable does not resurrect it.

The task -> deliverable half is triggered in the tasks router, so those tests
drive it through PATCH /api/tasks/{id} rather than writing Task.status directly.

Run with: pytest tests/test_deliverable_task_sync.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.task import Task
from app.models.user import UserRole
from app.services.program_deliverable_service import (
    MODULE_STATUS_COMPLETED,
    MODULE_STATUS_IN_PROGRESS,
    get_program_deliverable_service,
)

DELIVERABLES = "/api/deliverables/engagements"
TASKS = "/api/tasks"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def advisor(db_session, test_engagement, make_user):
    user = make_user(UserRole.ADVISOR)
    test_engagement.primary_advisor_id = user.id
    db_session.flush()
    return user


@pytest.fixture
def client_user(db_session, test_engagement, make_user):
    """A business owner on this engagement, who may be assigned tasks."""
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = [user.id]
    db_session.flush()
    return user


def _preset(db_session, title, mandatory=True, order=1, module_code="V1"):
    row = ProgramModuleDeliverable(
        program_type="value_builder",
        module_code=module_code,
        deliverable_key=f"key-{uuid.uuid4()}",
        title=title,
        is_mandatory=mandatory,
        display_order=order,
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def required(db_session):
    return _preset(db_session, "Financial Health Summary", mandatory=True, order=1)


@pytest.fixture
def optional(db_session):
    return _preset(db_session, "Budget or Forecast Outline", mandatory=False, order=2)


def _generate(api, user, engagement, module_code="V1"):
    return api.as_user(user).post(f"{DELIVERABLES}/{engagement.id}/modules/{module_code}/tasks")


def _complete_task(api, user, task_id, task_status="completed"):
    return api.as_user(user).patch(f"{TASKS}/{task_id}", json={"status": task_status})


def _task_for(db_session, engagement, deliverable):
    return (
        db_session.query(Task)
        .filter(
            Task.engagement_id == engagement.id,
            Task.source_deliverable_id == deliverable.id,
        )
        .one()
    )


def _complete_deliverable(api, user, engagement, deliverable, is_complete=True):
    return api.as_user(user).put(
        f"{DELIVERABLES}/{engagement.id}/items/{deliverable.id}/complete",
        json={"is_complete": is_complete},
    )


def _module(api, user, engagement, module_code="V1"):
    payload = api.as_user(user).get(f"{DELIVERABLES}/{engagement.id}").json()
    return next((m for m in payload["modules"] if m["module_code"] == module_code), None)


def _item(module, title):
    return next(d for d in module["deliverables"] if d["title"] == title)


# ----------------------------------------------------------------------
# The rule itself
# ----------------------------------------------------------------------
class TestTaskCompletionCompletesDeliverable:

    def test_completing_the_only_task_completes_its_deliverable(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        task = _task_for(db_session, test_engagement, required)

        assert _complete_task(api, advisor, task.id).status_code == 200
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is True

    def test_partial_completion_leaves_the_deliverable_incomplete(
        self, api, advisor, db_session, test_engagement, required
    ):
        """A second task added by hand holds the deliverable open."""
        _generate(api, advisor, test_engagement)
        generated = _task_for(db_session, test_engagement, required)
        db_session.add(
            Task(
                engagement_id=test_engagement.id,
                created_by_user_id=advisor.id,
                title="Follow up with the accountant",
                source_deliverable_id=required.id,
            )
        )
        db_session.flush()

        _complete_task(api, advisor, generated.id)
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is False

    def test_a_cancelled_task_does_not_hold_the_deliverable_open(
        self, api, advisor, db_session, test_engagement, required
    ):
        """
        Work that was called off is not outstanding. Otherwise a cancelled task
        would block its deliverable forever, with nothing in the UI to clear it.
        """
        _generate(api, advisor, test_engagement)
        generated = _task_for(db_session, test_engagement, required)
        extra = Task(
            engagement_id=test_engagement.id,
            created_by_user_id=advisor.id,
            title="Chase the bank statements",
            source_deliverable_id=required.id,
            status="cancelled",
        )
        db_session.add(extra)
        db_session.flush()

        _complete_task(api, advisor, generated.id)
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is True

    def test_a_deliverable_with_no_tasks_is_never_auto_completed(
        self, api, advisor, db_session, test_engagement, required, optional
    ):
        """
        The vacuous-truth guard: "every task is closed" is trivially true of a
        deliverable that has none.
        """
        _generate(api, advisor, test_engagement)
        # Give the optional one no task at all.
        db_session.query(Task).filter(Task.source_deliverable_id == optional.id).delete()
        db_session.flush()

        _complete_task(api, advisor, _task_for(db_session, test_engagement, required).id)
        module = _module(api, advisor, test_engagement)
        assert _item(module, optional.title)["is_complete"] is False

    def test_the_service_declines_a_deliverable_with_no_tasks(
        self, db_session, test_engagement, advisor, required
    ):
        """Pinned on the service too, since no router path can reach this."""
        service = get_program_deliverable_service(db_session)
        assert service.complete_deliverable_if_tasks_done(test_engagement, required.id, advisor.id) is None


# ----------------------------------------------------------------------
# The other direction
# ----------------------------------------------------------------------
class TestDeliverableCompletionClosesTasks:

    def test_completing_a_deliverable_completes_its_task(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        assert _complete_deliverable(api, advisor, test_engagement, required).status_code == 200

        task = _task_for(db_session, test_engagement, required)
        db_session.refresh(task)
        assert task.status == "completed"
        assert task.completed_at is not None

    def test_every_open_task_on_that_deliverable_is_closed(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        db_session.add(
            Task(
                engagement_id=test_engagement.id,
                created_by_user_id=advisor.id,
                title="Follow up with the accountant",
                source_deliverable_id=required.id,
                status="in_progress",
            )
        )
        db_session.flush()

        _complete_deliverable(api, advisor, test_engagement, required)

        statuses = {
            t.status
            for t in db_session.query(Task).filter(Task.source_deliverable_id == required.id).all()
        }
        assert statuses == {"completed"}

    def test_a_cancelled_task_is_left_alone(
        self, api, advisor, db_session, test_engagement, required
    ):
        """Work that was called off is not work that got done."""
        cancelled = Task(
            engagement_id=test_engagement.id,
            created_by_user_id=advisor.id,
            title="Chase the bank statements",
            source_deliverable_id=required.id,
            status="cancelled",
        )
        db_session.add(cancelled)
        db_session.flush()

        _generate(api, advisor, test_engagement)
        _complete_deliverable(api, advisor, test_engagement, required)

        db_session.refresh(cancelled)
        assert cancelled.status == "cancelled"

    def test_other_deliverables_tasks_are_untouched(
        self, api, advisor, db_session, test_engagement, required, optional
    ):
        _generate(api, advisor, test_engagement)
        _complete_deliverable(api, advisor, test_engagement, required)

        other = _task_for(db_session, test_engagement, optional)
        db_session.refresh(other)
        assert other.status == "pending"

    def test_an_unrelated_task_is_untouched(
        self, api, advisor, db_session, test_engagement, required
    ):
        manual = Task(
            engagement_id=test_engagement.id,
            created_by_user_id=advisor.id,
            title="Book the quarterly review",
            task_type="manual",
        )
        db_session.add(manual)
        db_session.flush()

        _generate(api, advisor, test_engagement)
        _complete_deliverable(api, advisor, test_engagement, required)

        db_session.refresh(manual)
        assert manual.status == "pending"

    def test_uncompleting_a_deliverable_does_not_reopen_its_tasks(
        self, api, advisor, db_session, test_engagement, required
    ):
        """Each direction only ever closes; that is what stops a loop."""
        _generate(api, advisor, test_engagement)
        _complete_deliverable(api, advisor, test_engagement, required)
        _complete_deliverable(api, advisor, test_engagement, required, is_complete=False)

        task = _task_for(db_session, test_engagement, required)
        db_session.refresh(task)
        assert task.status == "completed"

    def test_completing_a_deliverable_with_no_tasks_is_harmless(
        self, api, advisor, test_engagement, required
    ):
        assert _complete_deliverable(api, advisor, test_engagement, required).status_code == 200
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is True


# ----------------------------------------------------------------------
# Module status
# ----------------------------------------------------------------------
class TestModuleStatusFollows:

    def test_completing_every_required_task_completes_the_module(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        _complete_task(api, advisor, _task_for(db_session, test_engagement, required).id)
        assert _module(api, advisor, test_engagement)["status"] == MODULE_STATUS_COMPLETED

    def test_an_optional_incomplete_deliverable_does_not_block_the_module(
        self, api, advisor, db_session, test_engagement, required, optional
    ):
        _generate(api, advisor, test_engagement)
        _complete_task(api, advisor, _task_for(db_session, test_engagement, required).id)

        module = _module(api, advisor, test_engagement)
        assert _item(module, optional.title)["is_complete"] is False
        assert module["status"] == MODULE_STATUS_COMPLETED

    def test_a_commenced_module_still_completes(
        self, api, advisor, db_session, test_engagement, required
    ):
        """Commencement feeds in_progress only; completion still wins."""
        api.as_user(advisor).post(f"{DELIVERABLES}/{test_engagement.id}/modules/V1/commence")
        _generate(api, advisor, test_engagement)
        _complete_task(api, advisor, _task_for(db_session, test_engagement, required).id)

        module = _module(api, advisor, test_engagement)
        assert module["is_commenced"] is True
        assert module["status"] == MODULE_STATUS_COMPLETED


# ----------------------------------------------------------------------
# One way only
# ----------------------------------------------------------------------
class TestCompletionIsOneWay:

    def test_reopening_a_task_leaves_the_deliverable_complete(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        task = _task_for(db_session, test_engagement, required)
        _complete_task(api, advisor, task.id)

        assert _complete_task(api, advisor, task.id, task_status="pending").status_code == 200

        module = _module(api, advisor, test_engagement)
        assert _item(module, required.title)["is_complete"] is True
        assert module["status"] == MODULE_STATUS_COMPLETED

    def test_reopening_does_not_regress_a_module_that_was_only_commenced(
        self, api, advisor, db_session, test_engagement, required, optional
    ):
        """The optional one keeps the module short of Complete throughout."""
        optional.is_mandatory = True
        db_session.flush()

        _generate(api, advisor, test_engagement)
        task = _task_for(db_session, test_engagement, required)
        _complete_task(api, advisor, task.id)
        _complete_task(api, advisor, task.id, task_status="pending")

        module = _module(api, advisor, test_engagement)
        assert _item(module, required.title)["is_complete"] is True
        assert module["status"] == MODULE_STATUS_IN_PROGRESS


# ----------------------------------------------------------------------
# Who and what triggers it
# ----------------------------------------------------------------------
class TestSyncBoundaries:

    def test_a_client_assignee_completing_the_last_task_completes_it(
        self, api, advisor, client_user, db_session, test_engagement, required
    ):
        """
        Clients are barred from the deliverables API entirely, so this proves
        the sync runs server-side rather than through that guard.
        """
        _generate(api, advisor, test_engagement)
        task = _task_for(db_session, test_engagement, required)
        task.assigned_to_user_ids = [client_user.id]
        db_session.flush()

        assert _complete_task(api, client_user, task.id).status_code == 200
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is True

    def test_a_manual_task_touches_no_deliverable(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        manual = Task(
            engagement_id=test_engagement.id,
            created_by_user_id=advisor.id,
            title="Book the quarterly review",
            task_type="manual",
        )
        db_session.add(manual)
        db_session.flush()

        _complete_task(api, advisor, manual.id)
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is False

    def test_a_diagnostic_task_touches_no_deliverable(
        self, api, advisor, db_session, test_engagement, required
    ):
        _generate(api, advisor, test_engagement)
        generated = Task(
            engagement_id=test_engagement.id,
            created_by_user_id=advisor.id,
            title="Address the weakest capability area",
            task_type="diagnostic_generated",
        )
        db_session.add(generated)
        db_session.flush()

        _complete_task(api, advisor, generated.id)
        assert _item(_module(api, advisor, test_engagement), required.title)["is_complete"] is False

    def test_a_sale_ready_engagement_is_a_no_op(
        self, api, advisor, db_session, test_engagement, required
    ):
        """
        Tasks exist on every engagement; deliverables are Value Builder only.
        The task must still update cleanly.
        """
        _generate(api, advisor, test_engagement)
        task = _task_for(db_session, test_engagement, required)
        test_engagement.tool = "sale_ready"
        db_session.flush()

        assert _complete_task(api, advisor, task.id).status_code == 200

    def test_the_task_still_completes_when_its_deliverable_is_gone(
        self, api, advisor, db_session, test_engagement
    ):
        """A task outliving its deliverable is by design, and must not 500."""
        created = api.as_user(advisor).post(
            f"{DELIVERABLES}/{test_engagement.id}/items",
            json={"module_code": "V1", "title": "Cashflow Forecast", "is_mandatory": True},
        ).json()
        deliverable_id = next(
            d["deliverable_id"]
            for m in created["modules"]
            if m["module_code"] == "V1"
            for d in m["deliverables"]
            if d["title"] == "Cashflow Forecast"
        )

        _generate(api, advisor, test_engagement)
        task = db_session.query(Task).filter(Task.title == "Cashflow Forecast").one()
        api.as_user(advisor).delete(f"{DELIVERABLES}/{test_engagement.id}/items/{deliverable_id}")

        resp = _complete_task(api, advisor, task.id)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
