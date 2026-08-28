"""
Tests for the per-module diagnostic insights read.

Two things this file is really about.

First, the gap it closes. compute_value_movement returns nothing at all below
two completed diagnostics, and most engagements have exactly one - so the scores
sitting in Diagnostic.module_scores were unreachable in the ordinary case. These
tests pin that a single diagnostic is enough.

Second, honesty about missing data. Scores and findings come from two unrelated
sources, either of which may be absent, and the failure mode worth guarding
against is a module quietly reporting 0.0 or "Green" when nothing was measured.
Absent must stay absent.

Run with: pytest tests/test_program_guide_insights.py -v
"""
import uuid

import pytest

from app.models.bba import BBA
from app.models.diagnostic import Diagnostic
from app.models.program_guide import ProgramModuleContent
from app.models.user import UserRole
from app.services.scoring_service import ScoringService


def _url(engagement_id):
    return f"/api/program-guide/engagements/{engagement_id}/insights"


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
def make_diagnostic(db_session, test_engagement, test_user):
    """A completed diagnostic carrying whatever module scores the test needs."""
    def _make(scores, overall=None, status="completed"):
        diagnostic = Diagnostic(
            engagement_id=test_engagement.id,
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


@pytest.fixture
def cards(db_session):
    """
    Content rows for the modules the ranking tests compare against.

    The guide view only lists modules that actually have a card, so without
    these the comparison below would run over an empty list and pass vacuously.
    """
    rows = [
        ProgramModuleContent(
            program_type="value_builder",
            module_code=code,
            display_order=order,
            title=ScoringService.VALUE_BUILDER_MODULES[code],
        )
        for order, code in enumerate(["V1", "V5", "V6", "V11"], start=1)
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


@pytest.fixture
def make_bba(db_session, test_engagement, test_user):
    def _make(findings):
        bba = BBA(
            engagement_id=test_engagement.id,
            created_by_user_id=test_user.id,
            draft_findings={"findings": findings},
        )
        db_session.add(bba)
        db_session.flush()
        return bba
    return _make


def _module(payload, code):
    return next(m for m in payload["modules"] if m["module_code"] == code)


# ----------------------------------------------------------------------
# Role boundary
# ----------------------------------------------------------------------
class TestInsightsAccess:

    def test_advisor_can_read(self, api, advisor, test_engagement):
        assert api.as_user(advisor).get(_url(test_engagement.id)).status_code == 200

    def test_owner_is_denied(self, api, owner, test_engagement):
        """
        Part A puts per-module scores and diagnostic findings in the owner's No
        column. Same reason value-movement is advisor-only.
        """
        assert api.as_user(owner).get(_url(test_engagement.id)).status_code == 403

    def test_outsider_is_denied(self, api, outsider, test_engagement):
        assert api.as_user(outsider).get(_url(test_engagement.id)).status_code == 403

    def test_unknown_engagement_is_404(self, api, advisor):
        assert api.as_user(advisor).get(_url(uuid.uuid4())).status_code == 404

    def test_non_value_builder_is_rejected(self, api, advisor, db_session, test_engagement):
        test_engagement.tool = "sale_ready"
        db_session.flush()
        assert api.as_user(advisor).get(_url(test_engagement.id)).status_code == 400


# ----------------------------------------------------------------------
# Scores
# ----------------------------------------------------------------------
class TestScores:

    def test_a_single_diagnostic_is_enough(self, api, advisor, test_engagement, make_diagnostic):
        """
        The whole reason this route exists. value-movement needs two completed
        diagnostics and returns nothing below that; this one answers from one.
        """
        make_diagnostic({"V1": (2.6, 7)}, overall=2.9)
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert payload["has_scores"] is True
        assert payload["overall_score"] == 2.9
        assert _module(payload, "V1")["score"] == 2.6

    def test_rag_and_severity_are_derived(self, api, advisor, test_engagement, make_diagnostic):
        make_diagnostic({"V1": (2.6, 7), "V2": (1.4, 3), "V3": (4.6, 4)})
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert (_module(payload, "V1")["rag"], _module(payload, "V1")["severity"]) == ("Amber", "High")
        assert (_module(payload, "V2")["rag"], _module(payload, "V2")["severity"]) == ("Red", "Critical")
        assert (_module(payload, "V3")["rag"], _module(payload, "V3")["severity"]) == ("Green", "Strong")

    def test_answered_question_count_is_carried(self, api, advisor, test_engagement, make_diagnostic):
        """
        A module scored on three answers is not comparable to one scored on
        eighteen. The count travels so the UI can say so.
        """
        make_diagnostic({"V2": (1.4, 3)})
        assert _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V2")["answered_questions"] == 3

    def test_every_module_is_present_even_when_unscored(self, api, advisor, test_engagement, make_diagnostic):
        """
        All eleven, always. A caller must never have to guess whether a module
        was omitted or simply has nothing yet.
        """
        make_diagnostic({"V1": (2.6, 7)})
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert [m["module_code"] for m in payload["modules"]] == list(ScoringService.VALUE_BUILDER_MODULES)

    def test_an_unscored_module_reports_null_not_zero(self, api, advisor, test_engagement, make_diagnostic):
        """
        The failure worth guarding: 0.0 renders as a real score and Red renders
        as a real finding. Unmeasured must stay visibly unmeasured.
        """
        make_diagnostic({"V1": (2.6, 7)})
        v5 = _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V5")

        assert v5["score"] is None
        assert v5["rag"] is None
        assert v5["severity"] is None

    def test_no_diagnostic_means_no_scores(self, api, advisor, test_engagement):
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert payload["has_scores"] is False
        assert payload["diagnostic_id"] is None
        assert all(m["score"] is None for m in payload["modules"])

    def test_an_incomplete_diagnostic_is_ignored(self, api, advisor, test_engagement, make_diagnostic):
        make_diagnostic({"V1": (2.6, 7)}, status="in_progress")
        assert api.as_user(advisor).get(_url(test_engagement.id)).json()["has_scores"] is False

    def test_the_latest_completed_diagnostic_wins(self, api, advisor, db_session, test_engagement, make_diagnostic):
        from datetime import datetime, timedelta

        older = make_diagnostic({"V1": (1.0, 7)})
        newer = make_diagnostic({"V1": (3.8, 7)})
        older.completed_at = datetime(2026, 1, 1)
        newer.completed_at = datetime(2026, 1, 1) + timedelta(days=30)
        db_session.flush()

        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()
        assert _module(payload, "V1")["score"] == 3.8
        assert payload["diagnostic_id"] == str(newer.id)


# ----------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------
class TestFindings:

    def test_findings_are_attributed_to_their_module(self, api, advisor, test_engagement, make_bba):
        make_bba([
            {"rank": 1, "title": "No cash flow forecast", "summary": "Reports twice a year",
             "priority_area": "Financial Management", "impact": "high", "urgency": "immediate"},
        ])
        finding = _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V1")["findings"][0]

        assert finding["title"] == "No cash flow forecast"
        assert finding["impact"] == "high"

    def test_the_raw_priority_area_is_carried_through(self, api, advisor, test_engagement, make_bba):
        """
        Matching is documented as fragile across renames. A finding that reads
        wrong on a module is the only signal it mismatched, so the text it was
        matched on has to be visible.
        """
        make_bba([{"rank": 1, "title": "Finding", "priority_area": "Financial Management"}])
        finding = _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V1")["findings"][0]

        assert finding["priority_area"] == "Financial Management"

    def test_findings_are_ordered_by_rank(self, api, advisor, test_engagement, make_bba):
        make_bba([
            {"rank": 4, "title": "Second", "priority_area": "Financial Management"},
            {"rank": 2, "title": "First", "priority_area": "Financial Management"},
        ])
        titles = [f["title"] for f in _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V1")["findings"]]

        assert titles == ["First", "Second"]

    def test_a_retired_module_name_still_matches(self, api, advisor, test_engagement, make_bba):
        """
        BBA findings are freeform text and old rows keep the old wording.
        MODULE_NAME_ALIASES rescues V8, whose rename replaced a word rather than
        widening one - the case the loose contains fallback cannot catch.
        """
        make_bba([{"rank": 1, "title": "No trademark", "priority_area": "Brand, IP & Competitive Advantage"}])
        assert _module(api.as_user(advisor).get(_url(test_engagement.id)).json(), "V8")["findings"][0]["title"] == "No trademark"

    def test_unmatched_findings_are_surfaced_not_dropped(self, api, advisor, test_engagement, make_bba):
        """
        A finding matching nothing is the visible symptom of a module order that
        has quietly degraded to the default taxonomy. Dropping it hides exactly
        the thing an advisor needs to see.
        """
        make_bba([{"rank": 1, "title": "Something else", "priority_area": "Wholly Unmappable Area"}])
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert [f["title"] for f in payload["unmatched_findings"]] == ["Something else"]
        assert all(m["findings"] == [] for m in payload["modules"])

    def test_no_bba_means_no_findings(self, api, advisor, test_engagement):
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert payload["has_findings"] is False
        assert payload["source_bba_id"] is None
        assert all(m["findings"] == [] for m in payload["modules"])


# ----------------------------------------------------------------------
# The two sources are independent
# ----------------------------------------------------------------------
class TestSourcesAreIndependent:

    def test_scores_without_findings(self, api, advisor, test_engagement, make_diagnostic):
        make_diagnostic({"V1": (2.6, 7)})
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert (payload["has_scores"], payload["has_findings"]) == (True, False)

    def test_findings_without_scores(self, api, advisor, test_engagement, make_bba):
        make_bba([{"rank": 1, "title": "Finding", "priority_area": "Financial Management"}])
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert (payload["has_scores"], payload["has_findings"]) == (False, True)
        assert _module(payload, "V1")["score"] is None

    def test_neither_still_returns_every_module(self, api, advisor, test_engagement):
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert len(payload["modules"]) == 11
        assert (payload["has_scores"], payload["has_findings"]) == (False, False)


# ----------------------------------------------------------------------
# Rank agrees with the guide
# ----------------------------------------------------------------------
class TestRankMatchesTheGuide:

    def test_effective_rank_matches_the_program_guide(self, api, advisor, test_engagement, cards, make_bba):
        """
        The insights panel prints "Rank N of 11" beside the module the guide
        also positions. Two orderings from two code paths would be visible to a
        client, so they are pinned to each other rather than each to a literal.
        """
        make_bba([
            {"rank": 1, "title": "A", "priority_area": "Systems & Processes"},
            {"rank": 2, "title": "B", "priority_area": "Technology"},
        ])
        client = api.as_user(advisor)
        insights = client.get(_url(test_engagement.id)).json()
        guide = client.get(f"/api/program-guide/engagements/{test_engagement.id}").json()

        guide_ranks = {m["module_code"]: m["effective_rank"] for m in guide["modules"]}
        assert guide_ranks, "no cards in the guide - the comparison below would be vacuous"

        compared = 0
        for module in insights["modules"]:
            if module["module_code"] in guide_ranks:
                assert module["effective_rank"] == guide_ranks[module["module_code"]]
                compared += 1
        assert compared == len(guide_ranks)

    def test_rank_reflects_a_custom_order(self, api, advisor, test_engagement, cards):
        client = api.as_user(advisor)
        client.put(
            f"/api/program-guide/engagements/{test_engagement.id}/order",
            json={"module_order": ["V11", "V1"]},
        )
        payload = client.get(_url(test_engagement.id)).json()

        assert _module(payload, "V11")["effective_rank"] == 1
        assert _module(payload, "V1")["effective_rank"] == 2
