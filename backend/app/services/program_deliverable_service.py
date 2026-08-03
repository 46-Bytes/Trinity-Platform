"""
Program Deliverable service: fetches the effective deliverable state for an
engagement and derives each module's status from it.

The state is read live, never cached. The schema was shaped so this is a single
round trip: the preset library LEFT JOINed to its sparse per-engagement
instances, UNION ALL the advisor-added rows. Because instances are sparse, a
preset with no instance row is a real deliverable that is simply incomplete and
in scope - hence the COALESCE defaults on the library leg.

Status derivation is deliberately kept out of the query. derive_module_status
is pure and takes plain DeliverableState tuples, so every rule in it can be
unit-tested by constructing inputs directly, with no database.
"""
from typing import Dict, List, NamedTuple, Sequence

from sqlalchemy import select, union_all, func, literal
from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.program_deliverable import EngagementModuleDeliverable, ProgramModuleDeliverable

# Derived module status values. Matches the vocabulary used by the persisted
# status columns elsewhere (Task, Diagnostic, Engagement, BBA, SBP all use
# 'in_progress'/'completed'); 'not_started' is new but keeps the same shape.
MODULE_STATUS_NOT_STARTED = "not_started"
MODULE_STATUS_IN_PROGRESS = "in_progress"
MODULE_STATUS_COMPLETED = "completed"


class DeliverableState(NamedTuple):
    """
    One deliverable's effective state, flattened for status purposes.

    `mandatory` comes from the library row for presets and from the instance
    row for advisor-added deliverables. `in_scope` and `complete` always come
    from the instance row, defaulted when no instance row exists.
    """
    mandatory: bool
    in_scope: bool
    complete: bool


def derive_module_status(states: Sequence[DeliverableState]) -> str:
    """
    Derive a module's status from its deliverables.

    Returns 'not_started', 'in_progress' or 'completed'.

    A module is complete once nothing mandatory is left outstanding AND at
    least one deliverable has actually been acted on. The second condition is
    load-bearing: without it a module whose deliverables are all optional and
    all untouched would vacuously report complete.

    Scope and completion are independent - a deliverable can be complete and
    scoped out at the same time. Such an item is not outstanding (it is out of
    scope) but still counts as activity, which falls out of the expressions
    below with no special-casing.
    """
    outstanding_mandatory = sum(1 for s in states if s.in_scope and s.mandatory and not s.complete)
    any_acted_on = any(s.complete or not s.in_scope for s in states)
    any_complete = any(s.complete for s in states)

    if outstanding_mandatory == 0 and any_acted_on:
        return MODULE_STATUS_COMPLETED
    elif any_complete:
        return MODULE_STATUS_IN_PROGRESS
    else:
        return MODULE_STATUS_NOT_STARTED


class ProgramDeliverableService:
    """Service for reading deliverable state and deriving module status."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    def get_deliverable_states_by_module(self, engagement: Engagement) -> Dict[str, List[DeliverableState]]:
        """
        Effective deliverable state for an engagement, grouped by module code.

        Only modules that actually have at least one deliverable appear as
        keys. A module with none is absent rather than mapped to an empty list
        - callers should use `.get(code, [])`, which derive_module_status
        correctly reads as 'not_started'.
        """
        preset_leg = (
            select(
                ProgramModuleDeliverable.module_code.label("module_code"),
                # The library is the only source of `mandatory` for a preset;
                # instances never override it.
                ProgramModuleDeliverable.is_mandatory.label("mandatory"),
                # No instance row means untouched: in scope and incomplete.
                func.coalesce(EngagementModuleDeliverable.is_in_scope, literal(True)).label("in_scope"),
                func.coalesce(EngagementModuleDeliverable.is_complete, literal(False)).label("complete"),
            )
            .select_from(ProgramModuleDeliverable)
            .outerjoin(
                EngagementModuleDeliverable,
                (EngagementModuleDeliverable.library_deliverable_id == ProgramModuleDeliverable.id)
                & (EngagementModuleDeliverable.engagement_id == engagement.id)
                & (EngagementModuleDeliverable.is_deleted == False),  # noqa: E712
            )
            .where(
                ProgramModuleDeliverable.program_type == engagement.tool,
                ProgramModuleDeliverable.is_active == True,  # noqa: E712
            )
        )

        # Advisor-added deliverables have no library row, so `mandatory` is read
        # from the instance. The COALESCE is defensive: "advisor-added rows
        # always set is_mandatory" is enforced in the service layer only, and a
        # stray NULL is safer treated as optional than as blocking forever.
        advisor_leg = select(
            EngagementModuleDeliverable.module_code.label("module_code"),
            func.coalesce(EngagementModuleDeliverable.is_mandatory, literal(False)).label("mandatory"),
            EngagementModuleDeliverable.is_in_scope.label("in_scope"),
            EngagementModuleDeliverable.is_complete.label("complete"),
        ).where(
            EngagementModuleDeliverable.engagement_id == engagement.id,
            EngagementModuleDeliverable.library_deliverable_id.is_(None),
            EngagementModuleDeliverable.is_deleted == False,  # noqa: E712
        )

        rows = self.db.execute(union_all(preset_leg, advisor_leg)).all()

        by_module: Dict[str, List[DeliverableState]] = {}
        for row in rows:
            by_module.setdefault(row.module_code, []).append(
                DeliverableState(
                    mandatory=bool(row.mandatory),
                    in_scope=bool(row.in_scope),
                    complete=bool(row.complete),
                )
            )
        return by_module

    # ------------------------------------------------------------------
    # Derived status
    # ------------------------------------------------------------------
    def get_module_statuses(self, engagement: Engagement) -> Dict[str, str]:
        """Module code -> derived status, for every module that has deliverables."""
        return {
            module_code: derive_module_status(states)
            for module_code, states in self.get_deliverable_states_by_module(engagement).items()
        }


def get_program_deliverable_service(db: Session) -> ProgramDeliverableService:
    return ProgramDeliverableService(db)
