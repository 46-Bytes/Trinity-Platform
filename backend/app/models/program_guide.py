"""
Program Guide models: client-authored module card content and per-engagement
state for module-based advisory programs (e.g. Value Builder).
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class ProgramModuleContent(Base):
    """
    Client-authored content for a single module card. Scoped by program_type so
    the same table can serve multiple module-based programs.

    The columns mirror the specification's own card sections one for one, which
    is why there are so many of them rather than a single content blob: each is
    rendered separately and edited separately by an admin.

    Durations throughout ("Target 95 to 130 minutes", "60 to 120 minutes
    depending on data quality") are stored as the spec's own wording rather
    than parsed into numbers. Nothing computes on them, and parsing would
    invent precision while discarding the qualifiers.
    """
    __tablename__ = "program_module_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    program_type = Column(String(100), nullable=False, comment="e.g. 'value_builder' - matches Engagement.tool")
    module_code = Column(String(20), nullable=False, comment="e.g. 'M0', 'V1'..'V11', 'M12'")
    display_order = Column(Integer, nullable=False, comment="Default/author-defined sequence for this module")

    title = Column(String(255), nullable=False)
    focus = Column(Text, nullable=True, comment="One-line statement of what this module concentrates on")
    purpose = Column(Text, nullable=True, comment="One-paragraph summary of what this module achieves")
    core_outcomes = Column(JSONB, nullable=True, comment="[text, ...] what is true once the module is done")

    # Preparation is split in two because the checklist is tickable and the
    # summary is not: EngagementModuleChecklistItem.checklist_item_key matches
    # preparation_checklist[].key, so that array's shape is load-bearing and
    # the owner/duration could not simply be folded into it.
    preparation_checklist = Column(JSONB, nullable=True, comment="[{key, text}] static preparation items")
    preparation_summary = Column(JSONB, nullable=True, comment="{owner, duration} who prepares, and how long it takes")

    sessions = Column(
        JSONB,
        nullable=True,
        comment="[{key, title, duration, format, agenda: [{key, title, duration, detail, questions: [text, ...]}]}] "
                "the facilitation plan; `questions` is the advisor's prompt script for that agenda item",
    )
    between_sessions = Column(
        JSONB,
        nullable=True,
        comment="{owner, duration, items: [text, ...]} work done between two sessions, e.g. generating "
                "a document from the first session's workbook before walking the client through it",
    )
    post_session_actions = Column(JSONB, nullable=True, comment="{owner, duration, items: [text, ...]} follow-up work after the session")

    notes = Column(
        JSONB,
        nullable=True,
        comment="[{key, title, text, items, section}] prose that is not part of any list. `title` and "
                "`section` are both optional and independent: a note may be titled or not, and attached to "
                "a named section or to the module as a whole. `items` carries a bulleted body. Started as "
                "two columns until a note arrived that was both titled AND section-attached, which neither "
                "could hold",
    )
    tables = Column(
        JSONB,
        nullable=True,
        comment="[{key, title, intro, section, columns: [{key, label}], rows: [{key, label, cells: [text]}]}] "
                "reference matrices the advisor reads, e.g. the four business model shapes against the "
                "dimensions that vary by shape. Cells align to columns by index, so every row carries "
                "exactly as many cells as there are columns",
    )

    guardrails = Column(
        JSONB,
        nullable=True,
        comment="{must_not: [text, ...], note} boundaries of profession rather than of module - where a module "
                "surfaces an issue belonging elsewhere, the advisor still addresses it and records it there",
    )
    quality_standards = Column(JSONB, nullable=True, comment="[text, ...] what good looks like for this module")

    recommended_tools = Column(
        JSONB,
        nullable=True,
        comment="[{tool_key, label, when, status}] Trinity tools for this module; `status` carries build state "
                "so an unbuilt tool can be shown as pending rather than silently omitted",
    )
    required_inputs = Column(
        JSONB,
        nullable=True,
        comment="[{key, label, source, fallback}] where source is one of the Part A literals "
                "'Held in Trinity'|'Advisor to upload'|'From an earlier module'; fallback states what to do "
                "when an earlier-module input is absent, since no module may assume another has run",
    )
    deliverables = Column(
        JSONB,
        nullable=True,
        comment="[label, ...] display-only labels, DERIVED by the seed script from the titles in "
                "program_module_deliverable. Not a source of truth: the deliverables the status engine "
                "reads live in that table. Retire this once the composed view replaces it.",
    )

    is_active = Column(Boolean, nullable=False, server_default='true')

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'module_code', name='uq_program_module_content_type_code'),
        Index('ix_program_module_content_type_order', 'program_type', 'display_order'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "program_type": self.program_type,
            "module_code": self.module_code,
            "display_order": self.display_order,
            "title": self.title,
            "focus": self.focus,
            "purpose": self.purpose,
            "core_outcomes": self.core_outcomes,
            "preparation_checklist": self.preparation_checklist,
            "preparation_summary": self.preparation_summary,
            "sessions": self.sessions,
            "between_sessions": self.between_sessions,
            "post_session_actions": self.post_session_actions,
            "notes": self.notes,
            "tables": self.tables,
            "guardrails": self.guardrails,
            "quality_standards": self.quality_standards,
            "recommended_tools": self.recommended_tools,
            "required_inputs": self.required_inputs,
            "deliverables": self.deliverables,
            "is_active": self.is_active,
        }


class EngagementProgramModuleState(Base):
    """
    Per-engagement advisor-adjusted module order. The recommended order itself
    is computed live from the latest BBA findings (see ProgramGuideService);
    this table only stores the manual override, if any.
    """
    __tablename__ = "engagement_program_module_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    program_type = Column(String(100), nullable=False)

    custom_order = Column(JSONB, nullable=True, comment="Advisor-set ordered array of module codes; may be partial")
    custom_order_set_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    custom_order_set_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    engagement = relationship("Engagement")


class EngagementModuleChecklistItem(Base):
    """
    Per-engagement tick-off state for a module's preparation checklist items.
    Schema only for now - no API/UI wired up yet; reserved for a future pass.
    """
    __tablename__ = "engagement_module_checklist_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    module_code = Column(String(20), nullable=False)
    checklist_item_key = Column(String(100), nullable=False, comment="Matches ProgramModuleContent.preparation_checklist[].key")

    is_checked = Column(Boolean, nullable=False, server_default='false')
    checked_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    checked_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', 'module_code', 'checklist_item_key', name='uq_engagement_module_checklist_item'),
    )
