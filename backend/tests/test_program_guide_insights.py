"""
Tests for the per-module diagnostic insights read.

Two things this file is really about.

First, the gap it closes. compute_value_movement returns nothing at all below
two completed diagnostics, and most engagements have exactly one - so the scores
sitting in Diagnostic.module_scores were unreachable in the ordinary case. These
tests pin that a single diagnostic is enough.

Second, honesty about missing data. Roughly a third of the diagnostic is
conditional, so a module may go unscored on a perfectly complete diagnostic, and
the failure mode worth guarding against is one quietly reporting 0.0 or "Green"
when nothing was measured. Absent must stay absent - and it matters more now
that the score also decides the module's position in the program: a missing
score read as zero would rank an unmeasured module as the worst in the business.

Run with: pytest tests/test_program_guide_insights.py -v
"""
import uuid

import pytest

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
# The score is the reason for the position
# ----------------------------------------------------------------------
class TestScoreDrivesTheOrder:
    """
    The order is the diagnostic's, so these pin the ordering rule against the
    same payload an advisor reads on the module card. Previously the order came
    from BBA findings matched to modules by freeform text; the score needs no
    matching at all, which is the whole point of the change.
    """

    def test_the_worst_scoring_module_is_worked_first(self, api, advisor, test_engagement, make_diagnostic):
        make_diagnostic({"V1": (4.2, 9), "V5": (1.3, 9), "V6": (2.8, 9)})
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert _module(payload, "V5")["effective_rank"] == 1
        assert _module(payload, "V6")["effective_rank"] == 2
        assert _module(payload, "V1")["effective_rank"] == 3

    def test_unscored_modules_fall_after_every_scored_one(self, api, advisor, test_engagement, make_diagnostic):
        """
        A module the diagnostic never asked about must not be read as a zero and
        ranked first. It is unmeasured, not catastrophic.
        """
        make_diagnostic({"V11": (4.9, 9)})
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert _module(payload, "V11")["effective_rank"] == 1
        assert _module(payload, "V1")["score"] is None
        assert _module(payload, "V1")["effective_rank"] > 1

    def test_equal_scores_break_ties_by_taxonomy_order(self, api, advisor, test_engagement, make_diagnostic):
        """
        Diagnostic scores are averages over a handful of answers, so ties are
        common. Without a stable tiebreak two modules could swap places between
        requests and the guide would look like it reordered itself.
        """
        make_diagnostic({"V6": (3.0, 9), "V2": (3.0, 9)})
        client = api.as_user(advisor)
        first = client.get(_url(test_engagement.id)).json()
        second = client.get(_url(test_engagement.id)).json()

        assert _module(first, "V2")["effective_rank"] < _module(first, "V6")["effective_rank"]
        assert [m["effective_rank"] for m in first["modules"]] == [
            m["effective_rank"] for m in second["modules"]
        ]

    def test_no_diagnostic_leaves_the_default_order(self, api, advisor, test_engagement, cards):
        guide = api.as_user(advisor).get(f"/api/program-guide/engagements/{test_engagement.id}").json()

        assert guide["order_source"] == "default"
        assert guide["source_diagnostic_id"] is None

    def test_a_scored_diagnostic_is_named_as_the_source(self, api, advisor, test_engagement, cards, make_diagnostic):
        diagnostic = make_diagnostic({"V1": (2.0, 9)})
        guide = api.as_user(advisor).get(f"/api/program-guide/engagements/{test_engagement.id}").json()

        assert guide["order_source"] == "diagnostic"
        assert guide["source_diagnostic_id"] == str(diagnostic.id)

    def test_a_diagnostic_that_scored_nothing_reports_the_default_order(
        self, api, advisor, test_engagement, cards, make_diagnostic
    ):
        """
        Crediting an empty diagnostic with the sequence would tell an advisor
        the order was tailored to this client when it is the default taxonomy.
        """
        make_diagnostic({})
        guide = api.as_user(advisor).get(f"/api/program-guide/engagements/{test_engagement.id}").json()

        assert guide["order_source"] == "default"
        assert guide["source_diagnostic_id"] is None


class TestMissingDataStaysMissing:

    def test_scores_present(self, api, advisor, test_engagement, make_diagnostic):
        make_diagnostic({"V1": (2.6, 7)})

        assert api.as_user(advisor).get(_url(test_engagement.id)).json()["has_scores"] is True

    def test_no_diagnostic_still_returns_every_module(self, api, advisor, test_engagement):
        payload = api.as_user(advisor).get(_url(test_engagement.id)).json()

        assert len(payload["modules"]) == 11
        assert payload["has_scores"] is False
        assert all(m["score"] is None for m in payload["modules"])


# ----------------------------------------------------------------------
# Rank agrees with the guide
# ----------------------------------------------------------------------
class TestRankMatchesTheGuide:

    def test_effective_rank_matches_the_program_guide(self, api, advisor, test_engagement, cards, make_diagnostic):
        """
        The insights panel prints "Rank N of 11" beside the module the guide
        also positions. Two orderings from two code paths would be visible to a
        client, so they are pinned to each other rather than each to a literal.
        """
        make_diagnostic({"V5": (1.9, 9), "V6": (2.4, 9), "V1": (4.1, 9)})
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
