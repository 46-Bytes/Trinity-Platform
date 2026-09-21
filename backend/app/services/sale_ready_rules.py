"""
Sale Ready rules: stage status, the QA gate on marking a stage complete, due
diligence (DD) item status, gaps, and program progress.

Pure functions over plain values - no database, no ORM - so each rule is unit
tested directly, like derive_module_status in program_deliverable_service.

Rules come from the client's build brief (12 Sep 2026). Where the client has
not answered yet, the choice lives in SaleReadyPolicy and nowhere else, so an
answer changes one value instead of code. Each such field names its question.
"""
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Optional, Sequence

# ----------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------
STAGE_TYPE_PRE_MODULE = "pre_module"
STAGE_TYPE_MODULE = "module"
STAGE_TYPE_POST_MODULE = "post_module"
STAGE_TYPES = frozenset({STAGE_TYPE_PRE_MODULE, STAGE_TYPE_MODULE, STAGE_TYPE_POST_MODULE})

SECTION_MUST_DO = "must_do"
SECTION_OPTIONAL = "optional"
SECTION_CLIENT_SPECIFIC = "client_specific"
TASK_SECTIONS = frozenset({SECTION_MUST_DO, SECTION_OPTIONAL, SECTION_CLIENT_SPECIFIC})

# What the advisor has done to a stage (stored). Display status is derived.
STAGE_STATE_NOT_STARTED = "not_started"
STAGE_STATE_STARTED = "started"
STAGE_STATE_COMPLETED = "completed"
STAGE_STATES = frozenset({STAGE_STATE_NOT_STARTED, STAGE_STATE_STARTED, STAGE_STATE_COMPLETED})

STAGE_STATUS_NOT_STARTED = "not_started"
STAGE_STATUS_IN_PROGRESS = "in_progress"
STAGE_STATUS_COMPLETED = "completed"

# Existing Task.status values this module reads.
TASK_STATUS_PENDING = "pending"
TASK_STATUS_COMPLETED = "completed"

# Sale Ready's own per-task marks, carried in tasks.sale_ready_state so the
# shared tasks.status keeps its four values (C7). NULL means an ordinary task.
TASK_STATE_NOT_APPLICABLE = "not_applicable"
TASK_STATE_BLOCKED = "blocked"
TASK_STATES = frozenset({TASK_STATE_NOT_APPLICABLE, TASK_STATE_BLOCKED})

DD_STATUS_YES = "yes"
DD_STATUS_IN_PROGRESS = "in_progress"
DD_STATUS_NO = "no"
DD_STATUS_NOT_APPLICABLE = "not_applicable"
DD_STATUSES = frozenset({DD_STATUS_YES, DD_STATUS_IN_PROGRESS, DD_STATUS_NO, DD_STATUS_NOT_APPLICABLE})

GAP_FIX = "fix"
GAP_DISCLOSE = "disclose"
GAP_REFER = "refer"
GAP_HANDLINGS = frozenset({GAP_FIX, GAP_DISCLOSE, GAP_REFER})


# ----------------------------------------------------------------------
# Open decisions
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class SaleReadyPolicy:
    """
    Choices that wait on client answers. Defaults follow the brief's literal text.
    """
    # C7 answered: N/A and blocked are Sale Ready marks, not global statuses.
    # A completed task is resolved, and so is one marked not required.
    resolved_task_statuses: FrozenSet[str] = field(default_factory=lambda: frozenset({TASK_STATUS_COMPLETED}))
    resolved_task_states: FrozenSet[str] = field(default_factory=lambda: frozenset({TASK_STATE_NOT_APPLICABLE}))
    # C14: the brief blocks completion only on DD items with *no* status, so
    # In progress passes. Narrow this set if the client says otherwise.
    qa_accepted_dd_statuses: FrozenSet[str] = DD_STATUSES


DEFAULT_POLICY = SaleReadyPolicy()


class TaskSnapshot(NamedTuple):
    """The task fields the rules read. `sale_ready_state` is NULL on most tasks."""
    section: Optional[str]
    status: str
    sale_ready_state: Optional[str] = None


def validate_task_state(state: Optional[str]) -> Optional[str]:
    """None clears the mark; anything else must be 'not_applicable' or 'blocked'."""
    if state is not None and state not in TASK_STATES:
        raise ValueError(f"Invalid task state {state!r}")
    return state


def is_task_resolved(task: TaskSnapshot, policy: "SaleReadyPolicy" = None) -> bool:
    """
    Done, or deliberately not required. Blocked is neither: it names a reason the
    work has not happened, so it leaves the stage open.
    """
    policy = policy or DEFAULT_POLICY
    if task.sale_ready_state == TASK_STATE_BLOCKED:
        return False
    return (
        task.status in policy.resolved_task_statuses
        or task.sale_ready_state in policy.resolved_task_states
    )


# ----------------------------------------------------------------------
# Stage status
# ----------------------------------------------------------------------
def validate_stage_state(state: str) -> str:
    if state not in STAGE_STATES:
        raise ValueError(f"Invalid stage state {state!r}")
    return state


def has_activity(tasks: Iterable[TaskSnapshot], dd_statuses: Iterable[Optional[str]]) -> bool:
    """
    'Something is ticked': a task moved off pending, a task marked N/A or
    blocked, or a DD item given a status.

    Marking tasks N/A leaves their status at 'pending', so without the state
    check a stage the advisor had worked through would still read Not started.
    """
    return (
        any(t.status != TASK_STATUS_PENDING or t.sale_ready_state is not None for t in tasks)
        or any(s is not None for s in dd_statuses)
    )


def derive_stage_status(
    stored_state: str,
    tasks: Sequence[TaskSnapshot],
    dd_statuses: Sequence[Optional[str]],
) -> str:
    """
    Brief: Not started until the advisor starts it or something is ticked, then
    In progress, then Complete when the advisor marks it.

    Phase tasks exist from engagement creation, so merely having tasks does not
    count as started - otherwise every phase would open In progress.
    """
    validate_stage_state(stored_state)
    if stored_state == STAGE_STATE_COMPLETED:
        return STAGE_STATUS_COMPLETED
    if stored_state == STAGE_STATE_STARTED or has_activity(tasks, dd_statuses):
        return STAGE_STATUS_IN_PROGRESS
    return STAGE_STATUS_NOT_STARTED


class QAResult(NamedTuple):
    passed: bool
    open_must_do: int
    dd_without_status: int
    reasons: List[str]


def qa_check(
    tasks: Sequence[TaskSnapshot],
    dd_statuses: Sequence[Optional[str]],
    policy: SaleReadyPolicy = DEFAULT_POLICY,
) -> QAResult:
    """
    Brief: a stage can't be marked complete while a must-do task is still open,
    or while any of its DD items has no status. Optional and client-specific
    tasks never gate completion.
    """
    must_do = [t for t in tasks if t.section == SECTION_MUST_DO]
    open_must_do = sum(1 for t in must_do if not is_task_resolved(t, policy))
    blocked = sum(1 for t in must_do if t.sale_ready_state == TASK_STATE_BLOCKED)
    dd_without_status = sum(1 for s in dd_statuses if s not in policy.qa_accepted_dd_statuses)

    reasons = []
    if open_must_do:
        blocked_note = f", {blocked} blocked" if blocked else ""
        reasons.append(
            f"{open_must_do} must-do task{'s' if open_must_do != 1 else ''} still open{blocked_note}"
        )
    if dd_without_status:
        reasons.append(f"{dd_without_status} DD item{'s' if dd_without_status != 1 else ''} with no status")
    return QAResult(not reasons, open_must_do, dd_without_status, reasons)


# ----------------------------------------------------------------------
# DD items
# ----------------------------------------------------------------------
def validate_dd_status(status: Optional[str]) -> Optional[str]:
    """None clears the status; anything else must be one of the four."""
    if status is not None and status not in DD_STATUSES:
        raise ValueError(f"Invalid DD status {status!r}")
    return status


def validate_gap_handling(status: Optional[str], gap_handling: Optional[str]) -> Optional[str]:
    """A gap is a DD item marked No; its handling can only be set while it is No."""
    if gap_handling is None:
        return None
    if gap_handling not in GAP_HANDLINGS:
        raise ValueError(f"Invalid gap handling {gap_handling!r}")
    if status != DD_STATUS_NO:
        raise ValueError("Gap handling can only be set on a DD item marked No")
    return gap_handling


def effective_gap_handling(status: Optional[str], gap_handling: Optional[str]) -> Optional[str]:
    """
    The handling that counts right now. A stored choice survives the item
    leaving No - so re-opening the gap restores it - but only counts while No.
    """
    return gap_handling if status == DD_STATUS_NO else None


class GapSummary(NamedTuple):
    total: int
    fix: int
    disclose: int
    refer: int
    unhandled: int


def summarise_gaps(items: Iterable[tuple]) -> GapSummary:
    """Gaps summary from (status, gap_handling) pairs."""
    counts: Dict[Optional[str], int] = {}
    total = 0
    for status, gap in items:
        if status != DD_STATUS_NO:
            continue
        total += 1
        counts[gap] = counts.get(gap, 0) + 1
    return GapSummary(total, counts.get(GAP_FIX, 0), counts.get(GAP_DISCLOSE, 0),
                      counts.get(GAP_REFER, 0), counts.get(None, 0))


# ----------------------------------------------------------------------
# Program progress
# ----------------------------------------------------------------------
class StageProgress(NamedTuple):
    stage_type: str
    status: str
    must_do_total: int
    must_do_resolved: int
    dd_total: int
    dd_yes: int


class ProgramProgress(NamedTuple):
    phases_completed: int
    phases_total: int
    modules_completed: int
    modules_total: int
    must_do_resolved: int
    must_do_total: int
    dd_yes: int
    dd_total: int
    percent: int


def program_progress(stages: Sequence[StageProgress]) -> ProgramProgress:
    """
    The roadmap's progress card. Phases are the four before the modules (the
    mockup counts x / 4); the bar is must-do tasks resolved across the program.
    """
    phases = [s for s in stages if s.stage_type == STAGE_TYPE_PRE_MODULE]
    modules = [s for s in stages if s.stage_type == STAGE_TYPE_MODULE]
    must_total = sum(s.must_do_total for s in stages)
    must_done = sum(s.must_do_resolved for s in stages)
    return ProgramProgress(
        phases_completed=sum(1 for s in phases if s.status == STAGE_STATUS_COMPLETED),
        phases_total=len(phases),
        modules_completed=sum(1 for s in modules if s.status == STAGE_STATUS_COMPLETED),
        modules_total=len(modules),
        must_do_resolved=must_done,
        must_do_total=must_total,
        dd_yes=sum(s.dd_yes for s in stages),
        dd_total=sum(s.dd_total for s in stages),
        percent=round(must_done / must_total * 100) if must_total else 0,
    )
