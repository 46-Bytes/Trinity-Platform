"""
Sale Ready rules (app/services/sale_ready_rules.py) and the pinned-order helpers.

Pure: no database, no fixtures from conftest. Each rule is asserted against the
brief's wording, and each open client decision against SaleReadyPolicy's
default, so an answer from the client shows up here as a changed expectation.
"""
import pytest

from app.services.program_guide_service import apply_pinned_last, validate_pinned_order
from app.services.program_registry import (
    PROGRAM_SALE_READY,
    PROGRAM_VALUE_BUILDER,
    pinned_last_modules,
)
from app.services.sale_ready_rules import (
    DD_STATUS_IN_PROGRESS,
    DD_STATUS_NO,
    DD_STATUS_NOT_APPLICABLE,
    DD_STATUS_YES,
    GAP_DISCLOSE,
    GAP_FIX,
    GAP_REFER,
    SECTION_CLIENT_SPECIFIC,
    SECTION_MUST_DO,
    TASK_STATE_BLOCKED,
    TASK_STATE_NOT_APPLICABLE,
    SECTION_OPTIONAL,
    STAGE_STATE_COMPLETED,
    STAGE_STATE_NOT_STARTED,
    STAGE_STATE_STARTED,
    STAGE_STATUS_COMPLETED,
    STAGE_STATUS_IN_PROGRESS,
    STAGE_STATUS_NOT_STARTED,
    STAGE_TYPE_MODULE,
    STAGE_TYPE_POST_MODULE,
    STAGE_TYPE_PRE_MODULE,
    SaleReadyPolicy,
    StageProgress,
    TaskSnapshot,
    derive_stage_status,
    effective_gap_handling,
    has_activity,
    is_task_resolved,
    program_progress,
    qa_check,
    summarise_gaps,
    validate_dd_status,
    validate_gap_handling,
    validate_stage_state,
    validate_task_state,
)


def must(status="pending", state=None):
    return TaskSnapshot(SECTION_MUST_DO, status, state)


def optional(status="pending"):
    return TaskSnapshot(SECTION_OPTIONAL, status)


# ----------------------------------------------------------------------
# Stage status
# ----------------------------------------------------------------------
class TestDeriveStageStatus:

    def test_untouched_stage_is_not_started(self):
        assert derive_stage_status(STAGE_STATE_NOT_STARTED, [must(), must()], [None, None]) == STAGE_STATUS_NOT_STARTED

    def test_having_tasks_is_not_starting(self):
        """Phase tasks exist from engagement creation; that alone must not start the phase."""
        assert derive_stage_status(STAGE_STATE_NOT_STARTED, [must()] * 6, []) == STAGE_STATUS_NOT_STARTED

    def test_advisor_start_moves_to_in_progress(self):
        assert derive_stage_status(STAGE_STATE_STARTED, [], []) == STAGE_STATUS_IN_PROGRESS

    @pytest.mark.parametrize("status", ["completed", "in_progress", "cancelled"])
    def test_a_ticked_task_moves_to_in_progress(self, status):
        assert derive_stage_status(STAGE_STATE_NOT_STARTED, [must(), optional(status)], []) == STAGE_STATUS_IN_PROGRESS

    def test_a_dd_status_moves_to_in_progress(self):
        assert derive_stage_status(STAGE_STATE_NOT_STARTED, [], [None, DD_STATUS_NO]) == STAGE_STATUS_IN_PROGRESS

    def test_complete_only_when_the_advisor_marks_it(self):
        """Every task done is still In progress until the advisor marks it complete."""
        tasks = [must("completed"), must("completed")]
        assert derive_stage_status(STAGE_STATE_STARTED, tasks, [DD_STATUS_YES]) == STAGE_STATUS_IN_PROGRESS
        assert derive_stage_status(STAGE_STATE_COMPLETED, tasks, [DD_STATUS_YES]) == STAGE_STATUS_COMPLETED

    def test_unknown_state_is_refused(self):
        with pytest.raises(ValueError):
            validate_stage_state("done")


# ----------------------------------------------------------------------
# QA gate
# ----------------------------------------------------------------------
class TestQACheck:

    def test_passes_when_must_do_done_and_every_dd_has_a_status(self):
        result = qa_check([must("completed"), optional()], [DD_STATUS_YES, DD_STATUS_NO])
        assert result.passed and result.reasons == []

    def test_open_must_do_blocks(self):
        result = qa_check([must("completed"), must(), must("in_progress")], [])
        assert not result.passed
        assert result.open_must_do == 2
        assert result.reasons == ["2 must-do tasks still open"]

    def test_optional_and_client_specific_never_block(self):
        tasks = [optional(), TaskSnapshot(SECTION_CLIENT_SPECIFIC, "pending")]
        assert qa_check(tasks, []).passed

    def test_blank_dd_status_blocks(self):
        result = qa_check([], [DD_STATUS_YES, None, None])
        assert not result.passed
        assert result.dd_without_status == 2
        assert result.reasons == ["2 DD items with no status"]

    def test_both_reasons_are_reported(self):
        result = qa_check([must()], [None])
        assert result.reasons == ["1 must-do task still open", "1 DD item with no status"]

    def test_stage_with_nothing_passes(self):
        """Sale Planner and Close-out may have no tasks or DD items."""
        assert qa_check([], []).passed

    # --- open decisions: defaults follow the brief, policy can change them ---

    def test_default_in_progress_dd_satisfies_the_gate(self):
        """C14: the brief blocks only items with *no* status."""
        assert qa_check([], [DD_STATUS_IN_PROGRESS]).passed

    def test_policy_can_require_a_final_dd_status(self):
        strict = SaleReadyPolicy(qa_accepted_dd_statuses=frozenset({DD_STATUS_YES, DD_STATUS_NO, DD_STATUS_NOT_APPLICABLE}))
        assert not qa_check([], [DD_STATUS_IN_PROGRESS], strict).passed

    def test_default_cancelled_must_do_does_not_count_as_resolved(self):
        """C7: until a 'not applicable' task status is agreed, only completed resolves a must-do."""
        assert not qa_check([must("cancelled")], []).passed

    def test_policy_can_add_a_resolved_status(self):
        widened = SaleReadyPolicy(resolved_task_statuses=frozenset({"completed", "not_applicable"}))
        assert qa_check([must("not_applicable")], [], widened).passed


# ----------------------------------------------------------------------
# DD items and gaps
# ----------------------------------------------------------------------
class TestDDRules:

    @pytest.mark.parametrize("status", [None, DD_STATUS_YES, DD_STATUS_IN_PROGRESS, DD_STATUS_NO, DD_STATUS_NOT_APPLICABLE])
    def test_valid_statuses(self, status):
        assert validate_dd_status(status) == status

    @pytest.mark.parametrize("status", ["done", "Yes", "", "complete"])
    def test_invalid_statuses(self, status):
        with pytest.raises(ValueError):
            validate_dd_status(status)

    @pytest.mark.parametrize("gap", [GAP_FIX, GAP_DISCLOSE, GAP_REFER])
    def test_gap_handling_on_a_no(self, gap):
        assert validate_gap_handling(DD_STATUS_NO, gap) == gap

    @pytest.mark.parametrize("status", [None, DD_STATUS_YES, DD_STATUS_IN_PROGRESS, DD_STATUS_NOT_APPLICABLE])
    def test_gap_handling_refused_unless_no(self, status):
        with pytest.raises(ValueError, match="marked No"):
            validate_gap_handling(status, GAP_FIX)

    def test_clearing_gap_handling_is_always_allowed(self):
        assert validate_gap_handling(DD_STATUS_YES, None) is None

    def test_unknown_gap_handling_refused(self):
        with pytest.raises(ValueError):
            validate_gap_handling(DD_STATUS_NO, "ignore")

    def test_stored_handling_counts_only_while_no(self):
        assert effective_gap_handling(DD_STATUS_NO, GAP_REFER) == GAP_REFER
        assert effective_gap_handling(DD_STATUS_IN_PROGRESS, GAP_REFER) is None

    def test_gap_summary(self):
        summary = summarise_gaps([
            (DD_STATUS_NO, GAP_FIX), (DD_STATUS_NO, GAP_REFER), (DD_STATUS_NO, GAP_REFER),
            (DD_STATUS_NO, None), (DD_STATUS_YES, GAP_FIX), (None, None),
        ])
        assert summary == (4, 1, 0, 2, 1)


# ----------------------------------------------------------------------
# Progress
# ----------------------------------------------------------------------
class TestProgramProgress:

    def test_counts_match_the_mockup_card(self):
        stages = [
            StageProgress(STAGE_TYPE_PRE_MODULE, STAGE_STATUS_COMPLETED, 6, 6, 0, 0),
            StageProgress(STAGE_TYPE_PRE_MODULE, STAGE_STATUS_IN_PROGRESS, 8, 2, 8, 8),
            StageProgress(STAGE_TYPE_MODULE, STAGE_STATUS_COMPLETED, 10, 10, 21, 20),
            StageProgress(STAGE_TYPE_MODULE, STAGE_STATUS_NOT_STARTED, 10, 0, 74, 0),
            StageProgress(STAGE_TYPE_POST_MODULE, STAGE_STATUS_NOT_STARTED, 0, 0, 10, 0),
        ]
        p = program_progress(stages)
        assert (p.phases_completed, p.phases_total) == (1, 2)
        assert (p.modules_completed, p.modules_total) == (1, 2)
        assert (p.must_do_resolved, p.must_do_total) == (18, 34)
        assert (p.dd_yes, p.dd_total) == (28, 113)
        assert p.percent == 53

    def test_post_module_stages_are_not_counted_as_phases(self):
        p = program_progress([StageProgress(STAGE_TYPE_POST_MODULE, STAGE_STATUS_COMPLETED, 0, 0, 0, 0)])
        assert p.phases_total == 0

    def test_empty_program_is_zero_percent(self):
        assert program_progress([]).percent == 0


# ----------------------------------------------------------------------
# Pinned order
# ----------------------------------------------------------------------
class TestPinnedOrder:

    def test_registry(self):
        assert pinned_last_modules(PROGRAM_SALE_READY) == ("M8",)
        assert pinned_last_modules(PROGRAM_VALUE_BUILDER) == ()
        assert pinned_last_modules(None) == ()

    def test_apply_moves_pinned_to_the_end(self):
        assert apply_pinned_last(["M8", "M2", "M1"], ("M8",)) == ["M2", "M1", "M8"]

    def test_apply_ignores_a_pinned_code_not_in_the_order(self):
        assert apply_pinned_last(["M2", "M1"], ("M8",)) == ["M2", "M1"]

    def test_apply_with_nothing_pinned_is_identity(self):
        assert apply_pinned_last(["V3", "V1"], ()) == ["V3", "V1"]

    @pytest.mark.parametrize("order", [[], ["M2", "M1"], ["M2", "M1", "M8"], ["M8"]])
    def test_valid_orders(self, order):
        validate_pinned_order(order, ("M8",))

    @pytest.mark.parametrize("order", [["M8", "M1"], ["M1", "M8", "M2"]])
    def test_pinned_before_unpinned_is_refused(self, order):
        with pytest.raises(ValueError, match="pinned last"):
            validate_pinned_order(order, ("M8",))


# ----------------------------------------------------------------------
# Sale Ready task states (C7: N/A and blocked, never global statuses)
# ----------------------------------------------------------------------
class TestTaskStates:

    def test_done_or_not_required_is_resolved(self):
        assert is_task_resolved(must("completed")) is True
        assert is_task_resolved(must("pending", TASK_STATE_NOT_APPLICABLE)) is True

    def test_blocked_is_open(self):
        """Blocked names a reason the work has not happened; it must not pass QA."""
        assert is_task_resolved(must("pending", TASK_STATE_BLOCKED)) is False
        assert is_task_resolved(must("pending")) is False

    def test_blocked_beats_a_stale_completed_status(self):
        assert is_task_resolved(must("completed", TASK_STATE_BLOCKED)) is False

    def test_not_applicable_lets_a_stage_complete(self):
        result = qa_check([must("completed"), must("pending", TASK_STATE_NOT_APPLICABLE)], [DD_STATUS_YES])
        assert result.passed is True and result.open_must_do == 0

    def test_blocked_keeps_a_stage_open_and_is_named(self):
        result = qa_check([must("completed"), must("pending", TASK_STATE_BLOCKED)], [DD_STATUS_YES])
        assert result.passed is False and result.open_must_do == 1
        assert result.reasons == ["1 must-do task still open, 1 blocked"]

    def test_marking_tasks_moves_a_stage_off_not_started(self):
        """N/A leaves status 'pending', so without the state check the stage would read Not started."""
        for state in (TASK_STATE_NOT_APPLICABLE, TASK_STATE_BLOCKED):
            assert has_activity([must("pending", state)], [None]) is True
            assert derive_stage_status(STAGE_STATE_NOT_STARTED, [must("pending", state)], [None]) ==                 STAGE_STATUS_IN_PROGRESS
        assert has_activity([must("pending")], [None]) is False

    def test_optional_and_client_specific_states_never_gate(self):
        tasks = [TaskSnapshot(SECTION_OPTIONAL, "pending", TASK_STATE_BLOCKED),
                 TaskSnapshot(SECTION_CLIENT_SPECIFIC, "pending", TASK_STATE_BLOCKED)]
        assert qa_check(tasks, [DD_STATUS_YES]).passed is True

    @pytest.mark.parametrize("state", [TASK_STATE_NOT_APPLICABLE, TASK_STATE_BLOCKED, None])
    def test_validate_accepts_the_two_states_and_none(self, state):
        assert validate_task_state(state) == state

    def test_validate_rejects_anything_else(self):
        with pytest.raises(ValueError, match="Invalid task state"):
            validate_task_state("cancelled")

    def test_snapshot_defaults_to_no_state(self):
        """Every non-Sale Ready reader constructs a snapshot without one."""
        assert TaskSnapshot(SECTION_MUST_DO, "pending").sale_ready_state is None
