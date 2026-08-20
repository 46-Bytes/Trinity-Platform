"""
Role boundary tests for the Program Guide API.

Part A's roles matrix gives a business owner the program dashboard and No to
everything else - open a module, module card contents, diagnostic findings. All
three of those were readable by any client with engagement access before these
tests existed, and the module card library was readable by any authenticated
user at all.

The dashboard is the one read owners keep, so the assertions that matter most
here are the ones checking WHAT it returns, not just who may call it: a schema
that grew a content field, or one refactored to inherit from
ProgramModuleContentItem, would hand an owner exactly what Part A withholds.

Run with: pytest tests/test_program_guide_api.py -v
"""
import uuid

import pytest

from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.program_guide import ProgramModuleContent
from app.models.user import UserRole
from app.schemas.program_guide import DashboardModuleItem, ProgramModuleContentItem

BASE = "/api/program-guide/engagements"
CONTENT = "/api/program-guide/content"

# Everything the advisor's card carries that the owner's dashboard does not.
#
# Derived rather than hand-listed on purpose. A hand-written set silently stops
# covering each new card section as the spec's parts land - which is exactly
# when this test matters most. Subtracting the two schemas means any field added
# to the card is treated as forbidden on the dashboard until someone
# deliberately adds it to DashboardModuleItem too.
CONTENT_FIELDS = set(ProgramModuleContentItem.model_fields) - set(DashboardModuleItem.model_fields)


@pytest.fixture
def advisor(db_session, test_engagement, make_user):
    user = make_user(UserRole.ADVISOR)
    test_engagement.primary_advisor_id = user.id
    db_session.flush()
    return user


@pytest.fixture
def owner(db_session, test_engagement, make_user):
    """A client on the engagement - Part A's business owner."""
    user = make_user(UserRole.CLIENT)
    test_engagement.client_ids = [user.id]
    db_session.flush()
    return user


@pytest.fixture
def admin(make_user):
    return make_user(UserRole.ADMIN)


@pytest.fixture
def outsider(make_user):
    return make_user(UserRole.ADVISOR)


@pytest.fixture
def module(db_session, test_engagement):
    """One card with content, and one mandatory preset so status is derivable."""
    card = ProgramModuleContent(
        program_type="value_builder",
        module_code="V1",
        display_order=1,
        title="Financial Management",
        purpose="Build the financial foundation",
        preparation_checklist=[{"key": "load", "text": "Load financials"}],
        recommended_tools=[{"tool_key": "bba", "label": "Report Builder"}],
        required_inputs=[{"key": "V1-I1", "label": "Accounts", "source": "Advisor to upload"}],
        deliverables=["Financial Health Summary"],
        # The advisor-only sections. Present here so the by-value leak
        # assertions have something real to fail on.
        sessions=[{
            "key": "V1-S1",
            "title": "Financial Workshop",
            "agenda": [{
                "key": "V1-S1-A3",
                "title": "Expenses review",
                "questions": ["Walk me through your three biggest expense lines."],
            }],
        }],
        guardrails={"must_not": ["redo bookkeeping or rebuild the accounts"]},
    )
    preset = ProgramModuleDeliverable(
        program_type="value_builder",
        module_code="V1",
        deliverable_key=f"key-{uuid.uuid4()}",
        title="Financial Health Summary",
        is_mandatory=True,
        display_order=1,
    )
    db_session.add_all([card, preset])
    db_session.flush()
    return {"card": card, "preset": preset}


# ----------------------------------------------------------------------
# The three endpoints that leaked
# ----------------------------------------------------------------------
class TestOwnerIsDeniedCardContents:
    """Part A: Open a module - No. Module card contents - No."""

    def test_owner_cannot_read_the_guide(self, api, owner, test_engagement, module):
        assert api.as_user(owner).get(f"{BASE}/{test_engagement.id}").status_code == 403

    def test_advisor_can_read_the_guide(self, api, advisor, test_engagement, module):
        assert api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").status_code == 200

    def test_admin_can_read_the_guide(self, api, admin, test_engagement, module):
        assert api.as_user(admin).get(f"{BASE}/{test_engagement.id}").status_code == 200

    def test_outsider_cannot_read_the_guide(self, api, outsider, test_engagement, module):
        assert api.as_user(outsider).get(f"{BASE}/{test_engagement.id}").status_code == 403


class TestOwnerIsDeniedDiagnosticFindings:
    """Part A: Diagnostic findings - No. Value movement is per-module score and RAG."""

    def test_owner_cannot_read_value_movement(self, api, owner, test_engagement):
        assert api.as_user(owner).get(f"{BASE}/{test_engagement.id}/value-movement").status_code == 403

    def test_advisor_can_read_value_movement(self, api, advisor, test_engagement):
        assert api.as_user(advisor).get(f"{BASE}/{test_engagement.id}/value-movement").status_code == 200


class TestModuleCardLibrary:
    """
    /content is not engagement-scoped, so it had no authorization at all - any
    authenticated user could pull the whole library for any program type.
    """

    def test_owner_is_denied(self, api, owner, module):
        assert api.as_user(owner).get(f"{CONTENT}?program_type=value_builder").status_code == 403

    def test_advisor_is_allowed(self, api, advisor, module):
        assert api.as_user(advisor).get(f"{CONTENT}?program_type=value_builder").status_code == 200

    def test_admin_is_allowed(self, api, admin, module):
        assert api.as_user(admin).get(f"{CONTENT}?program_type=value_builder").status_code == 200


# ----------------------------------------------------------------------
# The dashboard - the one read owners keep
# ----------------------------------------------------------------------
class TestDashboardAccess:

    @pytest.mark.parametrize("role_fixture", ["owner", "advisor", "admin"])
    def test_everyone_with_access_can_read_it(self, api, request, test_engagement, module, role_fixture):
        user = request.getfixturevalue(role_fixture)
        resp = api.as_user(user).get(f"{BASE}/{test_engagement.id}/dashboard")
        assert resp.status_code == 200, resp.text

    def test_outsider_is_still_denied(self, api, outsider, test_engagement, module):
        assert api.as_user(outsider).get(f"{BASE}/{test_engagement.id}/dashboard").status_code == 403

    def test_unknown_engagement_is_404(self, api, owner):
        assert api.as_user(owner).get(f"{BASE}/{uuid.uuid4()}/dashboard").status_code == 404


class TestDashboardLeaksNoContent:
    """
    The assertions that actually protect the owner. A schema change that adds a
    content field, or a refactor making DashboardModuleItem inherit from
    ProgramModuleContentItem, fails here.
    """

    def test_the_forbidden_set_is_not_empty(self):
        """
        CONTENT_FIELDS is derived, so a refactor collapsing the two schemas
        would empty it and quietly turn the leak tests below into no-ops.
        """
        assert CONTENT_FIELDS, "the card and dashboard schemas no longer differ"

    def test_no_module_carries_a_content_field(self, api, owner, test_engagement, module):
        body = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").json()

        assert body["modules"], "nothing was asserted - the module list was empty"
        for item in body["modules"]:
            leaked = CONTENT_FIELDS & set(item)
            assert not leaked, f"dashboard exposed card content: {sorted(leaked)}"

    def test_the_authored_content_is_absent_by_value_too(self, api, owner, test_engagement, module):
        """
        Belt and braces. Field names could be renamed on the way out; the
        authored text itself must not appear anywhere in the payload.
        """
        raw = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").text
        assert "Build the financial foundation" not in raw
        assert "Load financials" not in raw
        assert "Walk me through your three biggest expense lines" not in raw
        assert "redo bookkeeping" not in raw

    def test_it_still_carries_what_the_owner_needs(self, api, owner, test_engagement, module):
        body = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").json()
        item = next(m for m in body["modules"] if m["module_code"] == "V1")

        assert item["title"] == "Financial Management"
        assert item["status"] == "not_started"
        assert body["total_modules"] == len(body["modules"])


class TestDashboardProgress:

    def test_progress_tracks_completion(self, api, owner, advisor, test_engagement, module):
        """Status is derived from the deliverables engine, not stored twice."""
        before = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").json()
        assert before["completed_modules"] == 0
        assert before["not_started_modules"] == before["total_modules"]

        api.as_user(advisor).put(
            f"/api/deliverables/engagements/{test_engagement.id}/items/{module['preset'].id}/complete",
            json={"is_complete": True},
        )

        after = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").json()
        assert after["completed_modules"] == 1
        assert next(m for m in after["modules"] if m["module_code"] == "V1")["status"] == "completed"

    def test_counts_add_up(self, api, owner, test_engagement, module):
        body = api.as_user(owner).get(f"{BASE}/{test_engagement.id}/dashboard").json()
        assert (
            body["completed_modules"] + body["in_progress_modules"] + body["not_started_modules"]
            == body["total_modules"]
        )


@pytest.fixture
def second_module(db_session):
    """
    A second card, so ordering has something to reorder.

    The guide view only lists modules that actually have a content row, so a
    reorder naming a code with no card would move nothing and assert nothing.
    """
    card = ProgramModuleContent(
        program_type="value_builder",
        module_code="V11",
        display_order=11,
        title="Risk, Legal, Compliance & Property",
        purpose="Register the exposures the business carries",
    )
    db_session.add(card)
    db_session.flush()
    return card


class TestModuleOrdering:
    """
    The reorder endpoints, which had no coverage at all and were both broken.

    Each declares response_model=ProgramGuideView but returned the service's
    order dict ({source, order, bba_id, ...}), so FastAPI's response validation
    raised and every call 500'd. The frontend has shipped the reorder buttons
    since ModuleReorderControls landed, which is how a feature can be visibly
    present and entirely non-functional at the same time.
    """

    def test_reorder_returns_the_guide_view(self, api, advisor, test_engagement, module, second_module):
        resp = api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/order",
            json={"module_order": ["V11", "V1"]},
        )
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["order_source"] == "custom"
        assert "modules" in body

    def test_reorder_moves_the_module(self, api, advisor, test_engagement, module, second_module):
        body = api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/order",
            json={"module_order": ["V11", "V1"]},
        ).json()

        ranks = {m["module_code"]: m["effective_rank"] for m in body["modules"]}
        assert ranks["V11"] == 1
        assert ranks["V1"] == 2

    def test_a_partial_order_keeps_every_module(self, api, advisor, test_engagement, module, second_module):
        """
        The order may be partial; unnamed modules are appended rather than
        dropped, so the guide is never gated.
        """
        body = api.as_user(advisor).put(
            f"{BASE}/{test_engagement.id}/order",
            json={"module_order": ["V11"]},
        ).json()

        assert body["modules"][0]["module_code"] == "V11"
        assert len(body["modules"]) == len(
            api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").json()["modules"]
        )

    def test_reset_returns_the_guide_view(self, api, advisor, test_engagement, module, second_module):
        client = api.as_user(advisor)
        client.put(f"{BASE}/{test_engagement.id}/order", json={"module_order": ["V11", "V1"]})

        resp = client.post(f"{BASE}/{test_engagement.id}/order/reset")
        assert resp.status_code == 200, resp.text
        assert resp.json()["order_source"] != "custom"

    def test_reset_restores_the_recommended_order(self, api, advisor, test_engagement, module, second_module):
        client = api.as_user(advisor)
        before = client.get(f"{BASE}/{test_engagement.id}").json()
        client.put(f"{BASE}/{test_engagement.id}/order", json={"module_order": ["V11", "V1"]})
        after = client.post(f"{BASE}/{test_engagement.id}/order/reset").json()

        assert [m["module_code"] for m in after["modules"]] == [
            m["module_code"] for m in before["modules"]
        ]

    def test_owner_cannot_reorder(self, api, owner, test_engagement, module, second_module):
        assert api.as_user(owner).put(
            f"{BASE}/{test_engagement.id}/order",
            json={"module_order": ["V11", "V1"]},
        ).status_code == 403

    def test_owner_cannot_reset(self, api, owner, test_engagement, module, second_module):
        assert api.as_user(owner).post(f"{BASE}/{test_engagement.id}/order/reset").status_code == 403

    def test_outsider_cannot_reorder(self, api, outsider, test_engagement, module, second_module):
        assert api.as_user(outsider).put(
            f"{BASE}/{test_engagement.id}/order",
            json={"module_order": ["V11", "V1"]},
        ).status_code == 403
