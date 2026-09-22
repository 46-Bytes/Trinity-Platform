"""
Sale Ready Sale Planner and Close-out.

Closing the program saves the close-out decisions, records who closed it, and
ends the engagement (lifecycle status 'ended') in one commit. It deliberately
leaves engagement.completed_at alone - that column belongs to the diagnostic
flows, which treat it as write-once, and the generic End does not set it either.
Runs inside the rollback-only db_session; nothing is written to the database.
"""
import pytest

from app.models.engagement import Engagement
from app.models.sale_ready import EngagementProgramCloseout, EngagementSalePlanner, EngagementStageState, ProgramStage
from app.models.user import UserRole
from app.services.sale_ready_planner_service import CloseoutPermissionError, get_sale_ready_planner_service
from app.utils.auth import get_original_user

BASE = "/api/sale-ready/engagements"


@pytest.fixture(autouse=True)
def seeded(db_session):
    stage = db_session.query(ProgramStage).filter_by(program_type="sale_ready", stage_code="SALE_PLANNER").first()
    if not stage or not stage.ui_config:
        pytest.skip("Sale Ready templates are not seeded: python scripts/seed_sale_ready_program.py")


@pytest.fixture
def advisor(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def owner(make_user):
    return make_user(UserRole.CLIENT)


@pytest.fixture
def engagement(db_session, advisor, owner):
    eng = Engagement(
        engagement_name="Sale Ready close-out test",
        primary_advisor_id=advisor.id,
        client_ids=[owner.id],
        tool="sale_ready",
        status="active",
    )
    db_session.add(eng)
    db_session.flush()
    return eng


# ----------------------------------------------------------------------
# Sale Planner
# ----------------------------------------------------------------------
def test_sale_planner_read_is_empty_and_creates_nothing(api, db_session, engagement, advisor):
    view = api.as_user(advisor).get(f"{BASE}/{engagement.id}/sale-planner").json()
    assert view["sale_type"] is None and view["sale_structures"] == []
    assert view["issues"] == {} and view["issues_total"] == 43
    assert set(view["config"]) == {"sale_types", "sale_structures", "value_proposition_structures",
                                   "marketing_questions", "issues"}
    assert db_session.query(EngagementSalePlanner).filter_by(engagement_id=engagement.id).count() == 0


def test_sale_planner_saves_by_key_and_merges_maps(api, engagement, advisor):
    client = api.as_user(advisor)
    url = f"{BASE}/{engagement.id}/sale-planner"
    question = "who_is_the_buyer_describe_the_ideal_buyer"

    r = client.patch(url, json={
        "sale_type": "share_sale",
        "sale_structures": ["cash_purchase", "earn_out"],
        "value_propositions": {"earn_out": "Bridges the valuation gap"},
        "marketing_answers": {question: "A regional competitor"},
        "issues": {"staff_entitlements": {"addressed": True, "note": "Covered in M4"}},
    })
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["sale_type"] == "share_sale" and view["sale_structures"] == ["cash_purchase", "earn_out"]
    assert view["issues_addressed"] == 1 and view["updated_by_name"]

    # Maps merge by key; other answers are kept, and null removes one.
    view = client.patch(url, json={
        "value_propositions": {"cash_purchase": "Clean exit"},
        "issues": {"when_to_tell_staff": {"addressed": False, "note": "Decided at workshop"}},
    }).json()
    assert view["value_propositions"] == {"earn_out": "Bridges the valuation gap", "cash_purchase": "Clean exit"}
    assert set(view["issues"]) == {"staff_entitlements", "when_to_tell_staff"}
    view = client.patch(url, json={"value_propositions": {"earn_out": None}, "sale_type": None}).json()
    assert view["value_propositions"] == {"cash_purchase": "Clean exit"} and view["sale_type"] is None

    roadmap = client.get(f"{BASE}/{engagement.id}/roadmap").json()
    assert roadmap["sale_planner_issues"] == {"addressed": 1, "total": 43}


@pytest.mark.parametrize("body", [
    {"sale_type": "merger"},
    {"sale_structures": ["cash_purchase", "cash_purchase"]},
    {"sale_structures": ["barter"]},
    {"marketing_answers": {"not_a_question": "x"}},
    {"issues": {"staff_entitlements": {"addressed": "yes"}}},
    {"issues": {"staff_entitlements": "done"}},
])
def test_sale_planner_rejects_unknown_keys_and_bad_values(api, engagement, advisor, body):
    # 422 when the request shape itself is wrong, 400 when the service rejects a value.
    assert api.as_user(advisor).patch(f"{BASE}/{engagement.id}/sale-planner", json=body).status_code in (400, 422)


def test_owner_cannot_read_or_edit_planner_or_closeout(api, engagement, owner):
    client = api.as_user(owner)
    assert client.get(f"{BASE}/{engagement.id}/sale-planner").status_code == 403
    assert client.patch(f"{BASE}/{engagement.id}/sale-planner", json={"sale_type": "share_sale"}).status_code == 403
    assert client.get(f"{BASE}/{engagement.id}/closeout").status_code == 403
    assert client.post(f"{BASE}/{engagement.id}/closeout/close",
                       json={"confirm_without_referral": True}).status_code == 403


# ----------------------------------------------------------------------
# Close-out
# ----------------------------------------------------------------------
def test_close_requires_confirmation_without_referral_and_changes_nothing(api, db_session, engagement, advisor):
    client = api.as_user(advisor)
    r = client.post(f"{BASE}/{engagement.id}/closeout/close", json={"ongoing_assistance": "Quarterly check-in"})
    assert r.status_code == 400 and "without referring" in r.json()["detail"]

    db_session.refresh(engagement)
    assert engagement.status == "active" and engagement.completed_at is None
    assert db_session.query(EngagementProgramCloseout).filter_by(engagement_id=engagement.id).count() == 0


def test_close_ends_engagement_and_reopen_recommences(api, db_session, engagement, advisor):
    client = api.as_user(advisor)
    client.patch(f"{BASE}/{engagement.id}/closeout", json={"fresh_appraisal_required": True})

    r = client.post(f"{BASE}/{engagement.id}/closeout/close",
                    json={"referred_to_benchmark": True, "ongoing_assistance": "  Monthly calls  "})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["is_closed"] and view["closed_at"] and view["closed_by_name"]
    assert view["fresh_appraisal_required"] and view["referred_to_benchmark"]
    assert view["ongoing_assistance"] == "Monthly calls"
    assert view["engagement_status"] == "ended"
    assert view["engagement_completed_at"] is None, "close must not write the shared column"

    row = db_session.query(EngagementProgramCloseout).filter_by(engagement_id=engagement.id).one()
    assert row.closed_by_user_id == advisor.id and row.closed_by_original_user_id is None
    db_session.refresh(engagement)
    assert engagement.status == "ended"
    assert engagement.completed_at is None, "close must not write the shared column"

    roadmap = client.get(f"{BASE}/{engagement.id}/roadmap").json()
    assert roadmap["closeout"]["is_closed"] and roadmap["closeout"]["referred_to_benchmark"]

    # Closed means locked: no edits and no second close.
    assert client.patch(f"{BASE}/{engagement.id}/closeout", json={"ongoing_assistance": "x"}).status_code == 400
    assert client.post(f"{BASE}/{engagement.id}/closeout/close",
                       json={"confirm_without_referral": True}).status_code == 400

    view = client.post(f"{BASE}/{engagement.id}/closeout/reopen").json()
    assert not view["is_closed"] and view["closed_at"] is None and view["engagement_status"] == "active"
    assert view["ongoing_assistance"] == "Monthly calls"  # decisions are kept
    assert client.post(f"{BASE}/{engagement.id}/closeout/reopen").status_code == 400


def test_close_program_does_not_complete_p7_stage(api, db_session, engagement, advisor):
    """Closing the program ends the engagement; P7 completes only via its own Mark complete."""
    client = api.as_user(advisor)
    stage_url = f"{BASE}/{engagement.id}/stages/CLOSEOUT"

    def p7_state():
        return db_session.query(EngagementStageState).filter_by(
            engagement_id=engagement.id, stage_code="CLOSEOUT"
        ).one()

    assert client.get(stage_url).json()["stage"]["status"] == "not_started"

    r = client.post(f"{BASE}/{engagement.id}/closeout/close", json={"referred_to_benchmark": True})
    assert r.status_code == 200, r.text
    assert r.json()["is_closed"] and r.json()["engagement_status"] == "ended"

    # The engagement has ended, but P7 is untouched.
    detail = client.get(stage_url).json()
    assert detail["stage"]["status"] == "not_started" and detail["completed_at"] is None
    assert p7_state().status == "not_started" and p7_state().completed_at is None
    roadmap = client.get(f"{BASE}/{engagement.id}/roadmap").json()
    assert next(s for s in roadmap["post_phases"] if s["stage_code"] == "CLOSEOUT")["status"] == "not_started"
    assert roadmap["closeout"]["is_closed"]

    # P7's normal Mark complete is what completes it. Its must-do tasks (C2) gate
    # that, so resolve whatever the templates currently create.
    for task in client.get(stage_url).json()["tasks"]:
        if task["section"] == "must_do":
            assert client.patch(
                f"{BASE}/{engagement.id}/tasks/{task['id']}", json={"status": "completed"}
            ).status_code == 200
    done = client.post(f"{stage_url}/complete").json()
    assert done["stage"]["status"] == "completed" and done["completed_at"] is not None
    assert p7_state().completed_by_user_id == advisor.id
    assert client.get(f"{BASE}/{engagement.id}/closeout").json()["is_closed"]

    # Reopening the program leaves P7 as it is.
    client.post(f"{BASE}/{engagement.id}/closeout/reopen")
    assert client.get(stage_url).json()["stage"]["status"] == "completed"


def test_close_with_confirmation_and_no_referral(api, engagement, advisor):
    r = api.as_user(advisor).post(f"{BASE}/{engagement.id}/closeout/close", json={"confirm_without_referral": True})
    assert r.status_code == 200 and r.json()["engagement_status"] == "ended"
    assert r.json()["referred_to_benchmark"] is False


def test_close_records_original_user_when_impersonating(api, db_session, engagement, advisor, make_user):
    from app.main import app

    super_admin = make_user(UserRole.SUPER_ADMIN)
    app.dependency_overrides[get_original_user] = lambda: super_admin
    try:
        r = api.as_user(advisor).post(f"{BASE}/{engagement.id}/closeout/close", json={"referred_to_benchmark": True})
    finally:
        app.dependency_overrides.pop(get_original_user, None)
    assert r.status_code == 200, r.text
    row = db_session.query(EngagementProgramCloseout).filter_by(engagement_id=engagement.id).one()
    assert row.closed_by_user_id == advisor.id and row.closed_by_original_user_id == super_admin.id


def test_unassigned_role_cannot_close(db_session, engagement, advisor):
    service = get_sale_ready_planner_service(db_session)
    with pytest.raises(CloseoutPermissionError):
        service.close_program(engagement, {}, True, advisor, None, can_change_status=False)
    db_session.refresh(engagement)
    assert engagement.status == "active"


def test_close_is_all_or_nothing(db_session, engagement, advisor, monkeypatch):
    db_session.commit()  # the engagement itself must survive the rollback under test
    service = get_sale_ready_planner_service(db_session)

    def failing_commit():
        raise RuntimeError("database went away")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        service.close_program(engagement, {"referred_to_benchmark": True}, False, advisor, None, can_change_status=True)
    monkeypatch.undo()

    db_session.refresh(engagement)
    assert engagement.status == "active" and engagement.completed_at is None
    assert db_session.query(EngagementProgramCloseout).filter_by(engagement_id=engagement.id).count() == 0


@pytest.fixture
def seeded_issue_keys(db_session):
    """The Sale Planner issue keys, from the seeded stage config."""
    stage = db_session.query(ProgramStage).filter_by(
        program_type="sale_ready", stage_code="SALE_PLANNER").first()
    return [i["key"] for i in stage.ui_config["issues"]]


# ----------------------------------------------------------------------
# Regressions
# ----------------------------------------------------------------------
class TestIssueNoteIsNotLostByTheCheckbox:
    """
    A partial issue payload patches only the fields it carries. The checkbox
    sends `addressed` alone, so it can no longer overwrite a note saved a
    moment earlier by the note field's blur.
    """

    KEY = "staff_entitlements"

    def _patch(self, client, engagement, issue):
        return client.patch(f"{BASE}/{engagement.id}/sale-planner", json={"issues": {self.KEY: issue}})

    def test_toggling_addressed_keeps_the_note(self, api, engagement, advisor):
        client = api.as_user(advisor)
        self._patch(client, engagement, {"addressed": False, "note": "Covered in M4"})
        view = self._patch(client, engagement, {"addressed": True}).json()
        assert view["issues"][self.KEY] == {"addressed": True, "note": "Covered in M4"}

    def test_saving_a_note_keeps_addressed(self, api, engagement, advisor):
        client = api.as_user(advisor)
        self._patch(client, engagement, {"addressed": True, "note": ""})
        view = self._patch(client, engagement, {"note": "Handled in M2"}).json()
        assert view["issues"][self.KEY] == {"addressed": True, "note": "Handled in M2"}

    def test_the_reported_two_request_sequence(self, api, engagement, advisor):
        """
        The exact pair the UI emits: the note's blur commit, then the checkbox
        built from the state rendered before that commit returned.
        """
        client = api.as_user(advisor)
        a = self._patch(client, engagement, {"note": "Handled in M2"})
        assert a.json()["issues"][self.KEY]["note"] == "Handled in M2"
        b = self._patch(client, engagement, {"addressed": True})
        assert b.json()["issues"][self.KEY] == {"addressed": True, "note": "Handled in M2"}

    def test_a_new_key_still_defaults(self, api, engagement, advisor):
        view = self._patch(api.as_user(advisor), engagement, {"note": "Only a note"}).json()
        assert view["issues"][self.KEY] == {"addressed": False, "note": "Only a note"}

    def test_null_still_removes_the_issue(self, api, engagement, advisor):
        client = api.as_user(advisor)
        self._patch(client, engagement, {"addressed": True, "note": "Covered in M4"})
        view = self._patch(client, engagement, None).json()
        assert self.KEY not in view["issues"]

    def test_other_issues_are_untouched(self, api, engagement, advisor, seeded_issue_keys):
        client = api.as_user(advisor)
        other = next(k for k in seeded_issue_keys if k != self.KEY)
        client.patch(f"{BASE}/{engagement.id}/sale-planner", json={"issues": {
            self.KEY: {"addressed": True, "note": "Covered in M4"},
            other: {"addressed": False, "note": "Still open"},
        }})
        view = self._patch(client, engagement, {"addressed": False}).json()
        assert view["issues"][other] == {"addressed": False, "note": "Still open"}


class TestCanCloseIsReportedToTheUi:
    """
    Opening the panel is wider than closing it, so the view carries the
    capability and the button follows it instead of 403ing.
    """

    def _view(self, api, engagement, user):
        return api.as_user(user).get(f"{BASE}/{engagement.id}/closeout").json()

    def test_assigned_primary_advisor_can_close(self, api, engagement, advisor):
        assert self._view(api, engagement, advisor)["can_close"] is True

    def test_secondary_advisor_can_close(self, api, db_session, engagement, make_user):
        second = make_user(UserRole.ADVISOR)
        engagement.secondary_advisor_ids = [second.id]
        db_session.flush()
        assert self._view(api, engagement, second)["can_close"] is True

    @pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.SUPER_ADMIN])
    def test_admins_can_close(self, api, engagement, make_user, role):
        assert self._view(api, engagement, make_user(role))["can_close"] is True

    def test_associated_but_unassigned_advisor_cannot_close(
        self, api, db_session, engagement, owner, make_user
    ):
        """Reaches the panel through AdvisorClient, but is not on the engagement."""
        from app.models.adv_client import AdvisorClient
        other = make_user(UserRole.ADVISOR)
        engagement.client_id = owner.id
        db_session.add(AdvisorClient(advisor_id=other.id, client_id=owner.id, status="active"))
        db_session.flush()

        view = self._view(api, engagement, other)
        assert view["can_close"] is False
        # The backend guard is unchanged - the flag only stops the pointless click.
        assert api.as_user(other).post(
            f"{BASE}/{engagement.id}/closeout/close", json={"referred_to_benchmark": True}
        ).status_code == 403

    def test_can_close_is_reported_on_every_closeout_response(self, api, engagement, advisor):
        client = api.as_user(advisor)
        assert client.patch(f"{BASE}/{engagement.id}/closeout",
                            json={"fresh_appraisal_required": True}).json()["can_close"] is True
        assert client.post(f"{BASE}/{engagement.id}/closeout/close",
                           json={"referred_to_benchmark": True}).json()["can_close"] is True
        assert client.post(f"{BASE}/{engagement.id}/closeout/reopen").json()["can_close"] is True


class TestCloseDoesNotTouchTheSharedCompletedAt:
    """
    engagement.completed_at belongs to the diagnostic flows, which all write it
    once and never again, and it is published as end_date. Sale Ready must not
    write it, so a close cannot destroy a date it did not set.
    """

    def test_a_pre_existing_value_survives_close_and_reopen(self, api, db_session, engagement, advisor):
        from datetime import datetime
        original = datetime(2025, 1, 15, 9, 0, 0)
        engagement.completed_at = original
        db_session.flush()

        client = api.as_user(advisor)
        assert client.post(f"{BASE}/{engagement.id}/closeout/close",
                           json={"referred_to_benchmark": True}).status_code == 200
        db_session.refresh(engagement)
        assert engagement.completed_at == original, "close overwrote a date it does not own"

        assert client.post(f"{BASE}/{engagement.id}/closeout/reopen").status_code == 200
        db_session.refresh(engagement)
        assert engagement.completed_at == original, "reopen cleared a date it does not own"

    def test_close_leaves_it_null_when_it_was_null(self, api, db_session, engagement, advisor):
        api.as_user(advisor).post(f"{BASE}/{engagement.id}/closeout/close",
                                  json={"referred_to_benchmark": True})
        db_session.refresh(engagement)
        assert engagement.completed_at is None


class TestGenericRecommenceReopensTheProgram:
    """
    The lifecycle Recommence and the dedicated Reopen must agree, so the
    engagement can never be active while the program says it is closed.
    """

    STATUS_URL = "/api/engagements"

    def _close(self, client, engagement):
        return client.post(f"{BASE}/{engagement.id}/closeout/close", json={"referred_to_benchmark": True})

    def test_recommence_clears_the_close(self, api, db_session, engagement, advisor):
        client = api.as_user(advisor)
        assert self._close(client, engagement).status_code == 200

        r = client.post(f"{self.STATUS_URL}/{engagement.id}/status", json={"status": "active"})
        assert r.status_code == 200

        row = db_session.query(EngagementProgramCloseout).filter_by(engagement_id=engagement.id).one()
        assert row.closed_at is None and row.closed_by_user_id is None

        view = client.get(f"{BASE}/{engagement.id}/closeout").json()
        assert view["is_closed"] is False
        # Unlocked again: the decisions are editable and a second close is possible.
        assert client.patch(f"{BASE}/{engagement.id}/closeout",
                            json={"fresh_appraisal_required": True}).status_code == 200
        assert self._close(client, engagement).status_code == 200

    def test_recommence_keeps_the_close_out_decisions(self, api, engagement, advisor):
        client = api.as_user(advisor)
        client.patch(f"{BASE}/{engagement.id}/closeout", json={"ongoing_assistance": "Monthly calls"})
        self._close(client, engagement)
        client.post(f"{self.STATUS_URL}/{engagement.id}/status", json={"status": "active"})
        view = client.get(f"{BASE}/{engagement.id}/closeout").json()
        assert view["ongoing_assistance"] == "Monthly calls" and view["referred_to_benchmark"] is True

    def test_generic_end_does_not_close_the_program(self, api, db_session, engagement, advisor):
        """Closing records decisions and stays a deliberate act; ending is not mirrored."""
        client = api.as_user(advisor)
        assert client.post(f"{self.STATUS_URL}/{engagement.id}/status",
                           json={"status": "ended"}).status_code == 200
        assert client.get(f"{BASE}/{engagement.id}/closeout").json()["is_closed"] is False
        db_session.refresh(engagement)
        assert engagement.completed_at is None

    def test_pausing_a_closed_program_leaves_it_closed(self, api, engagement, advisor):
        """Only the recommence transition reconciles; pause must not reopen."""
        client = api.as_user(advisor)
        self._close(client, engagement)
        assert client.post(f"{self.STATUS_URL}/{engagement.id}/status",
                           json={"status": "paused"}).status_code == 200
        assert client.get(f"{BASE}/{engagement.id}/closeout").json()["is_closed"] is True

    def test_recommence_without_a_closeout_row_is_a_no_op(self, api, db_session, engagement, advisor):
        client = api.as_user(advisor)
        assert client.post(f"{self.STATUS_URL}/{engagement.id}/status",
                           json={"status": "active"}).status_code == 200
        assert db_session.query(EngagementProgramCloseout).filter_by(
            engagement_id=engagement.id).count() == 0

    @pytest.mark.parametrize("tool", ["value_builder", "bba_builder", None])
    def test_other_programs_recommence_untouched(self, api, db_session, advisor, owner, tool):
        """The hook is scoped to sale_ready; every other tool takes the original path."""
        eng = Engagement(engagement_name=f"{tool} lifecycle", primary_advisor_id=advisor.id,
                         client_ids=[owner.id], tool=tool, status="ended")
        db_session.add(eng)
        db_session.flush()
        r = api.as_user(advisor).post(f"{self.STATUS_URL}/{eng.id}/status", json={"status": "active"})
        assert r.status_code == 200
        db_session.refresh(eng)
        assert eng.status == "active" and eng.completed_at is None
