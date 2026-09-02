"""
Tests for generating tasks from a module's deliverables.

Part A states four rules about this and every one of them is a rule about what
must NOT happen: nothing is created automatically, one deliverable may carry
several tasks, task completion and deliverable completion never move each
other, and scoping a deliverable out leaves its tasks standing. Rules phrased as
prohibitions are the ones that rot silently, so each has a test here.

Run with: pytest tests/test_deliverable_task_generation.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.task import Task
from app.models.user import UserRole
from app.services.program_deliverable_service import (
    TASK_TYPE_DELIVERABLE,
    get_program_deliverable_service,
)

BASE = "/api/deliverables/engagements"


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
def owner(db_session, test_engagement, make_user):
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = [user.id]
    db_session.flush()
    return user


@pytest.fixture
def outsider(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def presets(db_session, test_engagement):
    """Two mandatory presets and one optional, all on V1."""
    rows = [
        ProgramModuleDeliverable(
            program_type="value_builder",
            module_code="V1",
            deliverable_key=f"key-{uuid.uuid4()}",
            title=title,
            is_mandatory=mandatory,
            display_order=order,
        )
        for order, (title, mandatory) in enumerate(
            [
                ("Financial Health Summary", True),
                ("Margin & Cost Improvement Plan", True),
                ("Budget or Forecast Outline", False),
            ],
            start=1,
        )
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


def _generate(api, user, engagement, module_code="V1"):
    return api.as_user(user).post(f"{BASE}/{engagement.id}/modules/{module_code}/tasks")


def _item(payload, module_code, title):
    module = next(m for m in payload["modules"] if m["module_code"] == module_code)
    return next(d for d in module["deliverables"] if d["title"] == title)


# ----------------------------------------------------------------------
# Role boundary
# ----------------------------------------------------------------------
class TestGenerationRoleBoundary:

    def test_advisor_can_generate(self, api, advisor, test_engagement, presets):
        assert _generate(api, advisor, test_engagement).status_code == 201

    def test_owner_is_denied(self, api, owner, test_engagement, presets):
        """Owners create nothing anywhere in Part A's roles matrix."""
        assert _generate(api, owner, test_engagement).status_code == 403

    def test_outsider_is_denied(self, api, outsider, test_engagement, presets):
        assert _generate(api, outsider, test_engagement).status_code == 403

    def test_unknown_engagement_is_404(self, api, advisor, presets):
        assert api.as_user(advisor).post(f"{BASE}/{uuid.uuid4()}/modules/V1/tasks").status_code == 404

    def test_owner_generates_nothing(self, api, owner, advisor, db_session, test_engagement, presets):
        """A refused call must not have written before refusing."""
        _generate(api, owner, test_engagement)
        assert db_session.query(Task).filter(Task.engagement_id == test_engagement.id).count() == 0


# ----------------------------------------------------------------------
# What gets created
# ----------------------------------------------------------------------
class TestGeneration:

    def test_one_task_per_deliverable(self, api, advisor, db_session, test_engagement, presets):
        resp = _generate(api, advisor, test_engagement)
        assert resp.json()["created_count"] == 3

        tasks = db_session.query(Task).filter(Task.engagement_id == test_engagement.id).all()
        assert {t.title for t in tasks} == {p.title for p in presets}

    def test_tasks_carry_the_module_and_source(self, api, advisor, db_session, test_engagement, presets):
        _generate(api, advisor, test_engagement)
        tasks = db_session.query(Task).filter(Task.engagement_id == test_engagement.id).all()

        assert {t.module_reference for t in tasks} == {"V1"}
        assert {t.task_type for t in tasks} == {TASK_TYPE_DELIVERABLE}
        # A preset is addressed by its LIBRARY id, which is what the API also
        # accepts for mutations. Storing anything else would leave the count
        # unable to find its own tasks.
        assert {t.source_deliverable_id for t in tasks} == {p.id for p in presets}

    def test_mandatory_deliverables_produce_higher_priority(self, api, advisor, db_session, test_engagement, presets):
        _generate(api, advisor, test_engagement)
        by_title = {
            t.title: t.priority
            for t in db_session.query(Task).filter(Task.engagement_id == test_engagement.id).all()
        }
        assert by_title["Financial Health Summary"] == "high"
        assert by_title["Budget or Forecast Outline"] == "medium"

    def test_task_count_is_reported_back(self, api, advisor, test_engagement, presets):
        payload = _generate(api, advisor, test_engagement).json()["view"]
        assert _item(payload, "V1", "Financial Health Summary")["task_count"] == 1

    def test_task_count_is_zero_before_generating(self, api, advisor, test_engagement, presets):
        payload = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").json()
        assert all(d["task_count"] == 0 for m in payload["modules"] for d in m["deliverables"])

    def test_only_the_named_module_is_generated(self, api, advisor, db_session, test_engagement, presets):
        other = ProgramModuleDeliverable(
            program_type="value_builder",
            module_code="V2",
            deliverable_key=f"key-{uuid.uuid4()}",
            title="Strategy Workbook",
            is_mandatory=True,
            display_order=1,
        )
        db_session.add(other)
        db_session.flush()

        _generate(api, advisor, test_engagement, module_code="V1")
        assert db_session.query(Task).filter(Task.title == "Strategy Workbook").count() == 0

    def test_a_module_with_no_deliverables_creates_nothing(self, api, advisor, test_engagement, presets):
        resp = _generate(api, advisor, test_engagement, module_code="V7")
        assert resp.status_code == 201
        assert resp.json()["created_count"] == 0


# ----------------------------------------------------------------------
# Idempotence and skipping
# ----------------------------------------------------------------------
class TestRegeneration:

    def test_second_click_creates_nothing(self, api, advisor, db_session, test_engagement, presets):
        _generate(api, advisor, test_engagement)
        second = _generate(api, advisor, test_engagement).json()

        assert second["created_count"] == 0
        assert second["skipped_count"] == 3
        assert db_session.query(Task).filter(Task.engagement_id == test_engagement.id).count() == 3

    def test_a_new_deliverable_generates_without_duplicating_the_rest(
        self, api, advisor, db_session, test_engagement, presets
    ):
        """
        The button has to keep working as an advisor adds deliverables, without
        re-creating the tasks already there.
        """
        _generate(api, advisor, test_engagement)
        api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/items",
            json={"module_code": "V1", "title": "Cashflow Forecast", "is_mandatory": True},
        )

        resp = _generate(api, advisor, test_engagement).json()
        assert resp["created_count"] == 1
        assert db_session.query(Task).filter(Task.engagement_id == test_engagement.id).count() == 4

    def test_scoped_out_deliverables_are_skipped(self, api, advisor, db_session, test_engagement, presets):
        """Excluded from completion, so generating work for them contradicts the advisor."""
        api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{presets[0].id}/scope",
            json={"is_in_scope": False},
        )
        assert _generate(api, advisor, test_engagement).json()["created_count"] == 2
        assert db_session.query(Task).filter(Task.title == presets[0].title).count() == 0

    def test_completed_deliverables_are_skipped(self, api, advisor, test_engagement, presets):
        api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{presets[0].id}/complete",
            json={"is_complete": True},
        )
        assert _generate(api, advisor, test_engagement).json()["created_count"] == 2

    def test_a_deleted_task_can_be_regenerated(self, api, advisor, db_session, test_engagement, presets):
        """
        The count reads live and excludes soft-deleted tasks, so deleting one
        puts the deliverable back in the button's scope rather than stranding it.
        """
        _generate(api, advisor, test_engagement)
        task = db_session.query(Task).filter(Task.title == presets[0].title).one()
        task.is_deleted = True
        db_session.flush()

        assert _generate(api, advisor, test_engagement).json()["created_count"] == 1

    def test_several_tasks_per_deliverable_are_expressible(self, db_session, test_engagement, advisor, presets):
        """
        Part A allows one deliverable to carry several tasks. Nothing enforces
        uniqueness on source_deliverable_id - generation declines to add a
        second, but the column does not stop one being added by hand.
        """
        service = get_program_deliverable_service(db_session)
        service.generate_tasks_for_module(test_engagement, "V1", advisor.id)

        db_session.add(
            Task(
                engagement_id=test_engagement.id,
                created_by_user_id=advisor.id,
                title="Follow up with the accountant",
                source_deliverable_id=presets[0].id,
            )
        )
        db_session.flush()

        states = service.get_deliverable_states_by_module(test_engagement)["V1"]
        assert next(s.task_count for s in states if s.deliverable_id == presets[0].id) == 2


# ----------------------------------------------------------------------
# The separation Part A is most explicit about
# ----------------------------------------------------------------------
class TestTasksAndDeliverablesStaySeparate:

    def test_generating_does_not_complete_anything(self, api, advisor, test_engagement, presets):
        payload = _generate(api, advisor, test_engagement).json()["view"]
        module = next(m for m in payload["modules"] if m["module_code"] == "V1")

        assert all(not d["is_complete"] for d in module["deliverables"])
        assert module["status"] == "not_started"

    def test_completing_a_task_does_not_complete_its_deliverable(
        self, api, advisor, db_session, test_engagement, presets
    ):
        _generate(api, advisor, test_engagement)
        for task in db_session.query(Task).filter(Task.engagement_id == test_engagement.id).all():
            task.status = "completed"
        db_session.flush()

        payload = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").json()
        module = next(m for m in payload["modules"] if m["module_code"] == "V1")
        assert all(not d["is_complete"] for d in module["deliverables"])
        assert module["status"] == "not_started"

    def test_completing_a_deliverable_does_not_touch_its_tasks(
        self, api, advisor, db_session, test_engagement, presets
    ):
        _generate(api, advisor, test_engagement)
        api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{presets[0].id}/complete",
            json={"is_complete": True},
        )

        task = db_session.query(Task).filter(Task.title == presets[0].title).one()
        assert task.status == "pending"

    def test_scoping_out_leaves_the_task_standing(self, api, advisor, db_session, test_engagement, presets):
        """
        The rule the missing foreign key exists to protect. An FK to the
        instance row would have been ondelete='CASCADE' through the library,
        so retiring a preset would have deleted a client's tasks.
        """
        _generate(api, advisor, test_engagement)
        api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/items/{presets[0].id}/scope",
            json={"is_in_scope": False},
        )

        assert db_session.query(Task).filter(Task.title == presets[0].title).count() == 1

    def test_removing_an_advisor_deliverable_leaves_its_task_standing(
        self, api, advisor, db_session, test_engagement
    ):
        created = api.as_user(advisor).post(
            f"{BASE}/{test_engagement.id}/items",
            json={"module_code": "V1", "title": "Cashflow Forecast", "is_mandatory": True},
        ).json()
        deliverable_id = _item(created, "V1", "Cashflow Forecast")["deliverable_id"]

        _generate(api, advisor, test_engagement)
        api.as_user(advisor).delete(f"{BASE}/{test_engagement.id}/items/{deliverable_id}")

        assert db_session.query(Task).filter(Task.title == "Cashflow Forecast").count() == 1

    def test_a_module_is_never_completed_by_its_tasks(self, db_session, test_engagement, advisor, presets):
        """
        derive_module_status reads deliverables only. Pinned directly rather
        than through the API, so a future change to the status query that
        started consulting task_count fails here.
        """
        from app.services.program_deliverable_service import derive_module_status

        service = get_program_deliverable_service(db_session)
        service.generate_tasks_for_module(test_engagement, "V1", advisor.id)

        states = service.get_deliverable_states_by_module(test_engagement)["V1"]
        assert all(s.task_count == 1 for s in states)
        assert derive_module_status(states) == "not_started"
