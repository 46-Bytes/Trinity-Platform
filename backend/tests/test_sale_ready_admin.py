"""
Sale Ready Management: the master content admins edit for future engagements.

The point of nearly every test here is the same invariant - editing master
content changes what the NEXT engagement is built from and leaves every running
engagement exactly as it was. An engagement's tasks and DD items are copies
taken when it was created, and its program guide is a frozen snapshot, so no
admin action reaches back into one.

Runs inside the rollback-only db_session; nothing is written to the database.
"""
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.models.engagement import Engagement
from app.models.sale_ready import (
    EngagementDDItem,
    EngagementSaleReadyGuide,
    ProgramDDTemplate,
    ProgramGuideContent,
    ProgramStage,
    ProgramTaskTemplate,
)
from app.models.task import Task
from app.models.user import UserRole
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.sale_ready_service import get_sale_ready_service

ADMIN_BASE = "/api/sale-ready/admin"
SR_BASE = "/api/sale-ready/engagements"

_NEEDS_MIGRATION = (
    "Sale Ready Management tables are missing. Migrate first:\n"
    "    cd backend && alembic upgrade head"
)


@pytest.fixture(autouse=True)
def schema_and_seed(db_session):
    """Skip the whole module until the Sale Ready Management migration is applied."""
    for table in ("program_guide_content", "engagement_sale_ready_guide"):
        try:
            db_session.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))
        except Exception:
            pytest.skip(_NEEDS_MIGRATION, allow_module_level=True)
    try:
        db_session.execute(text("SELECT guide FROM program_stage LIMIT 0"))
    except Exception:
        pytest.skip(_NEEDS_MIGRATION, allow_module_level=True)

    stage = db_session.query(ProgramStage).filter_by(
        program_type=PROGRAM_SALE_READY, stage_code="M1",
    ).first()
    if stage is None:
        pytest.skip("Sale Ready is not seeded: python scripts/seed_sale_ready_program.py")


@pytest.fixture
def admin(make_user):
    return make_user(UserRole.ADMIN)


@pytest.fixture
def advisor(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def owner(make_user):
    return make_user(UserRole.CLIENT)


def _db_now(db_session):
    """
    The database's own clock, which is what stamps created_at everywhere.

    Postgres runs in the server's local timezone while Python's utcnow() does
    not, so deriving a test timestamp from Python would compare two different
    clocks - here that was a five-hour skew. Everything below is offset from
    this single value instead.
    """
    return db_session.execute(text("SELECT LOCALTIMESTAMP")).scalar()


def _engagement(db_session, advisor, owner, name="Admin test engagement", created_at=None):
    eng = Engagement(
        engagement_name=name,
        primary_advisor_id=advisor.id,
        client_ids=[owner.id],
        tool=PROGRAM_SALE_READY,
        status="active",
    )
    if created_at is not None:
        eng.created_at = created_at
    db_session.add(eng)
    db_session.flush()
    return eng


@pytest.fixture
def engagement(db_session, advisor, owner):
    """A live engagement, already initialized - its tasks and DD items exist."""
    eng = _engagement(db_session, advisor, owner)
    get_sale_ready_service(db_session).ensure_initialized(eng, advisor)
    return eng


def _m1_task_template(db_session):
    return db_session.query(ProgramTaskTemplate).filter_by(
        program_type=PROGRAM_SALE_READY, stage_code="M1", section="must_do", is_active=True,
    ).order_by(ProgramTaskTemplate.default_order.asc()).first()


def _m1_dd_template(db_session):
    return db_session.query(ProgramDDTemplate).filter_by(
        program_type=PROGRAM_SALE_READY, stage_code="M1", is_active=True,
    ).order_by(ProgramDDTemplate.default_order.asc()).first()


# ======================================================================
# Permissions
# ======================================================================
class TestOnlyAdminsReachIt:
    ENDPOINTS = [
        ("get", "/guide"),
        ("get", "/task-templates"),
        ("get", "/dd-templates"),
        ("get", "/dd-categories"),
    ]

    @pytest.mark.parametrize("role", [UserRole.ADVISOR, UserRole.FIRM_ADVISOR,
                                      UserRole.FIRM_ADMIN, UserRole.CLIENT])
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_other_roles_are_refused(self, api, make_user, role, method, path):
        client = api.as_user(make_user(role))
        assert getattr(client, method)(f"{ADMIN_BASE}{path}").status_code == 403

    @pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.SUPER_ADMIN])
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_admins_are_served(self, api, make_user, role, method, path):
        client = api.as_user(make_user(role))
        assert getattr(client, method)(f"{ADMIN_BASE}{path}").status_code == 200

    def test_writes_are_refused_for_an_advisor(self, api, advisor, db_session):
        client = api.as_user(advisor)
        template = _m1_task_template(db_session)
        assert client.patch(f"{ADMIN_BASE}/guide/stages/M1", json={"purpose": "x"}).status_code == 403
        assert client.post(f"{ADMIN_BASE}/task-templates",
                           json={"stage_code": "M1", "section": "must_do", "title": "x"}).status_code == 403
        assert client.delete(f"{ADMIN_BASE}/task-templates/{template.id}").status_code == 403


# ======================================================================
# The structure is fixed
# ======================================================================
class TestStagesAndCategoriesCannotBeRestructured:
    def test_all_fifteen_stages_are_listed_read_only(self, api, admin):
        view = api.as_user(admin).get(f"{ADMIN_BASE}/guide").json()
        assert len(view["stages"]) == 15
        codes = [s["stage_code"] for s in view["stages"]]
        assert codes[:4] == ["DIAG", "APPRAISAL", "PRIORITISE", "WORKSHOP"]
        assert codes[-1] == "CLOSEOUT"

    def test_there_is_no_stage_create_delete_or_reorder_route(self, api, admin):
        client = api.as_user(admin)
        assert client.post(f"{ADMIN_BASE}/guide/stages", json={"stage_code": "M9"}).status_code in (404, 405)
        assert client.delete(f"{ADMIN_BASE}/guide/stages/M1").status_code in (404, 405)

    def test_unknown_stage_is_404(self, api, admin):
        assert api.as_user(admin).patch(
            f"{ADMIN_BASE}/guide/stages/NOPE", json={"purpose": "x"}
        ).status_code == 404

    def test_dd_categories_are_the_fixed_sixteen(self, api, admin):
        categories = api.as_user(admin).get(f"{ADMIN_BASE}/dd-categories").json()
        assert len(categories) == 16
        assert all(c["sub_items"] for c in categories)

    def test_a_new_item_must_use_an_existing_category_and_sub_item(self, api, admin):
        resp = api.as_user(admin).post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": "99", "sub_item_code": "99.1", "document_required": "Invented",
        })
        assert resp.status_code == 400
        assert "existing sub-item" in resp.json()["detail"]

    def test_a_new_item_inherits_stage_and_category_from_its_sub_item(self, api, admin, db_session):
        sibling = _m1_dd_template(db_session)
        created = api.as_user(admin).post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": sibling.category_code,
            "sub_item_code": sibling.sub_item_code,
            "document_required": "A new document",
        }).json()
        assert created["stage_code"] == sibling.stage_code
        assert created["category"] == sibling.category


# ======================================================================
# Editing master content never touches a live engagement
# ======================================================================
class TestEditsDoNotReachLiveEngagements:
    def test_editing_a_task_template_leaves_the_engagement_task_alone(
        self, api, db_session, admin, engagement
    ):
        template = _m1_task_template(db_session)
        get_sale_ready_service(db_session).start_stage(engagement, "M1", admin)
        task = db_session.query(Task).filter_by(
            engagement_id=engagement.id, source_task_template_id=template.id,
        ).one()
        before = task.title

        api.as_user(admin).patch(f"{ADMIN_BASE}/task-templates/{template.id}",
                                 json={"title": "Renamed by the admin"})
        db_session.refresh(task)
        assert task.title == before

    def test_editing_a_dd_template_leaves_the_engagement_item_alone(
        self, api, db_session, admin, engagement
    ):
        template = _m1_dd_template(db_session)
        item = db_session.query(EngagementDDItem).filter_by(
            engagement_id=engagement.id, template_item_id=template.id,
        ).one()
        before = item.document_required

        api.as_user(admin).patch(f"{ADMIN_BASE}/dd-templates/{template.id}",
                                 json={"document_required": "Rewritten by the admin"})
        db_session.refresh(item)
        assert item.document_required == before

    def test_retiring_a_template_leaves_the_engagement_item_in_place(
        self, api, db_session, admin, engagement
    ):
        template = _m1_dd_template(db_session)
        before = db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count()

        assert api.as_user(admin).delete(f"{ADMIN_BASE}/dd-templates/{template.id}").status_code == 204
        db_session.refresh(template)
        assert template.is_active is False

        get_sale_ready_service(db_session).get_dd_checklist(engagement, admin)
        assert db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count() == before
        assert db_session.query(EngagementDDItem).filter_by(
            engagement_id=engagement.id, template_item_id=template.id,
        ).count() == 1

    def test_a_full_round_of_edits_changes_no_engagement_row(
        self, api, db_session, admin, engagement
    ):
        service = get_sale_ready_service(db_session)
        service.start_stage(engagement, "M1", admin)
        task_template, dd_template = _m1_task_template(db_session), _m1_dd_template(db_session)

        def snapshot():
            tasks = db_session.query(Task).filter_by(engagement_id=engagement.id).all()
            items = db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).all()
            return (
                sorted((str(t.id), t.title, t.section, t.status) for t in tasks),
                sorted((str(i.id), i.document_required, i.status, i.display_order) for i in items),
            )

        before = snapshot()
        client = api.as_user(admin)
        client.patch(f"{ADMIN_BASE}/guide/stages/M1", json={"purpose": "Rewritten"})
        client.patch(f"{ADMIN_BASE}/guide/program", json={"rules": [{"title": "T", "body": "B"}]})
        client.patch(f"{ADMIN_BASE}/task-templates/{task_template.id}", json={"title": "Renamed"})
        client.patch(f"{ADMIN_BASE}/dd-templates/{dd_template.id}", json={"document_required": "Rewritten"})
        client.post(f"{ADMIN_BASE}/task-templates",
                    json={"stage_code": "M1", "section": "must_do", "title": "Brand new"})
        client.post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": dd_template.category_code,
            "sub_item_code": dd_template.sub_item_code,
            "document_required": "Brand new",
        })
        service.get_stage_detail(engagement, "M1", admin)
        service.get_dd_checklist(engagement, admin)

        assert snapshot() == before


# ======================================================================
# New master content reaches future engagements only
# ======================================================================
class TestNewContentIsForFutureEngagementsOnly:
    def test_a_new_dd_item_does_not_reach_a_live_engagement(
        self, api, db_session, admin, engagement
    ):
        sibling = _m1_dd_template(db_session)
        before = db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count()

        created = api.as_user(admin).post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": sibling.category_code,
            "sub_item_code": sibling.sub_item_code,
            "document_required": "Added after this engagement began",
        }).json()

        get_sale_ready_service(db_session).get_dd_checklist(engagement, admin)
        assert db_session.query(EngagementDDItem).filter_by(engagement_id=engagement.id).count() == before
        assert db_session.query(EngagementDDItem).filter_by(
            engagement_id=engagement.id, item_key=created["item_key"],
        ).count() == 0

    def test_a_new_dd_item_does_reach_an_engagement_created_afterwards(
        self, api, db_session, admin, advisor, owner
    ):
        sibling = _m1_dd_template(db_session)
        created = api.as_user(admin).post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": sibling.category_code,
            "sub_item_code": sibling.sub_item_code,
            "document_required": "Added before this engagement began",
        }).json()
        db_session.flush()

        later = _engagement(db_session, advisor, owner, "Created after the edit",
                            created_at=_db_now(db_session) + timedelta(minutes=5))
        get_sale_ready_service(db_session).ensure_initialized(later, advisor)

        assert db_session.query(EngagementDDItem).filter_by(
            engagement_id=later.id, item_key=created["item_key"],
        ).count() == 1

    def test_a_new_task_template_does_not_reach_a_started_module(
        self, api, db_session, admin, engagement
    ):
        service = get_sale_ready_service(db_session)
        service.start_stage(engagement, "M1", admin)
        before = db_session.query(Task).filter_by(
            engagement_id=engagement.id, module_reference="M1",
        ).count()

        created = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates", json={
            "stage_code": "M1", "section": "must_do", "title": "Added after the module started",
        }).json()

        # Starting again must not pull it in, and neither must a plain read.
        service.start_stage(engagement, "M1", admin)
        service.get_stage_detail(engagement, "M1", admin)

        assert db_session.query(Task).filter_by(
            engagement_id=engagement.id, module_reference="M1",
        ).count() == before
        assert db_session.query(Task).filter_by(
            engagement_id=engagement.id, source_task_template_id=created["id"],
        ).count() == 0

    def test_a_new_phase_task_template_does_not_reach_a_live_engagement(
        self, api, db_session, admin, engagement
    ):
        before = db_session.query(Task).filter_by(
            engagement_id=engagement.id, module_reference="DIAG",
        ).count()
        api.as_user(admin).post(f"{ADMIN_BASE}/task-templates", json={
            "stage_code": "DIAG", "section": "must_do", "title": "New phase task",
        })
        get_sale_ready_service(db_session).get_roadmap(engagement, admin)
        assert db_session.query(Task).filter_by(
            engagement_id=engagement.id, module_reference="DIAG",
        ).count() == before

    def test_a_retired_template_is_skipped_by_a_new_engagement(
        self, api, db_session, admin, advisor, owner
    ):
        template = _m1_dd_template(db_session)
        api.as_user(admin).delete(f"{ADMIN_BASE}/dd-templates/{template.id}")
        db_session.flush()

        later = _engagement(db_session, advisor, owner, "After the retirement",
                            created_at=_db_now(db_session) + timedelta(minutes=5))
        get_sale_ready_service(db_session).ensure_initialized(later, advisor)

        assert db_session.query(EngagementDDItem).filter_by(
            engagement_id=later.id, template_item_id=template.id,
        ).count() == 0


# ======================================================================
# The guide is frozen per engagement
# ======================================================================
class TestGuideSnapshot:
    def test_it_is_written_once_and_never_rewritten(self, db_session, admin, engagement):
        service = get_sale_ready_service(db_session)
        row = db_session.query(EngagementSaleReadyGuide).filter_by(engagement_id=engagement.id).one()
        original, created_at = row.content, row.created_at

        service.ensure_initialized(engagement, admin)
        service.get_roadmap(engagement, admin)
        db_session.refresh(row)
        assert row.content == original and row.created_at == created_at
        assert db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=engagement.id).count() == 1

    def test_it_holds_the_program_content_and_all_fifteen_stages(self, db_session, engagement):
        content = db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=engagement.id).one().content
        assert set(content) == {"program", "stages"}
        assert set(content["program"]) >= {"workflow", "rules"}
        assert len(content["stages"]) == 15

    def test_every_stage_block_is_normalised(self, db_session, engagement):
        """A snapshot carries the same five keys the admin screen exposes."""
        content = db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=engagement.id).one().content
        for code, block in content["stages"].items():
            assert set(block) == {"purpose", "steps", "watch", "templates", "run_with"}, code
            assert isinstance(block["purpose"], str)
            assert all(isinstance(block[k], list) for k in ("steps", "watch", "templates"))

    def test_a_partially_filled_master_is_still_normalised(
        self, api, db_session, admin, advisor, owner
    ):
        """Editing one field must not leave the next snapshot missing the others."""
        stage = db_session.query(ProgramStage).filter_by(
            program_type=PROGRAM_SALE_READY, stage_code="M7").one()
        stage.guide = {"purpose": "Only a purpose"}
        db_session.flush()

        later = _engagement(db_session, advisor, owner, "After a partial edit")
        get_sale_ready_service(db_session).ensure_initialized(later, advisor)
        block = db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=later.id).one().content["stages"]["M7"]
        assert set(block) == {"purpose", "steps", "watch", "templates", "run_with"}
        assert block["purpose"] == "Only a purpose"
        assert block["steps"] == [] and block["run_with"] is None

    def test_editing_the_guide_does_not_change_a_live_engagement(
        self, api, db_session, admin, engagement
    ):
        before = db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=engagement.id).one().content

        api.as_user(admin).patch(f"{ADMIN_BASE}/guide/stages/M1",
                                 json={"purpose": "Rewritten by the admin"})
        api.as_user(admin).patch(f"{ADMIN_BASE}/guide/program",
                                 json={"workflow": [{"stage": "DIAG", "label": "Rewritten"}]})

        served = api.as_user(admin).get(f"{SR_BASE}/{engagement.id}/guide").json()
        assert served == before
        assert served["stages"]["M1"].get("purpose") != "Rewritten by the admin"

    def test_an_engagement_created_afterwards_gets_the_new_guide(
        self, api, db_session, admin, advisor, owner
    ):
        api.as_user(admin).patch(f"{ADMIN_BASE}/guide/stages/M1",
                                 json={"purpose": "The new purpose"})
        db_session.flush()

        later = _engagement(db_session, advisor, owner, "After the guide edit")
        get_sale_ready_service(db_session).ensure_initialized(later, advisor)
        content = db_session.query(EngagementSaleReadyGuide).filter_by(
            engagement_id=later.id).one().content
        assert content["stages"]["M1"]["purpose"] == "The new purpose"

    def test_the_stage_detail_serves_the_frozen_guide(self, api, db_session, admin, engagement):
        api.as_user(admin).patch(f"{ADMIN_BASE}/guide/stages/M1", json={"purpose": "Rewritten"})
        detail = get_sale_ready_service(db_session).get_stage_detail(engagement, "M1", admin)
        assert detail["guide"].get("purpose") != "Rewritten"


# ======================================================================
# Editing rules
# ======================================================================
class TestGuideEditing:
    def test_each_field_can_be_set_and_others_are_kept(self, api, admin):
        client = api.as_user(admin)
        client.patch(f"{ADMIN_BASE}/guide/stages/M2", json={
            "purpose": "P", "steps": ["one", "two"], "watch": ["careful"],
            "templates": ["A template"], "run_with": "Runs with M7",
        })
        view = client.patch(f"{ADMIN_BASE}/guide/stages/M2", json={"purpose": "P2"}).json()
        guide = next(s for s in view["stages"] if s["stage_code"] == "M2")["guide"]
        assert guide["purpose"] == "P2"
        assert guide["steps"] == ["one", "two"] and guide["watch"] == ["careful"]
        assert guide["templates"] == ["A template"] and guide["run_with"] == "Runs with M7"

    def test_blank_lines_are_dropped(self, api, admin):
        view = api.as_user(admin).patch(f"{ADMIN_BASE}/guide/stages/M3", json={
            "steps": ["  first  ", "", "   ", "second"],
        }).json()
        guide = next(s for s in view["stages"] if s["stage_code"] == "M3")["guide"]
        assert guide["steps"] == ["first", "second"]

    def test_workflow_must_name_a_real_stage(self, api, admin):
        resp = api.as_user(admin).patch(f"{ADMIN_BASE}/guide/program", json={
            "workflow": [{"stage": "NOT_A_STAGE", "label": "x"}],
        })
        assert resp.status_code == 400

    def test_workflow_accepts_the_modules_pseudo_stage(self, api, admin):
        resp = api.as_user(admin).patch(f"{ADMIN_BASE}/guide/program", json={
            "workflow": [{"stage": "modules", "label": "Modules run in roadmap order"}],
        })
        assert resp.status_code == 200


class TestTaskTemplateEditing:
    def test_create_generates_a_key_and_appends(self, api, db_session, admin):
        created = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates", json={
            "stage_code": "M4", "section": "optional", "title": "An optional extra",
        }).json()
        assert created["template_key"].startswith("M4-OPT-")
        assert created["is_active"] is True
        siblings = [t for t in db_session.query(ProgramTaskTemplate).filter_by(
            program_type=PROGRAM_SALE_READY, stage_code="M4", section="optional").all()]
        assert created["default_order"] == max(t.default_order for t in siblings)

    def test_generated_keys_do_not_collide(self, api, admin):
        client = api.as_user(admin)
        keys = {
            client.post(f"{ADMIN_BASE}/task-templates", json={
                "stage_code": "M5", "section": "must_do", "title": f"Task {i}",
            }).json()["template_key"]
            for i in range(3)
        }
        assert len(keys) == 3

    def test_client_specific_cannot_be_templated(self, api, admin):
        resp = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates", json={
            "stage_code": "M1", "section": "client_specific", "title": "x",
        })
        assert resp.status_code == 422

    def test_stage_code_and_key_are_immutable(self, api, db_session, admin):
        template = _m1_task_template(db_session)
        api.as_user(admin).patch(f"{ADMIN_BASE}/task-templates/{template.id}", json={
            "stage_code": "M2", "template_key": "HACKED", "title": "Fine",
        })
        db_session.refresh(template)
        assert template.stage_code == "M1" and template.template_key != "HACKED"
        assert template.title == "Fine"

    def test_unknown_stage_is_refused(self, api, admin):
        resp = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates", json={
            "stage_code": "M99", "section": "must_do", "title": "x",
        })
        assert resp.status_code == 404

    def test_retire_then_restore(self, api, db_session, admin):
        template = _m1_task_template(db_session)
        assert api.as_user(admin).delete(f"{ADMIN_BASE}/task-templates/{template.id}").status_code == 204
        db_session.refresh(template)
        assert template.is_active is False
        api.as_user(admin).patch(f"{ADMIN_BASE}/task-templates/{template.id}", json={"is_active": True})
        db_session.refresh(template)
        assert template.is_active is True

    def test_reorder_rewrites_the_group(self, api, db_session, admin):
        rows = db_session.query(ProgramTaskTemplate).filter_by(
            program_type=PROGRAM_SALE_READY, stage_code="M6", section="must_do", is_active=True,
        ).order_by(ProgramTaskTemplate.default_order.asc()).all()
        ids = [str(r.id) for r in rows]
        reversed_ids = list(reversed(ids))
        result = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates/reorder",
                                         json={"ids": reversed_ids}).json()
        assert [r["id"] for r in result] == reversed_ids
        assert [r["default_order"] for r in result] == list(range(1, len(ids) + 1))

    def test_reorder_must_cover_the_whole_group(self, api, db_session, admin):
        rows = db_session.query(ProgramTaskTemplate).filter_by(
            program_type=PROGRAM_SALE_READY, stage_code="M6", section="must_do", is_active=True,
        ).all()
        resp = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates/reorder",
                                       json={"ids": [str(rows[0].id)]})
        assert resp.status_code == 400

    def test_reorder_cannot_mix_stages(self, api, db_session, admin):
        a = _m1_task_template(db_session)
        b = db_session.query(ProgramTaskTemplate).filter_by(
            program_type=PROGRAM_SALE_READY, stage_code="M2", section="must_do", is_active=True,
        ).first()
        resp = api.as_user(admin).post(f"{ADMIN_BASE}/task-templates/reorder",
                                       json={"ids": [str(a.id), str(b.id)]})
        assert resp.status_code == 400


class TestDDTemplateEditing:
    def test_create_generates_an_item_key(self, api, db_session, admin):
        sibling = _m1_dd_template(db_session)
        created = api.as_user(admin).post(f"{ADMIN_BASE}/dd-templates", json={
            "category_code": sibling.category_code,
            "sub_item_code": sibling.sub_item_code,
            "document_required": "Something new",
        }).json()
        assert created["item_key"].startswith("DD-")
        assert created["item_key"] != sibling.item_key

    def test_stage_and_structure_are_immutable(self, api, db_session, admin):
        template = _m1_dd_template(db_session)
        api.as_user(admin).patch(f"{ADMIN_BASE}/dd-templates/{template.id}", json={
            "stage_code": "M2", "category_code": "9", "sub_item_code": "9.9",
            "document_required": "Fine",
        })
        db_session.refresh(template)
        assert template.stage_code == "M1" and template.category_code != "9"
        assert template.document_required == "Fine"

    def test_retire_then_restore(self, api, db_session, admin):
        template = _m1_dd_template(db_session)
        assert api.as_user(admin).delete(f"{ADMIN_BASE}/dd-templates/{template.id}").status_code == 204
        db_session.refresh(template)
        assert template.is_active is False
        api.as_user(admin).patch(f"{ADMIN_BASE}/dd-templates/{template.id}", json={"is_active": True})
        db_session.refresh(template)
        assert template.is_active is True

    def test_unknown_item_is_404(self, api, admin):
        import uuid as _uuid
        assert api.as_user(admin).patch(
            f"{ADMIN_BASE}/dd-templates/{_uuid.uuid4()}", json={"document_required": "x"}
        ).status_code == 404


# ======================================================================
# Value Builder and other programs are untouched
# ======================================================================
class TestOtherProgramsAreUntouched:
    def test_the_admin_api_only_ever_sees_sale_ready(self, api, admin, db_session):
        view = api.as_user(admin).get(f"{ADMIN_BASE}/guide").json()
        codes = {s["stage_code"] for s in view["stages"]}
        assert not any(c.startswith("V") for c in codes)

        templates = api.as_user(admin).get(f"{ADMIN_BASE}/task-templates").json()
        rows = db_session.query(ProgramTaskTemplate).filter(
            ProgramTaskTemplate.id.in_([t["id"] for t in templates])
        ).all()
        assert all(r.program_type == PROGRAM_SALE_READY for r in rows)

    def test_the_guide_content_row_is_scoped_to_sale_ready(self, api, admin, db_session):
        api.as_user(admin).patch(f"{ADMIN_BASE}/guide/program",
                                 json={"rules": [{"title": "T", "body": "B"}]})
        rows = db_session.query(ProgramGuideContent).all()
        assert {r.program_type for r in rows} == {PROGRAM_SALE_READY}
