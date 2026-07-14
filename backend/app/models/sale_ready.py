"""
Sale Ready Program models.

Split mirrors the Program Guide (Value Builder) feature:
  - Template tables, seeded from JSON per ``program_type`` (e.g. 'sale_ready'):
    ``ProgramStage``, ``ProgramTaskTemplate``, ``ProgramDDTemplate``.
  - Per-engagement runtime state:
    ``EngagementStageState``, ``EngagementDDItem``, ``EngagementDocumentRegisterEntry``.

Phases and modules are unified into one ``ProgramStage`` concept (they follow the
same layout), distinguished by ``stage_type`` (pre_module / module / post_module).

Generated tasks live in the existing ``tasks`` table - not here - tagged with
``module_reference`` = stage_code and ``section`` = must_do / optional / ai_custom.
"""
from sqlalchemy import (
    Column, String, Text, DateTime, Date, Integer, Numeric, Boolean, func,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


# ----------------------------------------------------------------------------
# Template tables (seeded from JSON, per program_type)
# ----------------------------------------------------------------------------
class ProgramStage(Base):
    """
    Template row for a single phase or module in a program. One row per
    pre-module phase, module, and post-module checklist. Reorderable iff
    ``stage_type == 'module'``.
    """
    __tablename__ = "program_stage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    program_type = Column(String(100), nullable=False, comment="e.g. 'sale_ready' - matches Engagement.tool")
    stage_code = Column(String(30), nullable=False, comment="e.g. 'ONBOARD', 'DIAG', 'M_FIN', 'SALE_PLANNER'")
    stage_type = Column(String(20), nullable=False, comment="pre_module | module | post_module")
    default_order = Column(Integer, nullable=False, comment="Default sequence within the program")

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, server_default='true')

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'stage_code', name='uq_program_stage_type_code'),
        Index('ix_program_stage_type_order', 'program_type', 'default_order'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "program_type": self.program_type,
            "stage_code": self.stage_code,
            "stage_type": self.stage_type,
            "default_order": self.default_order,
            "title": self.title,
            "description": self.description,
            "is_active": self.is_active,
        }


class ProgramTaskTemplate(Base):
    """
    Template row for a pre-loaded task. Drives task auto-generation into the
    existing task system when an engagement is created.
    """
    __tablename__ = "program_task_template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    program_type = Column(String(100), nullable=False)
    stage_code = Column(String(30), nullable=False, comment="Matches ProgramStage.stage_code")
    section = Column(String(20), nullable=False, comment="must_do | optional | ai_custom")

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, server_default='medium', comment="low | medium | high | critical")
    default_order = Column(Integer, nullable=False, server_default='0')
    due_offset_days = Column(Integer, nullable=True, comment="Days after stage start_date; NULL = advisor sets manually")

    is_active = Column(Boolean, nullable=False, server_default='true')

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        Index('ix_program_task_template_type_stage', 'program_type', 'stage_code'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "program_type": self.program_type,
            "stage_code": self.stage_code,
            "section": self.section,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "default_order": self.default_order,
            "due_offset_days": self.due_offset_days,
            "is_active": self.is_active,
        }


class ProgramDDTemplate(Base):
    """
    Template row for a due-diligence checklist item, seeded per module.
    """
    __tablename__ = "program_dd_template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    program_type = Column(String(100), nullable=False)
    module_code = Column(String(30), nullable=False, comment="ProgramStage.stage_code of a stage_type='module' row")

    category = Column(String(255), nullable=False)
    sub_item = Column(Text, nullable=True)
    document_required = Column(Text, nullable=True)
    action_step = Column(Text, nullable=True)
    default_order = Column(Integer, nullable=False, server_default='0')

    is_active = Column(Boolean, nullable=False, server_default='true')

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        Index('ix_program_dd_template_type_module', 'program_type', 'module_code'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "program_type": self.program_type,
            "module_code": self.module_code,
            "category": self.category,
            "sub_item": self.sub_item,
            "document_required": self.document_required,
            "action_step": self.action_step,
            "default_order": self.default_order,
            "is_active": self.is_active,
        }


# ----------------------------------------------------------------------------
# Runtime state tables (per engagement)
# ----------------------------------------------------------------------------
class EngagementStageState(Base):
    """
    Per-engagement, per-stage runtime state: status, dates, lead advisor, and
    the persisted (advisor-adjustable) module priority order.
    """
    __tablename__ = "engagement_stage_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    stage_code = Column(String(30), nullable=False)

    status = Column(String(20), nullable=False, server_default='not_started', comment="not_started | in_progress | complete")
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    lead_advisor_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    priority_order = Column(Integer, nullable=True, comment="Persisted module order (set at Prioritisation); NULL falls back to default_order")

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    engagement = relationship("Engagement")

    __table_args__ = (
        UniqueConstraint('engagement_id', 'stage_code', name='uq_engagement_stage_state'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id),
            "stage_code": self.stage_code,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "lead_advisor_id": str(self.lead_advisor_id) if self.lead_advisor_id else None,
            "priority_order": self.priority_order,
        }


class EngagementDDItem(Base):
    """
    Per-engagement due-diligence item - the single source of truth for both the
    master DD checklist and a module's DD view (the module view is the same rows
    filtered by ``module_code``; there is no sync).
    """
    __tablename__ = "engagement_dd_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    module_code = Column(String(30), nullable=False, index=True)

    category = Column(String(255), nullable=False)
    sub_item = Column(Text, nullable=True)
    document_required = Column(Text, nullable=True)
    action_step = Column(Text, nullable=True)
    responsible_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    completed = Column(Boolean, nullable=False, server_default='false')
    date_completed = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    # File reference (Feature 12 owns the full attach experience; store metadata + link now)
    media_id = Column(UUID(as_uuid=True), ForeignKey('media.id', ondelete='SET NULL'), nullable=True)
    file_link = Column(Text, nullable=True, comment="Cloud/Drive link if not stored as Media")

    display_order = Column(Integer, nullable=False, server_default='0')

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    engagement = relationship("Engagement")

    __table_args__ = (
        Index('ix_engagement_dd_item_eng_module', 'engagement_id', 'module_code'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id),
            "module_code": self.module_code,
            "category": self.category,
            "sub_item": self.sub_item,
            "document_required": self.document_required,
            "action_step": self.action_step,
            "responsible_user_id": str(self.responsible_user_id) if self.responsible_user_id else None,
            "completed": self.completed,
            "date_completed": self.date_completed.isoformat() if self.date_completed else None,
            "notes": self.notes,
            "media_id": str(self.media_id) if self.media_id else None,
            "file_link": self.file_link,
            "display_order": self.display_order,
        }


class EngagementDocumentRegisterEntry(Base):
    """
    Per-engagement, per-stage document register row.
    """
    __tablename__ = "engagement_document_register_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    stage_code = Column(String(30), nullable=False, index=True)

    document_name = Column(String(255), nullable=False)
    creation_date = Column(Date, nullable=True)
    document_id = Column(String(255), nullable=True, comment="Advisor-facing document reference/number")
    renewal_date = Column(Date, nullable=True)
    renewal_cost = Column(Numeric(12, 2), nullable=True)
    notes = Column(Text, nullable=True)

    media_id = Column(UUID(as_uuid=True), ForeignKey('media.id', ondelete='SET NULL'), nullable=True)
    file_link = Column(Text, nullable=True, comment="Cloud/Drive link if not stored as Media")

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    engagement = relationship("Engagement")

    __table_args__ = (
        Index('ix_engagement_doc_register_eng_stage', 'engagement_id', 'stage_code'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "engagement_id": str(self.engagement_id),
            "stage_code": self.stage_code,
            "document_name": self.document_name,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "document_id": self.document_id,
            "renewal_date": self.renewal_date.isoformat() if self.renewal_date else None,
            "renewal_cost": float(self.renewal_cost) if self.renewal_cost is not None else None,
            "notes": self.notes,
            "media_id": str(self.media_id) if self.media_id else None,
            "file_link": self.file_link,
        }
