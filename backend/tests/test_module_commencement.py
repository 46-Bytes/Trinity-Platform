"""
Service and endpoint tests for "Commence Module".

Commencement is the only thing that sets a module's status by hand. These pin
the two properties that matter: it reaches in_progress with nothing ticked, and
it never overrides what the deliverables say about completion.

Run with: pytest tests/test_module_commencement.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.program_guide import EngagementModuleCommencement
from app.models.user import UserRole
from app.services.program_deliverable_service import (
    MODULE_STATUS_COMPLETED,
    MODULE_STATUS_IN_PROGRESS,
    MODULE_STATUS_NOT_STARTED,
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
def preset(db_session):
    """One mandatory preset on V1, so the module has something to derive from."""
    row = ProgramModuleDeliverable(
        program_type="value_builder",
        module_code="V1",
        deliverable_key=f"key-{uuid.uuid4()}",
        title="Financial Health Summary",
        is_mandatory=True,
        display_order=1,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _module(payload, module_code):
    return next((m for m in payload["modules"] if m["module_code"] == module_code), None)


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------
class TestServiceCommencement:

    def test_untouched_module_is_not_started(self, db_session, test_engagement, preset):
        service = get_program_deliverable_service(db_session)
        assert service.get_module_statuses(test_engagement)["V1"] == MODULE_STATUS_NOT_STARTED

    def test_commencing_moves_it_to_in_progress(self, db_session, test_engagement, preset, test_user):
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V1", test_user.id)
        assert service.get_module_statuses(test_engagement)["V1"] == MODULE_STATUS_IN_PROGRESS

    def test_commencing_records_who_and_when(self, db_session, test_engagement, test_user):
        service = get_program_deliverable_service(db_session)
        row = service.set_module_commenced(test_engagement, "V1", test_user.id)
        assert row.is_commenced is True
        assert row.commenced_by_user_id == test_user.id
        assert row.commenced_at is not None

    def test_commencing_twice_is_idempotent(self, db_session, test_engagement, test_user):
        """A double click must not create a second row or rewrite the timestamp."""
        service = get_program_deliverable_service(db_session)
        first = service.set_module_commenced(test_engagement, "V1", test_user.id)
        first_at = first.commenced_at
        service.set_module_commenced(test_engagement, "V1", test_user.id)

        rows = db_session.query(EngagementModuleCommencement).filter(
            EngagementModuleCommencement.engagement_id == test_engagement.id,
            EngagementModuleCommencement.module_code == "V1",
        ).all()
        assert len(rows) == 1
        assert rows[0].commenced_at == first_at

    def test_commencing_creates_no_deliverable_state(self, db_session, test_engagement, preset, test_user):
        """Commencement is module-level only - it must tick nothing."""
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V1", test_user.id)

        states = service.get_deliverable_states_by_module(test_engagement)["V1"]
        assert all(not s.complete for s in states)

    def test_completion_still_wins(self, db_session, test_engagement, preset, test_user):
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V1", test_user.id)
        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)
        assert service.get_module_statuses(test_engagement)["V1"] == MODULE_STATUS_COMPLETED

    def test_unticking_leaves_it_in_progress(self, db_session, test_engagement, preset, test_user):
        """The reason commencement is stored rather than inferred."""
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V1", test_user.id)
        service.set_deliverable_complete(test_engagement, preset.id, True, test_user.id)
        service.set_deliverable_complete(test_engagement, preset.id, False, test_user.id)
        assert service.get_module_statuses(test_engagement)["V1"] == MODULE_STATUS_IN_PROGRESS

    def test_commenced_module_with_no_deliverables_has_a_status(self, db_session, test_engagement, test_user):
        """V7 has nothing authored, so it appears only because it was commenced."""
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V7", test_user.id)
        assert service.get_module_statuses(test_engagement)["V7"] == MODULE_STATUS_IN_PROGRESS

    def test_commencement_is_per_module(self, db_session, test_engagement, preset, test_user):
        service = get_program_deliverable_service(db_session)
        service.set_module_commenced(test_engagement, "V2", test_user.id)
        statuses = service.get_module_statuses(test_engagement)
        assert statuses["V2"] == MODULE_STATUS_IN_PROGRESS
        assert statuses["V1"] == MODULE_STATUS_NOT_STARTED

    def test_blank_module_code_is_rejected(self, db_session, test_engagement, test_user):
        service = get_program_deliverable_service(db_session)
        with pytest.raises(ValueError):
            service.set_module_commenced(test_engagement, "   ", test_user.id)


# ----------------------------------------------------------------------
# Endpoint
# ----------------------------------------------------------------------
class TestCommenceEndpoint:

    def test_advisor_can_commence_and_gets_the_view_back(self, api, advisor, test_engagement, preset):
        resp = api.as_user(advisor).post(f"{BASE}/{test_engagement.id}/modules/V1/commence")
        assert resp.status_code == 200, resp.text

        module = _module(resp.json(), "V1")
        assert module["status"] == MODULE_STATUS_IN_PROGRESS
        assert module["is_commenced"] is True

    def test_view_reports_commencement_on_the_next_read(self, api, advisor, test_engagement, preset):
        api.as_user(advisor).post(f"{BASE}/{test_engagement.id}/modules/V1/commence")
        resp = api.as_user(advisor).get(f"{BASE}/{test_engagement.id}")
        assert _module(resp.json(), "V1")["status"] == MODULE_STATUS_IN_PROGRESS

    def test_commenced_module_without_deliverables_is_listed(self, api, advisor, test_engagement):
        resp = api.as_user(advisor).post(f"{BASE}/{test_engagement.id}/modules/V7/commence")
        module = _module(resp.json(), "V7")
        assert module is not None
        assert module["deliverables"] == []
        assert module["status"] == MODULE_STATUS_IN_PROGRESS

    def test_owner_is_denied(self, api, owner, test_engagement):
        """Commencing is an advisor's decision; owners get the dashboard only."""
        resp = api.as_user(owner).post(f"{BASE}/{test_engagement.id}/modules/V1/commence")
        assert resp.status_code == 403

    def test_outsider_is_denied(self, api, outsider, test_engagement):
        resp = api.as_user(outsider).post(f"{BASE}/{test_engagement.id}/modules/V1/commence")
        assert resp.status_code == 403

    def test_unknown_engagement_is_404(self, api, advisor):
        resp = api.as_user(advisor).post(f"{BASE}/{uuid.uuid4()}/modules/V1/commence")
        assert resp.status_code == 404
