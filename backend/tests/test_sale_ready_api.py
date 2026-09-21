"""
Sale Ready service and API: initialization, tasks, completion QA, module order
and the DD checklist.

Runs against the seeded Sale Ready templates (scripts/seed_sale_ready_program.py)
inside the rollback-only db_session, so nothing is written to the database.
"""
import pytest

from app.models.engagement import Engagement
from app.models.sale_ready import EngagementDDItem, EngagementStageState, ProgramStage, ProgramTaskTemplate
from app.models.task import Task
from app.models.user import UserRole
from app.services.sale_ready_service import get_sale_ready_service

BASE = "/api/sale-ready/engagements"
M1_TASKS, M1_MUST, M1_DD = 13, 10, 21


@pytest.fixture(autouse=True)
def seeded(db_session):
    if db_session.query(ProgramStage).filter(ProgramStage.program_type == "sale_ready").count() != 15:
        pytest.skip("Sale Ready templates are not seeded: python scripts/seed_sale_ready_program.py")


@pytest.fixture
def created_with_engagement(db_session):
    """
    The templates of every stage whose tasks are created with the engagement.

    Read from the seeded templates rather than hardcoded, so adding a stage's
    tasks (CLOSEOUT, C2) does not break these tests before the reseed.
    """
    codes = {
        s.stage_code for s in db_session.query(ProgramStage).filter_by(
            program_type="sale_ready", task_creation="on_engagement_create", is_active=True)
    }
    templates = db_session.query(ProgramTaskTemplate).filter(
        ProgramTaskTemplate.program_type == "sale_ready",
        ProgramTaskTemplate.is_active == True,  # noqa: E712
        ProgramTaskTemplate.stage_code.in_(codes),
    ).all()
    return templates


@pytest.fixture
def phase_task_count(created_with_engagement):
    return len(created_with_engagement)


@pytest.fixture
def phase_task_stages(created_with_engagement):
    return {t.stage_code for t in created_with_engagement}


@pytest.fixture
def advisor(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def owner(make_user):
    return make_user(UserRole.CLIENT)


@pytest.fixture
def engagement(db_session, advisor, owner):
    eng = Engagement(
        engagement_name="Sale Ready test engagement",
        primary_advisor_id=advisor.id,
        client_ids=[owner.id],
        tool="sale_ready",
    )
    db_session.add(eng)
    db_session.flush()
    return eng


def _sr_tasks(db_session, engagement, stage_code=None):
    q = db_session.query(Task).filter(
        Task.engagement_id == engagement.id, Task.is_deleted == False, Task.section.isnot(None)  # noqa: E712
    )
    if stage_code:
        q = q.filter(Task.module_reference == stage_code)
    return q.all()


def _stage(roadmap, code):
    for group in ("phases", "modules", "post_phases"):
        for s in roadmap[group]:
            if s["stage_code"] == code:
                return s
    raise KeyError(code)


# ----------------------------------------------------------------------
# Initialization
# ----------------------------------------------------------------------
def test_new_engagement_initializes_stages_dd_and_phase_tasks(
    api, db_session, engagement, advisor, phase_task_count, phase_task_stages
):
    resp = api.as_user(advisor).get(f"{BASE}/{engagement.id}/roadmap")
    assert resp.status_code == 200, resp.text
    roadmap = resp.json()

    assert [s["stage_code"] for s in roadmap["phases"]] == ["DIAG", "APPRAISAL", "PRIORITISE", "WORKSHOP"]
    assert [s["stage_code"] for s in roadmap["modules"]] == [f"M{i}" for i in range(1, 9)]
    assert [s["stage_code"] for s in roadmap["post_phases"]] == ["TRANSITION", "SALE_PLANNER", "CLOSEOUT"]
    assert roadmap["order_source"] == "default"
    assert roadmap["modules"][-1]["is_pinned_last"] is True

    assert db_session.query(EngagementStageState).filter_by(engagement_id=engagement.id).count() == 15
    assert db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count() == 210
    tasks = _sr_tasks(db_session, engagement)
    assert len(tasks) == phase_task_count
    assert {t.module_reference for t in tasks} == phase_task_stages
    # Must-do tasks default to the primary advisor.
    assert all(t.assigned_to_user_ids == [advisor.id] for t in tasks)

    # Phase tasks existing does not make a phase In progress; modules are not created yet.
    assert _stage(roadmap, "DIAG")["status"] == "not_started"
    m1 = _stage(roadmap, "M1")
    assert m1["tasks_created"] is False and m1["must_do_total"] == M1_MUST and m1["dd_total"] == M1_DD
    assert roadmap["progress"]["dd_total"] == 210
    assert roadmap["progress"]["phases_total"] == 4 and roadmap["progress"]["modules_total"] == 8


def test_initialization_is_idempotent_and_never_recreates_deleted_tasks(
    api, db_session, engagement, advisor, phase_task_count
):
    client = api.as_user(advisor)
    client.get(f"{BASE}/{engagement.id}/roadmap")
    client.get(f"{BASE}/{engagement.id}/dd")
    client.get(f"{BASE}/{engagement.id}/roadmap")
    assert db_session.query(EngagementStageState).filter_by(engagement_id=engagement.id).count() == 15
    assert db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count() == 210
    assert len(_sr_tasks(db_session, engagement)) == phase_task_count

    deleted = _sr_tasks(db_session, engagement, "DIAG")[0]
    deleted.is_deleted = True
    db_session.flush()
    client.get(f"{BASE}/{engagement.id}/roadmap")
    assert len(_sr_tasks(db_session, engagement)) == phase_task_count - 1


# ----------------------------------------------------------------------
# Stages: start, QA, complete, reopen
# ----------------------------------------------------------------------
def test_start_creates_module_tasks_once(api, db_session, engagement, advisor):
    client = api.as_user(advisor)
    detail = client.get(f"{BASE}/{engagement.id}/stages/M1").json()
    assert detail["stage"]["tasks_created"] is False
    assert len(detail["template_preview"]) == M1_TASKS

    resp = client.post(f"{BASE}/{engagement.id}/stages/M1/start")
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["stage"]["status"] == "in_progress"
    assert detail["stage"]["start_date"] is not None
    assert len(detail["tasks"]) == M1_TASKS and detail["template_preview"] == []
    assert {t["section"] for t in detail["tasks"]} == {"must_do", "optional"}

    client.post(f"{BASE}/{engagement.id}/stages/M1/start")
    assert len(_sr_tasks(db_session, engagement, "M1")) == M1_TASKS


def test_complete_is_gated_by_qa(api, engagement, advisor):
    client = api.as_user(advisor)
    assert client.post(f"{BASE}/{engagement.id}/stages/M2/complete").status_code == 400  # not started

    detail = client.post(f"{BASE}/{engagement.id}/stages/M1/start").json()
    resp = client.post(f"{BASE}/{engagement.id}/stages/M1/complete")
    assert resp.status_code == 400
    assert "must-do" in resp.json()["detail"] and "DD item" in resp.json()["detail"]

    for task in detail["tasks"]:
        if task["section"] == "must_do":
            r = client.patch(f"{BASE}/{engagement.id}/tasks/{task['id']}", json={"status": "completed"})
            assert r.status_code == 200
    for item in detail["dd_items"]:
        # In progress is enough for QA (C14); only "no status" blocks.
        client.patch(f"{BASE}/{engagement.id}/dd/{item['id']}", json={"status": "in_progress"})

    detail = client.get(f"{BASE}/{engagement.id}/stages/M1").json()
    assert detail["qa"]["passed"] is True
    assert detail["stage"]["must_do_resolved"] == M1_MUST

    done = client.post(f"{BASE}/{engagement.id}/stages/M1/complete").json()
    assert done["stage"]["status"] == "completed" and done["completed_by_name"]
    roadmap = client.get(f"{BASE}/{engagement.id}/roadmap").json()
    assert roadmap["progress"]["modules_completed"] == 1

    reopened = client.post(f"{BASE}/{engagement.id}/stages/M1/reopen").json()
    assert reopened["stage"]["status"] == "in_progress" and reopened["completed_at"] is None


def test_stage_dates_lead_and_custom_tasks(api, engagement, advisor, owner):
    client = api.as_user(advisor)
    r = client.patch(f"{BASE}/{engagement.id}/stages/M3", json={"start_date": "2026-10-10", "due_date": "2026-10-01"})
    assert r.status_code == 400
    r = client.patch(f"{BASE}/{engagement.id}/stages/M3", json={"lead_advisor_id": str(owner.id)})
    assert r.status_code == 400  # a client cannot lead
    r = client.patch(f"{BASE}/{engagement.id}/stages/M3",
                     json={"start_date": "2026-10-01", "due_date": "2026-10-30", "lead_advisor_id": str(advisor.id)})
    assert r.status_code == 200 and r.json()["lead_advisor_id"] == str(advisor.id)

    r = client.post(f"{BASE}/{engagement.id}/stages/M3/tasks", json={"title": "Document the workshop hire income"})
    custom = [t for t in r.json()["tasks"] if t["section"] == "client_specific"]
    assert len(custom) == 1 and custom[0]["from_template"] is False

    r = client.patch(f"{BASE}/{engagement.id}/tasks/{custom[0]['id']}",
                     json={"notes": "Accountant to split", "assigned_to_user_id": str(owner.id)})
    task = next(t for t in r.json()["tasks"] if t["id"] == custom[0]["id"])
    assert task["notes"] == "Accountant to split" and task["assigned_to_user_id"] == str(owner.id)
    assert client.patch(f"{BASE}/{engagement.id}/tasks/{custom[0]['id']}",
                        json={"status": "not_applicable"}).status_code == 400



# ----------------------------------------------------------------------
# N/A and blocked (C7: Sale Ready only, never a new shared task status)
# ----------------------------------------------------------------------
def test_task_state_cycle_done_na_blocked_clear(api, engagement, advisor, db_session):
    """The mockup's four-state box, and what each state does to the stage."""
    client = api.as_user(advisor)
    detail = client.post(f"{BASE}/{engagement.id}/stages/M1/start").json()
    must = [t for t in detail["tasks"] if t["section"] == "must_do"]
    url = f"{BASE}/{engagement.id}/tasks/{must[0]['id']}"

    def patch(**body):
        r = client.patch(url, json=body)
        assert r.status_code == 200, r.text
        body = r.json()
        task = next(t for t in body["tasks"] if t["id"] == must[0]["id"])
        return task, body["stage"]["must_do_resolved"], body["qa"]

    task, resolved, _ = patch(status="completed")
    assert (task["status"], task["sale_ready_state"]) == ("completed", None) and resolved == 1

    # Not required: resolved for QA, but the shared status goes back to pending.
    task, resolved, _ = patch(sale_ready_state="not_applicable")
    assert (task["status"], task["sale_ready_state"]) == ("pending", "not_applicable") and resolved == 1

    task, resolved, qa = patch(sale_ready_state="blocked")
    assert (task["status"], task["sale_ready_state"]) == ("pending", "blocked") and resolved == 0
    assert qa["passed"] is False and "blocked" in " ".join(qa["reasons"])

    task, resolved, _ = patch(sale_ready_state=None)
    assert (task["status"], task["sale_ready_state"]) == ("pending", None) and resolved == 0

    assert client.patch(url, json={"sale_ready_state": "cancelled"}).status_code == 400


def test_completing_a_task_clears_its_state(api, engagement, advisor):
    client = api.as_user(advisor)
    detail = client.post(f"{BASE}/{engagement.id}/stages/M1/start").json()
    task_id = next(t["id"] for t in detail["tasks"] if t["section"] == "must_do")
    url = f"{BASE}/{engagement.id}/tasks/{task_id}"

    client.patch(url, json={"sale_ready_state": "blocked"})
    body = client.patch(url, json={"status": "completed"}).json()
    task = next(t for t in body["tasks"] if t["id"] == task_id)
    assert (task["status"], task["sale_ready_state"]) == ("completed", None)


def test_a_marked_task_moves_the_stage_off_not_started(api, engagement, advisor, phase_task_stages):
    """N/A and blocked leave status 'pending', so only the state makes this stage active."""
    stage_code = sorted(phase_task_stages)[0]
    client = api.as_user(advisor)
    detail = client.get(f"{BASE}/{engagement.id}/stages/{stage_code}").json()
    assert detail["stage"]["status"] == "not_started"

    task_id = detail["tasks"][0]["id"]
    body = client.patch(f"{BASE}/{engagement.id}/tasks/{task_id}", json={"sale_ready_state": "blocked"}).json()
    assert body["stage"]["status"] == "in_progress"


def test_not_applicable_lets_a_stage_complete(api, engagement, advisor):
    client = api.as_user(advisor)
    detail = client.post(f"{BASE}/{engagement.id}/stages/M1/start").json()
    for task in detail["tasks"]:
        if task["section"] == "must_do":
            client.patch(f"{BASE}/{engagement.id}/tasks/{task['id']}", json={"sale_ready_state": "not_applicable"})
    for item in detail["dd_items"]:
        client.patch(f"{BASE}/{engagement.id}/dd/{item['id']}", json={"status": "yes"})

    detail = client.get(f"{BASE}/{engagement.id}/stages/M1").json()
    assert detail["qa"]["passed"] is True and detail["stage"]["must_do_resolved"] == M1_MUST
    assert client.post(f"{BASE}/{engagement.id}/stages/M1/complete").status_code == 200


def test_optional_tasks_carry_a_state_without_gating(api, engagement, advisor):
    """The stage screen counts an optional N/A as resolved, so the API must return it."""
    client = api.as_user(advisor)
    detail = client.post(f"{BASE}/{engagement.id}/stages/M1/start").json()
    task_id = next(t["id"] for t in detail["tasks"] if t["section"] == "optional")

    body = client.patch(f"{BASE}/{engagement.id}/tasks/{task_id}",
                        json={"sale_ready_state": "not_applicable"}).json()
    task = next(t for t in body["tasks"] if t["id"] == task_id)
    assert task["sale_ready_state"] == "not_applicable" and task["status"] == "pending"
    # Optional tasks never counted towards the gate, and still do not.
    assert body["stage"]["must_do_resolved"] == 0


def test_state_never_leaks_onto_other_engagement_tasks(api, engagement, advisor, db_session):
    """Every task outside Sale Ready keeps a NULL state, so shared readers are unaffected."""
    client = api.as_user(advisor)
    client.post(f"{BASE}/{engagement.id}/stages/M1/start")
    others = db_session.query(Task).filter(
        Task.engagement_id == engagement.id, Task.section.is_(None)).all()
    assert all(t.sale_ready_state is None for t in others)

# ----------------------------------------------------------------------
# Module order
# ----------------------------------------------------------------------
def test_module_order_keeps_m8_pinned_last(api, engagement, advisor):
    client = api.as_user(advisor)
    client.get(f"{BASE}/{engagement.id}/roadmap")

    bad = ["M8", "M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    assert client.put(f"{BASE}/{engagement.id}/order", json={"module_order": bad}).status_code == 400
    assert client.put(f"{BASE}/{engagement.id}/order", json={"module_order": ["DIAG"]}).status_code == 400

    order = ["M3", "M1", "M2", "M7", "M4", "M5", "M6"]  # M8 omitted: still appended last
    roadmap = client.put(f"{BASE}/{engagement.id}/order", json={"module_order": order}).json()
    assert [m["stage_code"] for m in roadmap["modules"]] == order + ["M8"]
    assert roadmap["order_source"] == "custom"
    assert [m["effective_rank"] for m in roadmap["modules"]] == list(range(1, 9))

    roadmap = client.post(f"{BASE}/{engagement.id}/order/reset").json()
    assert roadmap["order_source"] == "default"
    assert [m["stage_code"] for m in roadmap["modules"]] == [f"M{i}" for i in range(1, 9)]


# ----------------------------------------------------------------------
# DD checklist
# ----------------------------------------------------------------------
def test_dd_edits_are_shared_between_master_and_stage(api, engagement, advisor):
    client = api.as_user(advisor)
    checklist = client.get(f"{BASE}/{engagement.id}/dd").json()
    assert checklist["stats"]["total"] == 210 and checklist["stats"]["no_status"] == 210
    item = next(i for i in checklist["items"] if i["stage_code"] == "M2")

    url = f"{BASE}/{engagement.id}/dd/{item['id']}"
    assert client.patch(url, json={"gap_handling": "refer"}).status_code == 400  # not a gap yet
    assert client.patch(url, json={"status": "maybe"}).status_code == 400
    r = client.patch(url, json={"status": "no", "gap_handling": "refer", "notes": "Owner holds key accounts",
                                "flag_for_m8": True, "responsible_user_id": str(advisor.id)})
    assert r.status_code == 200, r.text
    assert r.json()["gap_handling"] == "refer" and r.json()["flag_for_m8"] is True

    stage_item = next(i for i in client.get(f"{BASE}/{engagement.id}/stages/M2").json()["dd_items"]
                      if i["id"] == item["id"])
    assert stage_item["status"] == "no" and stage_item["notes"] == "Owner holds key accounts"
    flagged = client.get(f"{BASE}/{engagement.id}/stages/M8").json()["flagged_for_review"]
    assert [f["id"] for f in flagged] == [item["id"]]

    roadmap = client.get(f"{BASE}/{engagement.id}/roadmap").json()
    assert roadmap["gaps"] == {"total": 1, "fix": 0, "disclose": 0, "refer": 1, "unhandled": 0}
    stats = client.get(f"{BASE}/{engagement.id}/dd").json()["stats"]
    assert stats["no"] == 1 and stats["referred"] == 1 and stats["flagged"] == 1

    yes = client.patch(url, json={"status": "yes"}).json()
    assert yes["date_completed"] is not None
    assert client.get(f"{BASE}/{engagement.id}/roadmap").json()["gaps"]["total"] == 0


# ----------------------------------------------------------------------
# Access
# ----------------------------------------------------------------------
def test_owner_is_read_only_on_roadmap_and_dd(api, engagement, owner):
    client = api.as_user(owner)
    assert client.get(f"{BASE}/{engagement.id}/roadmap").status_code == 200
    checklist = client.get(f"{BASE}/{engagement.id}/dd")
    assert checklist.status_code == 200
    item_id = checklist.json()["items"][0]["id"]

    assert client.get(f"{BASE}/{engagement.id}/stages/M1").status_code == 403
    assert client.post(f"{BASE}/{engagement.id}/stages/M1/start").status_code == 403
    assert client.patch(f"{BASE}/{engagement.id}/dd/{item_id}", json={"status": "yes"}).status_code == 403
    assert client.put(f"{BASE}/{engagement.id}/order", json={"module_order": ["M2"]}).status_code == 403


def test_outsider_and_wrong_program_are_refused(api, db_session, engagement, make_user):
    outsider = make_user(UserRole.ADVISOR)
    assert api.as_user(outsider).get(f"{BASE}/{engagement.id}/roadmap").status_code == 403

    admin = make_user(UserRole.ADMIN)
    engagement.tool = "value_builder"
    db_session.flush()
    assert api.as_user(admin).get(f"{BASE}/{engagement.id}/roadmap").status_code == 400


# ----------------------------------------------------------------------
# Existing engagement (rolled back like everything else here)
# ----------------------------------------------------------------------
def test_existing_sale_ready_engagement_initializes(db_session):
    existing = db_session.query(Engagement).filter(
        Engagement.tool == "sale_ready", Engagement.is_deleted == False  # noqa: E712
    ).first()
    if existing is None:
        pytest.skip("No existing Sale Ready engagement in this database")

    service = get_sale_ready_service(db_session)
    before_stages = db_session.query(EngagementStageState).filter_by(engagement_id=existing.id).count()
    roadmap = service.get_roadmap(existing)
    again = service.get_roadmap(existing)

    assert db_session.query(EngagementStageState).filter_by(engagement_id=existing.id).count() == 15
    assert db_session.query(EngagementDDItem).filter_by(engagement_id=existing.id).count() == 210
    if before_stages == 0 and existing.primary_advisor_id:
        assert len(_sr_tasks(db_session, existing)) > 0
    assert roadmap["modules"][-1]["stage_code"] == "M8"
    assert roadmap["progress"] == again["progress"]
