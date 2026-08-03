"""
Program Deliverable models: the shared library of preset deliverables authored
per module, and the sparse per-engagement instances that carry completion and
scope state (e.g. Value Builder).

Template/instance split:
  - ProgramModuleDeliverable is the library. It is authored once and shared by
    every engagement, so library edits are visible to live engagements
    immediately - instances hold no copy of the authored text.
  - EngagementModuleDeliverable is sparse. A row exists only once someone has
    ticked a deliverable off or scoped it out; an absent row means "incomplete
    and in scope". This is what lets a newly added preset appear on every live
    engagement with no backfill.

The same table also carries advisor-added deliverables, which exist on one
engagement only and have no library row - see the discriminator note on
EngagementModuleDeliverable.library_deliverable_id.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class ProgramModuleDeliverable(Base):
    """
    A single preset deliverable in the module card library. Scoped by
    program_type so the same table can serve multiple module-based programs,
    matching ProgramModuleContent.

    Presets are never deleted - set is_active=False to retire one.
    """
    __tablename__ = "program_module_deliverable"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    program_type = Column(String(100), nullable=False, comment="e.g. 'value_builder' - matches Engagement.tool")
    module_code = Column(String(20), nullable=False, comment="e.g. 'M0', 'V1'..'V11', 'M12'")
    deliverable_key = Column(String(100), nullable=False, comment="Stable slug for this deliverable within the module")

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, comment="Optional longer explanation of the deliverable")
    is_mandatory = Column(
        Boolean,
        nullable=False,
        server_default='true',
        comment="Mandatory/optional flag for this preset; the only source of truth - instances never override it",
    )

    display_order = Column(Integer, nullable=False, comment="Author-defined sequence within (program_type, module_code)")
    is_active = Column(Boolean, nullable=False, server_default='true', comment="False retires the preset without deleting it")

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'module_code', 'deliverable_key', name='uq_program_module_deliverable_type_module_key'),
        Index('ix_program_module_deliverable_type_module_order', 'program_type', 'module_code', 'display_order'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "program_type": self.program_type,
            "module_code": self.module_code,
            "deliverable_key": self.deliverable_key,
            "title": self.title,
            "description": self.description,
            "is_mandatory": self.is_mandatory,
            "display_order": self.display_order,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<ProgramModuleDeliverable {self.program_type}/{self.module_code}/{self.deliverable_key}>"


class EngagementModuleDeliverable(Base):
    """
    Per-engagement deliverable state. Serves two kinds of row, discriminated by
    library_deliverable_id:

      - preset      (library_deliverable_id IS NOT NULL): title, description
                    and is_mandatory are read live from the library row and are
                    NULL here. May be scoped out, never deleted.
      - advisor-added (library_deliverable_id IS NULL): exists on this
                    engagement only and carries its own title, module_code and
                    is_mandatory. Removable by soft delete.

    These invariants are enforced in the service layer, matching the rest of
    app/models (no CheckConstraints anywhere in this codebase).

    Note that is_in_scope is deliberately a separate flag rather than a value
    folded into a status column: scoping a completed deliverable out and back
    in leaves is_complete untouched, whereas a single status field would forget
    it.
    """
    __tablename__ = "engagement_module_deliverable"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    module_code = Column(String(20), nullable=False, comment="Denormalised for presets; authoritative for advisor-added rows, which have no library row")

    # Discriminator: NOT NULL = preset instance, NULL = advisor-added
    library_deliverable_id = Column(
        UUID(as_uuid=True),
        ForeignKey('program_module_deliverable.id', ondelete='CASCADE'),
        nullable=True,
        comment="NOT NULL for a preset instance, NULL for an advisor-added deliverable",
    )

    # Advisor-added content. Always NULL for presets, which read the library row.
    title = Column(String(255), nullable=True, comment="Advisor-added deliverables only; MUST be NULL for presets, which read program_module_deliverable.title")
    description = Column(Text, nullable=True, comment="Advisor-added deliverables only; MUST be NULL for presets")
    is_mandatory = Column(
        Boolean,
        nullable=True,
        comment="Mandatory/optional flag for advisor-added deliverables only; MUST be NULL for presets, which read program_module_deliverable.is_mandatory",
    )

    # Completion
    is_complete = Column(Boolean, nullable=False, server_default='false')
    completed_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Scope - reversible exclusion, not deletion
    is_in_scope = Column(Boolean, nullable=False, server_default='true', comment="False means scoped out: retained on the engagement but excluded from completion")
    scoped_out_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    scoped_out_at = Column(DateTime, nullable=True)

    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment="Author of an advisor-added deliverable")

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, server_default='false', comment="Advisor-added deliverables only; presets are scoped out, never deleted")

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        # Postgres treats NULLs as distinct in a unique index, so this enforces
        # exactly one instance row per (engagement, preset) while placing no
        # limit on advisor-added rows. It also serves as the join index for
        # module status computation.
        UniqueConstraint('engagement_id', 'library_deliverable_id', name='uq_engagement_module_deliverable_engagement_library'),
        Index('ix_engagement_module_deliverable_engagement_module', 'engagement_id', 'module_code'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id),
            "module_code": self.module_code,
            "library_deliverable_id": str(self.library_deliverable_id) if self.library_deliverable_id else None,
            "title": self.title,
            "description": self.description,
            "is_mandatory": self.is_mandatory,
            "is_complete": self.is_complete,
            "completed_by_user_id": str(self.completed_by_user_id) if self.completed_by_user_id else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_in_scope": self.is_in_scope,
            "scoped_out_by_user_id": str(self.scoped_out_by_user_id) if self.scoped_out_by_user_id else None,
            "scoped_out_at": self.scoped_out_at.isoformat() if self.scoped_out_at else None,
            "created_by_user_id": str(self.created_by_user_id) if self.created_by_user_id else None,
        }

    def __repr__(self):
        kind = "preset" if self.library_deliverable_id else "advisor"
        return f"<EngagementModuleDeliverable {self.module_code} {kind} complete={self.is_complete} in_scope={self.is_in_scope}>"
