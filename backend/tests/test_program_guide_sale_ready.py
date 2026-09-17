"""
Sale Ready support in the Program Guide.

The Program Guide was built for Value Builder and guarded itself with
`engagement.tool != "value_builder"` in five places. Those guards now go through
app.services.program_registry, so the framework serves any listed program.

What these tests are actually protecting:

  - Sale Ready is accepted wherever Value Builder is, with the SAME
    authorization rules. Generalising a tool check is exactly the kind of change
    that quietly widens access, so the role boundary is re-asserted here for a
    sale_ready engagement rather than assumed from the Value Builder suite.
  - The taxonomy follows the program. Sale Ready must rank M1-M8 and Value
    Builder V1-V11; a single hardcoded taxonomy left behind would show one
    program the other's modules.
  - A tool that is NOT a program guide is still refused. Widening the guard to
    two programs must not widen it to everything.

Content is deliberately not asserted on: the client's Sale Ready module cards
and deliverables do not exist yet, so every test below authors the rows it needs.
"""
import uuid

import pytest

from app.models.diagnostic import Diagnostic
from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.program_guide import ProgramModuleContent
from app.models.user import UserRole
from app.services.program_guide_service import get_program_guide_service
from app.services.program_registry import (
    PROGRAM_SALE_READY,
    PROGRAM_VALUE_BUILDER,
    SUPPORTED_PROGRAM_TYPES,
    is_supported_program,
    program_label,
    supported_programs_phrase,
)
from app.services.scoring_service import ScoringService

GUIDE = "/api/program-guide/engagements"
DELIVERABLES = "/api/deliverables/engagements"

# A real Engagement.tool that is not a module-based program. Used to prove the
# guard still refuses something, rather than having been removed outright.
UNSUPPORTED_TOOL = "bba_builder"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def sale_ready_engagement(db_session, test_engagement):
    """
    The shared test engagement, switched to Sale Ready.

    Reuses test_engagement rather than building a second one so that
    `clean_library` and `make_diagnostic` - both bound to it - keep applying.
    """
    test_engagement.tool = PROGRAM_SALE_READY
    db_session.flush()
    return test_engagement


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
def sale_ready_cards(db_session, clean_library):
    """Module cards for every Sale Ready module, titled from the taxonomy."""
    rows = [
        ProgramModuleContent(
            program_type=PROGRAM_SALE_READY,
            module_code=code,
            display_order=order,
            title=title,
        )
        for order, (code, title) in enumerate(ScoringService.SALE_READY_MODULES.items(), start=1)
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


@pytest.fixture
def sale_ready_preset(db_session, clean_library):
    """One mandatory preset deliverable on M1."""
    row = ProgramModuleDeliverable(
        program_type=PROGRAM_SALE_READY,
        module_code="M1",
        deliverable_key=f"sr-{uuid.uuid4().hex[:8]}",
        title="Sale Ready test deliverable",
        is_mandatory=True,
        display_order=1,
        is_active=True,
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def make_sale_ready_diagnostic(db_session, sale_ready_engagement, test_user):
    """A completed diagnostic on the Sale Ready engagement."""
    def _make(scores, overall=None, status="completed"):
        diagnostic = Diagnostic(
            engagement_id=sale_ready_engagement.id,
            created_by_user_id=test_user.id,
            questions={},
            status=status,
            overall_score=overall,
            module_scores={
                "modules": {
                    code: {"module": code, "score": score, "count": count}
                    for code, (score, count) in scores.items()
                }
            },
        )
        db_session.add(diagnostic)
        db_session.flush()
        return diagnostic
    return _make


# ----------------------------------------------------------------------
# The registry itself - pure, no database
# ----------------------------------------------------------------------
class TestProgramRegistry:

    def test_both_programs_are_supported(self):
        assert is_supported_program(PROGRAM_VALUE_BUILDER)
        assert is_supported_program(PROGRAM_SALE_READY)

    @pytest.mark.parametrize("tool", [UNSUPPORTED_TOOL, "kpi_builder", "", None])
    def test_other_tools_are_not(self, tool):
        assert not is_supported_program(tool)

    def test_labels(self):
        assert program_label(PROGRAM_VALUE_BUILDER) == "Value Builder"
        assert program_label(PROGRAM_SALE_READY) == "Sale Ready"

    def test_unknown_label_falls_back_to_the_raw_value(self):
        """Never render 'undefined' at a user: an unknown tool shows itself."""
        assert program_label("mystery_tool") == "mystery_tool"
        assert program_label(None) == "unknown"

    def test_phrase_names_every_supported_program(self):
        phrase = supported_programs_phrase()
        assert "Value Builder" in phrase and "Sale Ready" in phrase

    def test_registry_and_scoring_taxonomy_agree(self):
        """
        Every supported program must have a module taxonomy to rank by.

        ScoringService.get_modules falls back to Sale Ready for anything it does
        not recognise, so this asserts on identity rather than truthiness - a
        program silently served the wrong taxonomy is the failure to catch.
        """
        by_program = {p: ScoringService.get_modules(p) for p in SUPPORTED_PROGRAM_TYPES}
        assert by_program[PROGRAM_VALUE_BUILDER] is ScoringService.VALUE_BUILDER_MODULES
        assert by_program[PROGRAM_SALE_READY] is ScoringService.SALE_READY_MODULES


class TestSaleReadyTaxonomy:

    def test_sale_ready_is_m1_to_m8(self):
        assert list(ScoringService.get_modules(PROGRAM_SALE_READY)) == [
            "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
        ]

    def test_value_builder_is_unchanged(self):
        assert list(ScoringService.get_modules(PROGRAM_VALUE_BUILDER)) == [
            "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11",
        ]


# ----------------------------------------------------------------------
# Ordering
# ----------------------------------------------------------------------
class TestSaleReadyOrdering:

    def test_default_order_is_the_full_taxonomy(self, db_session, sale_ready_engagement):
        """No diagnostic: every module, in taxonomy order, reported as default."""
        result = get_program_guide_service(db_session).compute_recommended_order(sale_ready_engagement)

        assert result["source"] == "default"
        assert result["order"] == list(ScoringService.SALE_READY_MODULES)
        assert result["diagnostic_id"] is None

    def test_worst_scoring_module_is_ranked_first(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        make_sale_ready_diagnostic({"M1": (4.5, 6), "M2": (1.2, 5), "M3": (3.0, 4)})
        result = get_program_guide_service(db_session).compute_recommended_order(sale_ready_engagement)

        assert result["source"] == "diagnostic"
        assert result["order"][:3] == ["M2", "M3", "M1"]

    def test_unscored_modules_are_appended_in_taxonomy_order(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        """
        A module the diagnostic never scored must not rank as if it scored zero.
        It goes after every scored module, in taxonomy order.
        """
        make_sale_ready_diagnostic({"M8": (2.0, 3)})
        result = get_program_guide_service(db_session).compute_recommended_order(sale_ready_engagement)

        assert result["order"][0] == "M8"
        assert result["order"][1:] == ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]

    def test_ties_break_on_taxonomy_position(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        """Equal scores must not swap places between requests."""
        make_sale_ready_diagnostic({"M3": (2.5, 4), "M1": (2.5, 4)})
        service = get_program_guide_service(db_session)

        first = service.compute_recommended_order(sale_ready_engagement)["order"]
        second = service.compute_recommended_order(sale_ready_engagement)["order"]

        assert first[:2] == ["M1", "M3"]
        assert first == second

    def test_unsupported_tool_reports_unsupported(self, db_session, test_engagement):
        test_engagement.tool = UNSUPPORTED_TOOL
        db_session.flush()
        result = get_program_guide_service(db_session).compute_recommended_order(test_engagement)

        assert result["source"] == "unsupported"
        assert result["order"] == []

    def test_value_builder_ordering_is_unchanged(
        self, db_session, test_engagement, test_user
    ):
        """Regression: the Value Builder path still ranks V-codes."""
        db_session.add(Diagnostic(
            engagement_id=test_engagement.id,
            created_by_user_id=test_user.id,
            questions={},
            status="completed",
            module_scores={"modules": {"V4": {"module": "V4", "score": 1.0, "count": 3}}},
        ))
        db_session.flush()

        result = get_program_guide_service(db_session).compute_recommended_order(test_engagement)

        assert result["source"] == "diagnostic"
        assert result["order"][0] == "V4"
        assert set(result["order"]) == set(ScoringService.VALUE_BUILDER_MODULES)


class TestSaleReadyCustomOrder:

    def test_advisor_override_wins_and_resets(
        self, db_session, sale_ready_engagement, test_user
    ):
        service = get_program_guide_service(db_session)

        custom = service.set_custom_order(sale_ready_engagement, ["M5", "M2"], test_user.id)
        assert custom["source"] == "custom"
        assert custom["order"][:2] == ["M5", "M2"]
        # Partial overrides are valid: the rest falls through to the computed order.
        assert set(custom["order"]) == set(ScoringService.SALE_READY_MODULES)

        reset = service.reset_custom_order(sale_ready_engagement)
        assert reset["source"] == "default"
        assert reset["order"] == list(ScoringService.SALE_READY_MODULES)


# ----------------------------------------------------------------------
# Insights and value movement
# ----------------------------------------------------------------------
class TestSaleReadyInsights:

    def test_insights_cover_every_sale_ready_module(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        make_sale_ready_diagnostic({"M1": (1.0, 4)}, overall=2.2)
        payload = get_program_guide_service(db_session).compute_module_insights(sale_ready_engagement)

        assert payload["program_type"] == PROGRAM_SALE_READY
        assert payload["has_scores"] is True
        assert [m["module_code"] for m in payload["modules"]] == list(ScoringService.SALE_READY_MODULES)

        m1 = next(m for m in payload["modules"] if m["module_code"] == "M1")
        assert m1["module_name"] == ScoringService.SALE_READY_MODULES["M1"]
        assert m1["score"] == 1.0
        assert m1["rag"] == "Red"

    def test_unscored_module_reports_null_not_zero(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        make_sale_ready_diagnostic({"M1": (3.0, 4)})
        payload = get_program_guide_service(db_session).compute_module_insights(sale_ready_engagement)

        m8 = next(m for m in payload["modules"] if m["module_code"] == "M8")
        assert m8["score"] is None
        assert m8["rag"] is None

    def test_unsupported_tool_returns_no_modules(self, db_session, test_engagement):
        test_engagement.tool = UNSUPPORTED_TOOL
        db_session.flush()
        payload = get_program_guide_service(db_session).compute_module_insights(test_engagement)

        assert payload["has_scores"] is False
        assert payload["modules"] == []

    def test_value_movement_uses_the_sale_ready_taxonomy(
        self, db_session, sale_ready_engagement, make_sale_ready_diagnostic
    ):
        """
        compute_value_movement takes the engagement, not just its id, precisely
        so it can pick the right taxonomy. Two completed diagnostics required.
        """
        make_sale_ready_diagnostic({"M1": (2.0, 4)}, overall=2.0)
        make_sale_ready_diagnostic({"M1": (3.5, 4)}, overall=3.0)

        payload = get_program_guide_service(db_session).compute_value_movement(sale_ready_engagement)

        assert payload["has_comparison"] is True
        codes = [m["module_code"] for m in payload["module_movements"]]
        assert codes == list(ScoringService.SALE_READY_MODULES)
        assert not any(c.startswith("V") for c in codes)


# ----------------------------------------------------------------------
# API acceptance and authorization
# ----------------------------------------------------------------------
class TestProgramGuideApiAcceptsSaleReady:

    def test_guide_is_served(self, api, advisor, sale_ready_engagement, sale_ready_cards):
        body = api.as_user(advisor).get(f"{GUIDE}/{sale_ready_engagement.id}").json()

        assert body["program_type"] == PROGRAM_SALE_READY
        assert [m["module_code"] for m in body["modules"]] == list(ScoringService.SALE_READY_MODULES)

    def test_insights_are_served(self, api, advisor, sale_ready_engagement):
        assert api.as_user(advisor).get(f"{GUIDE}/{sale_ready_engagement.id}/insights").status_code == 200

    def test_dashboard_is_served(self, api, advisor, sale_ready_engagement, sale_ready_cards):
        body = api.as_user(advisor).get(f"{GUIDE}/{sale_ready_engagement.id}/dashboard").json()
        assert body["total_modules"] == len(ScoringService.SALE_READY_MODULES)

    def test_reorder_round_trips(self, api, advisor, sale_ready_engagement, sale_ready_cards):
        client = api.as_user(advisor)
        body = client.put(
            f"{GUIDE}/{sale_ready_engagement.id}/order",
            json={"module_order": ["M6", "M1"]},
        ).json()

        assert body["order_source"] == "custom"
        assert [m["module_code"] for m in body["modules"]][:2] == ["M6", "M1"]

        reset = client.post(f"{GUIDE}/{sale_ready_engagement.id}/order/reset").json()
        assert reset["order_source"] == "default"

    def test_content_library_is_queryable_by_program_type(self, api, advisor, sale_ready_cards):
        resp = api.as_user(advisor).get(f"/api/program-guide/content?program_type={PROGRAM_SALE_READY}")
        assert resp.status_code == 200
        assert {row["module_code"] for row in resp.json()} == set(ScoringService.SALE_READY_MODULES)


class TestUnsupportedToolStillRefused:
    """Widening the guard to two programs must not widen it to everything."""

    @pytest.mark.parametrize("path", ["", "/insights", "/dashboard"])
    def test_guide_routes_reject_with_400(self, api, advisor, db_session, test_engagement, path):
        test_engagement.tool = UNSUPPORTED_TOOL
        db_session.flush()
        resp = api.as_user(advisor).get(f"{GUIDE}/{test_engagement.id}{path}")
        assert resp.status_code == 400

    def test_deliverables_reject_with_400(self, api, advisor, db_session, test_engagement):
        test_engagement.tool = UNSUPPORTED_TOOL
        db_session.flush()
        resp = api.as_user(advisor).get(f"{DELIVERABLES}/{test_engagement.id}")
        assert resp.status_code == 400


class TestSaleReadyAuthorizationUnchanged:
    """
    The same role boundary Value Builder has, re-asserted for Sale Ready.

    Generalising a tool check is exactly how an access rule gets widened by
    accident, so this does not assume the Value Builder suite covers it.
    """

    def test_owner_is_denied_the_guide(self, api, owner, sale_ready_engagement):
        assert api.as_user(owner).get(f"{GUIDE}/{sale_ready_engagement.id}").status_code == 403

    def test_owner_is_denied_insights(self, api, owner, sale_ready_engagement):
        assert api.as_user(owner).get(f"{GUIDE}/{sale_ready_engagement.id}/insights").status_code == 403

    def test_owner_is_denied_deliverables(self, api, owner, sale_ready_engagement):
        assert api.as_user(owner).get(f"{DELIVERABLES}/{sale_ready_engagement.id}").status_code == 403

    def test_owner_still_gets_the_dashboard(self, api, owner, sale_ready_engagement, sale_ready_cards):
        """The one Program Guide read an owner does get, unchanged."""
        assert api.as_user(owner).get(f"{GUIDE}/{sale_ready_engagement.id}/dashboard").status_code == 200

    def test_outsider_is_denied(self, api, outsider, sale_ready_engagement):
        assert api.as_user(outsider).get(f"{GUIDE}/{sale_ready_engagement.id}").status_code == 403

    def test_owner_cannot_reorder(self, api, owner, sale_ready_engagement):
        resp = api.as_user(owner).put(
            f"{GUIDE}/{sale_ready_engagement.id}/order",
            json={"module_order": ["M2"]},
        )
        assert resp.status_code == 403

    def test_unknown_engagement_is_404(self, api, advisor):
        assert api.as_user(advisor).get(f"{GUIDE}/{uuid.uuid4()}").status_code == 404


# ----------------------------------------------------------------------
# Deliverables, status and tasks
# ----------------------------------------------------------------------
class TestSaleReadyDeliverables:

    def test_preset_is_served_untouched(self, api, advisor, sale_ready_engagement, sale_ready_preset):
        body = api.as_user(advisor).get(f"{DELIVERABLES}/{sale_ready_engagement.id}").json()
        module = next(m for m in body["modules"] if m["module_code"] == "M1")

        assert body["program_type"] == PROGRAM_SALE_READY
        assert module["status"] == "not_started"
        item = module["deliverables"][0]
        assert item["deliverable_id"] == str(sale_ready_preset.id)
        assert item["source"] == "preset"
        assert item["is_in_scope"] is True
        assert item["is_complete"] is False

    def test_completing_the_only_mandatory_preset_completes_the_module(
        self, api, advisor, sale_ready_engagement, sale_ready_preset
    ):
        body = api.as_user(advisor).put(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items/{sale_ready_preset.id}/complete",
            json={"is_complete": True},
        ).json()

        module = next(m for m in body["modules"] if m["module_code"] == "M1")
        assert module["status"] == "completed"

    def test_commencing_moves_the_module_to_in_progress(
        self, api, advisor, sale_ready_engagement, sale_ready_preset
    ):
        body = api.as_user(advisor).post(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/modules/M1/commence"
        ).json()

        module = next(m for m in body["modules"] if m["module_code"] == "M1")
        assert module["is_commenced"] is True
        assert module["status"] == "in_progress"

    def test_scoping_out_is_not_deletion(
        self, api, advisor, sale_ready_engagement, sale_ready_preset
    ):
        body = api.as_user(advisor).put(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items/{sale_ready_preset.id}/scope",
            json={"is_in_scope": False},
        ).json()

        module = next(m for m in body["modules"] if m["module_code"] == "M1")
        item = module["deliverables"][0]
        assert item["is_in_scope"] is False
        assert item["is_complete"] is False

    def test_advisor_added_deliverable_round_trips(self, api, advisor, sale_ready_engagement):
        client = api.as_user(advisor)
        created = client.post(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items",
            json={"module_code": "M4", "title": "Advisor item", "is_mandatory": False},
        )
        assert created.status_code == 201

        module = next(m for m in created.json()["modules"] if m["module_code"] == "M4")
        item = module["deliverables"][0]
        assert item["source"] == "advisor"
        assert item["title"] == "Advisor item"

        removed = client.delete(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items/{item['deliverable_id']}"
        )
        assert removed.status_code == 200
        assert not any(m["module_code"] == "M4" for m in removed.json()["modules"])

    def test_preset_cannot_be_deleted(self, api, advisor, sale_ready_engagement, sale_ready_preset):
        """Presets are scoped out, never deleted - the rule is program-neutral."""
        resp = api.as_user(advisor).delete(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items/{sale_ready_preset.id}"
        )
        assert resp.status_code == 400


class TestSaleReadyTaskSync:

    def test_task_generation_and_two_way_sync(
        self, api, db_session, advisor, sale_ready_engagement, sale_ready_preset
    ):
        """
        The deliverable <-> task contract, unchanged for Sale Ready: generating
        is idempotent, and completing the deliverable closes its tasks.
        """
        from app.models.task import Task

        client = api.as_user(advisor)
        first = client.post(f"{DELIVERABLES}/{sale_ready_engagement.id}/modules/M1/tasks")
        assert first.status_code == 201
        assert first.json()["created_count"] == 1

        task = (
            db_session.query(Task)
            .filter(Task.source_deliverable_id == sale_ready_preset.id)
            .one()
        )
        assert task.task_type == "deliverable_generated"
        assert task.module_reference == "M1"
        assert task.priority == "high"  # mandatory preset

        # Idempotent: a second click creates nothing.
        again = client.post(f"{DELIVERABLES}/{sale_ready_engagement.id}/modules/M1/tasks")
        assert again.json()["created_count"] == 0

        # Completing the deliverable closes the task it generated.
        client.put(
            f"{DELIVERABLES}/{sale_ready_engagement.id}/items/{sale_ready_preset.id}/complete",
            json={"is_complete": True},
        )
        db_session.refresh(task)
        assert task.status == "completed"

    def test_closing_every_task_completes_the_deliverable(
        self, db_session, test_user, sale_ready_engagement, sale_ready_preset
    ):
        """The other direction, via the service the tasks API calls."""
        from app.services.program_deliverable_service import get_program_deliverable_service

        service = get_program_deliverable_service(db_session)
        created = service.generate_tasks_for_module(sale_ready_engagement, "M1", test_user.id)
        assert len(created) == 1

        # Still open: nothing should complete yet.
        assert service.complete_deliverable_if_tasks_done(
            sale_ready_engagement, sale_ready_preset.id, test_user.id
        ) is None

        created[0].status = "completed"
        db_session.flush()

        instance = service.complete_deliverable_if_tasks_done(
            sale_ready_engagement, sale_ready_preset.id, test_user.id
        )
        assert instance is not None and instance.is_complete is True

    def test_unsupported_tool_never_completes_a_deliverable(
        self, db_session, test_user, test_engagement, sale_ready_preset
    ):
        """The tool guard on the task->deliverable direction still holds."""
        from app.services.program_deliverable_service import get_program_deliverable_service

        test_engagement.tool = UNSUPPORTED_TOOL
        db_session.flush()

        assert get_program_deliverable_service(db_session).complete_deliverable_if_tasks_done(
            test_engagement, sale_ready_preset.id, test_user.id
        ) is None


# ----------------------------------------------------------------------
# Seeding isolation
# ----------------------------------------------------------------------
class TestSeedIsolation:

    def test_seeding_sale_ready_cannot_retire_value_builder(self, db_session, clean_library):
        """
        The safety property the whole single-fixture-per-program design rests
        on. Seeding Sale Ready must leave Value Builder content active, or a
        routine Sale Ready seed would silently retire a live program.
        """
        from scripts.seed_program_guide_content import _retire_missing_modules

        db_session.add_all([
            ProgramModuleContent(
                program_type=PROGRAM_VALUE_BUILDER,
                module_code="V1",
                display_order=1,
                title="Value Builder card",
                is_active=True,
            ),
            ProgramModuleContent(
                program_type=PROGRAM_SALE_READY,
                module_code="M1",
                display_order=1,
                title="Sale Ready card",
                is_active=True,
            ),
        ])
        db_session.flush()

        # A Sale Ready fixture that mentions M1 only.
        tally = _retire_missing_modules(
            db_session,
            [{"program_type": PROGRAM_SALE_READY, "module_code": "M1"}],
        )
        db_session.flush()

        assert tally["cards"] == 0
        vb = (
            db_session.query(ProgramModuleContent)
            .filter(
                ProgramModuleContent.program_type == PROGRAM_VALUE_BUILDER,
                ProgramModuleContent.module_code == "V1",
            )
            .one()
        )
        assert vb.is_active is True

    def test_sale_ready_fixture_is_structurally_valid(self):
        """
        The shipped structural fixture must pass the seed validator and match
        the scoring taxonomy, so the client's content drops into a file that
        already seeds cleanly.
        """
        import json
        import pathlib

        from scripts.seed_program_guide_content import validate_fixture

        path = (
            pathlib.Path(__file__).resolve().parents[1]
            / "files" / "program_guide" / "sale_ready_modules.json"
        )
        fixture = json.loads(path.read_text(encoding="utf-8"))

        validate_fixture(fixture)  # raises FixtureError if malformed

        assert {e["program_type"] for e in fixture} == {PROGRAM_SALE_READY}
        assert [e["module_code"] for e in fixture] == list(ScoringService.SALE_READY_MODULES)
        mismatches = [
            e["module_code"] for e in fixture
            if e["title"] != ScoringService.SALE_READY_MODULES[e["module_code"]]
        ]
        assert mismatches == []
