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

The mutation half of this module enforces the domain invariants, because there
are no CheckConstraints anywhere in this codebase - nothing at the DB level
stops a preset being soft deleted or an advisor-added row existing with no
title. The rules themselves live in small pure validators for the same reason
derive_module_status does: they are exhaustively testable without a database.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, NamedTuple, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, union_all, func, literal
from sqlalchemy.exc import IntegrityError
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


# ----------------------------------------------------------------------
# Invariant validators
#
# Pure - no DB access, no ORM objects. They take plain values and raise
# ValueError, which is the house convention for domain violations and is what
# the API layer translates into a 4xx.
# ----------------------------------------------------------------------
def normalize_advisor_title(title: Optional[str]) -> str:
    """Advisor-added deliverables must carry a title. Returns it stripped."""
    if title is None or not str(title).strip():
        raise ValueError("Advisor-added deliverables require a title")
    return str(title).strip()


def validate_advisor_mandatory(is_mandatory: Optional[bool]) -> bool:
    """
    Advisor-added deliverables must state whether they are mandatory. There is
    no library row to inherit the flag from, and a NULL here is what the status
    query has to COALESCE around.
    """
    if is_mandatory is None:
        raise ValueError("Advisor-added deliverables require is_mandatory")
    return bool(is_mandatory)


def normalize_module_code(module_code: Optional[str]) -> str:
    """Every deliverable belongs to a module. Returns the code stripped."""
    if module_code is None or not str(module_code).strip():
        raise ValueError("Advisor-added deliverables require a module_code")
    return str(module_code).strip()


def assert_advisor_added(library_deliverable_id: Optional[UUID], action: str) -> None:
    """
    Guard the advisor-only operations.

    Presets are library content shared by every engagement - they are scoped
    out, never edited or deleted per engagement. A non-NULL
    library_deliverable_id means this row is a preset instance.
    """
    if library_deliverable_id is not None:
        raise ValueError(f"Cannot {action} a preset deliverable; scope it out instead")


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


    # ------------------------------------------------------------------
    # Resolution and materialization
    # ------------------------------------------------------------------
    def _get_instance(self, engagement_id: UUID, instance_id: UUID) -> Optional[EngagementModuleDeliverable]:
        return (
            self.db.query(EngagementModuleDeliverable)
            .filter(
                EngagementModuleDeliverable.id == instance_id,
                EngagementModuleDeliverable.engagement_id == engagement_id,
                EngagementModuleDeliverable.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def _get_instance_for_preset(self, engagement_id: UUID, library_id: UUID) -> Optional[EngagementModuleDeliverable]:
        return (
            self.db.query(EngagementModuleDeliverable)
            .filter(
                EngagementModuleDeliverable.engagement_id == engagement_id,
                EngagementModuleDeliverable.library_deliverable_id == library_id,
                EngagementModuleDeliverable.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def _get_library_row(self, engagement: Engagement, library_id: UUID) -> Optional[ProgramModuleDeliverable]:
        """
        Active presets belonging to this engagement's program only. A retired
        preset is invisible to the status query, so allowing state to be written
        against one would record completion that nothing can read back.
        """
        return (
            self.db.query(ProgramModuleDeliverable)
            .filter(
                ProgramModuleDeliverable.id == library_id,
                ProgramModuleDeliverable.program_type == engagement.tool,
                ProgramModuleDeliverable.is_active == True,  # noqa: E712
            )
            .first()
        )

    def _materialize_preset(self, engagement: Engagement, library_row: ProgramModuleDeliverable) -> EngagementModuleDeliverable:
        """
        Find-or-create the instance row for a preset.

        Instances are sparse, so the first mutation on a preset creates its row.
        The insert is wrapped in a savepoint because uq_engagement_module_
        deliverable_engagement_library makes a concurrent create (a double
        click, realistically) an IntegrityError rather than a duplicate row -
        losing that race just means re-reading what the winner wrote.
        """
        existing = self._get_instance_for_preset(engagement.id, library_row.id)
        if existing is not None:
            return existing

        row = EngagementModuleDeliverable(
            engagement_id=engagement.id,
            # Copied from the library row, never caller-supplied: module_code is
            # denormalised here and only the library's value is authoritative.
            module_code=library_row.module_code,
            library_deliverable_id=library_row.id,
            # title/description/is_mandatory stay NULL - presets read them live
            # from the library row.
            is_complete=False,
            is_in_scope=True,
            is_deleted=False,
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
            return row
        except IntegrityError:
            self.db.expunge(row)
            return self._get_instance_for_preset(engagement.id, library_row.id)

    def _resolve(self, engagement: Engagement, deliverable_id: UUID):
        """
        Resolve a deliverable id to (instance_row, library_row).

        Advisor-added rows and already-materialized presets are addressed by
        their instance id; a preset that has never been touched has no instance
        row, so it is addressed by its library id. The two ids live in different
        tables, so there is no ambiguity.

        For a preset the instance is looked up too, so a caller addressing an
        already-materialized preset by its library id still gets the existing
        row back. A None instance therefore means "no row exists yet", not
        merely "not addressed by instance id" - which is what the no-op
        shortcuts in the mutation methods rely on.

        Returns (instance_or_None, library_row_or_None). Raises if neither.
        """
        instance = self._get_instance(engagement.id, deliverable_id)
        if instance is not None:
            return instance, None

        library_row = self._get_library_row(engagement, deliverable_id)
        if library_row is not None:
            return self._get_instance_for_preset(engagement.id, library_row.id), library_row

        raise ValueError(f"Deliverable {deliverable_id} not found for this engagement")

    # ------------------------------------------------------------------
    # Mutations: completion and scope
    #
    # These two write disjoint column sets. Scoping a completed deliverable out
    # and back in must leave is_complete untouched - that orthogonality is the
    # entire reason they are separate columns rather than one status field.
    # ------------------------------------------------------------------
    def set_deliverable_complete(
        self,
        engagement: Engagement,
        deliverable_id: UUID,
        is_complete: bool,
        user_id: UUID,
    ) -> Optional[EngagementModuleDeliverable]:
        """
        Mark a deliverable complete or incomplete.

        Returns None when the call would not change anything on a preset that
        has no instance row yet - an absent row already means incomplete, so
        materializing one would record no information.
        """
        instance, library_row = self._resolve(engagement, deliverable_id)

        if instance is None:
            if not is_complete:
                return None
            instance = self._materialize_preset(engagement, library_row)

        if instance.is_complete == bool(is_complete):
            return instance

        now = datetime.now(timezone.utc)
        instance.is_complete = bool(is_complete)
        instance.completed_by_user_id = user_id if is_complete else None
        instance.completed_at = now if is_complete else None

        self.db.commit()
        self.db.refresh(instance)
        return instance

    def set_deliverable_scope(
        self,
        engagement: Engagement,
        deliverable_id: UUID,
        is_in_scope: bool,
        user_id: UUID,
    ) -> Optional[EngagementModuleDeliverable]:
        """
        Scope a deliverable out, or back in.

        Scoping out is reversible and is not deletion: the row is retained and
        is_complete is deliberately left alone, so scoping a completed item out
        and back in restores it exactly as it was.

        Returns None when the call would not change anything on a preset with no
        instance row yet - an absent row already means in scope.
        """
        instance, library_row = self._resolve(engagement, deliverable_id)

        if instance is None:
            if is_in_scope:
                return None
            instance = self._materialize_preset(engagement, library_row)

        if instance.is_in_scope == bool(is_in_scope):
            return instance

        now = datetime.now(timezone.utc)
        instance.is_in_scope = bool(is_in_scope)
        instance.scoped_out_by_user_id = None if is_in_scope else user_id
        instance.scoped_out_at = None if is_in_scope else now

        self.db.commit()
        self.db.refresh(instance)
        return instance

    # ------------------------------------------------------------------
    # Mutations: advisor-added deliverables
    # ------------------------------------------------------------------
    def add_advisor_deliverable(
        self,
        engagement: Engagement,
        module_code: str,
        title: str,
        is_mandatory: bool,
        user_id: UUID,
        description: Optional[str] = None,
    ) -> EngagementModuleDeliverable:
        """Create a deliverable that exists on this engagement only."""
        row = EngagementModuleDeliverable(
            engagement_id=engagement.id,
            module_code=normalize_module_code(module_code),
            library_deliverable_id=None,
            title=normalize_advisor_title(title),
            description=description,
            is_mandatory=validate_advisor_mandatory(is_mandatory),
            is_complete=False,
            is_in_scope=True,
            is_deleted=False,
            created_by_user_id=user_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_advisor_deliverable(
        self,
        engagement: Engagement,
        instance_id: UUID,
        **fields: Any,
    ) -> EngagementModuleDeliverable:
        """
        Edit an advisor-added deliverable's title, description or is_mandatory.

        Only keys actually passed are applied, so omitting a field leaves it
        alone. Passing None explicitly for a required field raises rather than
        nulling it.
        """
        unknown = set(fields) - {"title", "description", "is_mandatory"}
        if unknown:
            raise ValueError(f"Cannot update {', '.join(sorted(unknown))}")

        instance = self._get_instance(engagement.id, instance_id)
        if instance is None:
            raise ValueError(f"Deliverable {instance_id} not found for this engagement")
        assert_advisor_added(instance.library_deliverable_id, "edit")

        if not fields:
            return instance

        if "title" in fields:
            instance.title = normalize_advisor_title(fields["title"])
        if "is_mandatory" in fields:
            instance.is_mandatory = validate_advisor_mandatory(fields["is_mandatory"])
        if "description" in fields:
            instance.description = fields["description"]

        self.db.commit()
        self.db.refresh(instance)
        return instance

    def remove_advisor_deliverable(
        self,
        engagement: Engagement,
        instance_id: UUID,
    ) -> EngagementModuleDeliverable:
        """
        Soft delete an advisor-added deliverable.

        Presets cannot be removed at all - they are library content shared by
        every engagement, and the per-engagement way to exclude one is to scope
        it out.
        """
        instance = self._get_instance(engagement.id, instance_id)
        if instance is None:
            raise ValueError(f"Deliverable {instance_id} not found for this engagement")
        assert_advisor_added(instance.library_deliverable_id, "delete")

        instance.is_deleted = True
        self.db.commit()
        self.db.refresh(instance)
        return instance


def get_program_deliverable_service(db: Session) -> ProgramDeliverableService:
    return ProgramDeliverableService(db)
