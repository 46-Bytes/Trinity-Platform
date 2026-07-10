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
    Client-authored content for a single module card (purpose, preparation
    checklist, recommended tools, deliverables). Scoped by program_type so
    the same table can serve multiple module-based programs.
    """
    __tablename__ = "program_module_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

    program_type = Column(String(100), nullable=False, comment="e.g. 'value_builder' - matches Engagement.tool")
    module_code = Column(String(20), nullable=False, comment="e.g. 'M0', 'V1'..'V11', 'M12'")
    display_order = Column(Integer, nullable=False, comment="Default/author-defined sequence for this module")

    title = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=True, comment="One-paragraph summary of what this module achieves")
    preparation_checklist = Column(JSONB, nullable=True, comment="[{key, text}] static preparation items")
    recommended_tools = Column(JSONB, nullable=True, comment="[{tool_key, label}] Trinity tools to run for this module")
    deliverables = Column(JSONB, nullable=True, comment="[label, ...] static deliverable labels")

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
            "purpose": self.purpose,
            "preparation_checklist": self.preparation_checklist,
            "recommended_tools": self.recommended_tools,
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)

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
