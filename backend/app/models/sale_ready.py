"""
Sale Ready program models: the stage, task and due diligence (DD) templates,
and each engagement's stage state and DD items.

The tables were created by add_sale_ready_program_tables and extended by
add_sale_ready_program_templates and add_sale_ready_engagement_state; the Sale
Planner and Close-out tables come from add_sale_ready_planner_closeout. These
classes mirror the schema those migrations produce, column for column,
including the legacy columns kept until a separately reviewed cleanup.

Allowed values for the String status/type columns live in
app/services/sale_ready_rules.py and are validated there, matching the rest of
app/models (no CheckConstraints). Tasks themselves live in `tasks` (see Task).
"""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


# ----------------------------------------------------------------------
# Templates - authored once per program, seeded from files/sale_ready/
# ----------------------------------------------------------------------
class ProgramStage(Base):
    """One of a program's stages: a phase before the modules, a module, or a phase after."""
    __tablename__ = "program_stage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    program_type = Column(String(100), nullable=False)
    stage_code = Column(String(30), nullable=False)
    stage_type = Column(String(20), nullable=False)
    default_order = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    display_code = Column(String(10), nullable=True,
                          comment="Code shown on the stage card: P1-P7 for phases, M1-M8 for modules")
    task_creation = Column(String(30), nullable=False, server_default='on_start',
                           comment="When template tasks are created: 'on_engagement_create' (phases) or 'on_start' (modules)")
    ui_variant = Column(String(30), nullable=True,
                        comment="Stage with its own screen: 'sale_planner', 'closeout', or NULL")
    # none_as_null: Python None must be SQL NULL, not a stored JSON 'null'.
    ui_config = Column(JSONB(none_as_null=True), nullable=True,
                       comment="Screen configuration, e.g. the Sale Planner's option lists and questions")

    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'stage_code', name='uq_program_stage_type_code'),
        Index('ix_program_stage_type_order', 'program_type', 'default_order'),
    )

    def __repr__(self):
        return f"<ProgramStage {self.program_type}/{self.stage_code}>"


class ProgramTaskTemplate(Base):
    """A preset task for a stage. Copied into `tasks` when the stage's tasks are created."""
    __tablename__ = "program_task_template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    program_type = Column(String(100), nullable=False)
    stage_code = Column(String(30), nullable=False)
    template_key = Column(String(100), nullable=False,
                          comment="Stable key within the stage, e.g. 'M1-MUST-03'; the seed upserts on it")
    section = Column(String(20), nullable=False)
    group_title = Column(String(255), nullable=True,
                         comment="Sub-group heading for phase tasks, e.g. 'Diagnostic Completion'")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, server_default='medium')
    default_order = Column(Integer, nullable=False, server_default='0')
    due_offset_days = Column(Integer, nullable=True)

    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'stage_code', 'template_key', name='uq_program_task_template_type_stage_key'),
        Index('ix_program_task_template_type_stage', 'program_type', 'stage_code'),
    )

    def __repr__(self):
        return f"<ProgramTaskTemplate {self.program_type}/{self.stage_code}/{self.template_key}>"


class ProgramDDTemplate(Base):
    """A due diligence checklist item. Copied into engagement_dd_item per engagement."""
    __tablename__ = "program_dd_template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    program_type = Column(String(100), nullable=False)
    item_key = Column(String(100), nullable=False, comment="Stable key for the checklist item, e.g. 'DD-029'")
    stage_code = Column(String(30), nullable=False,
                        comment="Stage the item belongs to: a module (M1-M8) or a phase (APPRAISAL, TRANSITION)")
    category_code = Column(String(10), nullable=False, comment="Category number, e.g. '3'")
    category = Column(String(255), nullable=False)
    sub_item_code = Column(String(10), nullable=False,
                           comment="Sub-item number, e.g. '3.1'; one Drive folder per sub-item later")
    sub_item = Column(Text, nullable=True)
    document_required = Column(Text, nullable=True)
    action_step = Column(Text, nullable=True)
    default_order = Column(Integer, nullable=False, server_default='0')

    is_active = Column(Boolean, nullable=False, server_default='true')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('program_type', 'item_key', name='uq_program_dd_template_type_item_key'),
        Index('ix_program_dd_template_type_stage', 'program_type', 'stage_code'),
    )

    def __repr__(self):
        return f"<ProgramDDTemplate {self.program_type}/{self.item_key}>"


# ----------------------------------------------------------------------
# Per-engagement state
# ----------------------------------------------------------------------
class EngagementStageState(Base):
    """
    One row per stage per engagement. `status` holds what the advisor did
    (not_started / started / completed); the displayed status is derived by
    sale_ready_rules.derive_stage_status.
    """
    __tablename__ = "engagement_stage_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    stage_code = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, server_default='not_started')
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    lead_advisor_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    started_at = Column(DateTime, nullable=True, comment="When the advisor started the stage")
    started_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_stage_state_started_by'),
        nullable=True, comment="Who started the stage",
    )
    completed_at = Column(DateTime, nullable=True, comment="When the advisor marked the stage complete")
    completed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_stage_state_completed_by'),
        nullable=True, comment="Who marked it complete (the impersonated user, if any)",
    )
    completed_by_original_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_stage_state_completed_by_original'),
        nullable=True, comment="The real user behind completed_by_user_id when an admin was impersonating",
    )

    # Legacy, unused: module order lives in engagement_program_module_state.
    # Kept until the reviewed cleanup migration drops it.
    priority_order = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', 'stage_code', name='uq_engagement_stage_state'),
    )

    def __repr__(self):
        return f"<EngagementStageState {self.engagement_id} {self.stage_code} {self.status}>"


class EngagementDDItem(Base):
    """
    An engagement's copy of one DD checklist item: one record, shown in both the
    stage view and the master checklist. `status` NULL means no status yet.
    """
    __tablename__ = "engagement_dd_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True)
    template_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey('program_dd_template.id', ondelete='RESTRICT', name='fk_engagement_dd_item_template_item'),
        nullable=False, comment="Checklist template row this item was copied from",
    )

    # Copied from the template when the engagement's checklist is created.
    item_key = Column(String(100), nullable=False, comment="Copied from the template, e.g. 'DD-029'")
    stage_code = Column(String(30), nullable=False, index=True)
    category_code = Column(String(10), nullable=False, comment="Copied from the template, e.g. '3'")
    category = Column(String(255), nullable=False)
    sub_item_code = Column(String(10), nullable=False, comment="Copied from the template, e.g. '3.1'")
    sub_item = Column(Text, nullable=True)
    document_required = Column(Text, nullable=True)
    action_step = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, server_default='0')

    status = Column(String(20), nullable=True,
                    comment="NULL (no status yet), 'yes', 'in_progress', 'no' or 'not_applicable'")
    status_changed_at = Column(DateTime, nullable=True, comment="When status last changed")
    status_changed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_dd_item_status_changed_by'),
        nullable=True, comment="Who last changed status",
    )
    date_completed = Column(Date, nullable=True)
    gap_handling = Column(String(20), nullable=True,
                          comment="For a gap (status 'no'): 'fix', 'disclose' or 'refer'; NULL = not yet decided")
    flag_for_m8 = Column(Boolean, nullable=False, server_default='false',
                         comment="Flagged for re-review at Due Diligence Preparation")
    responsible_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = Column(Text, nullable=True)

    # Legacy, unused: `completed` is superseded by `status`; media_id and
    # file_link wait on the Drive decision. Kept until the reviewed cleanup.
    completed = Column(Boolean, nullable=False, server_default='false')
    media_id = Column(UUID(as_uuid=True), ForeignKey('media.id', ondelete='SET NULL'), nullable=True)
    file_link = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', 'template_item_id', name='uq_engagement_dd_item_engagement_template'),
        Index('ix_engagement_dd_item_eng_stage', 'engagement_id', 'stage_code'),
        Index('ix_engagement_dd_item_engagement_status', 'engagement_id', 'status'),
    )

    def __repr__(self):
        return f"<EngagementDDItem {self.engagement_id} {self.item_key} {self.status}>"


# ----------------------------------------------------------------------
# Screens with their own data - created by add_sale_ready_planner_closeout
# ----------------------------------------------------------------------
class EngagementSalePlanner(Base):
    """
    The Sale Planner stage's decisions, one row per engagement. Answers are keyed
    by the stable keys in the stage's ui_config, so relabelling keeps them.
    """
    __tablename__ = "engagement_sale_planner"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagements.id', ondelete='CASCADE', name='fk_engagement_sale_planner_engagement'),
        nullable=False,
    )
    sale_type = Column(String(30), nullable=True,
                       comment="A sale_types key from the Sale Planner stage's ui_config, e.g. 'share_sale'")
    # none_as_null: Python None becomes SQL NULL, so NOT NULL rejects it
    # instead of storing a JSON 'null'.
    sale_structures = Column(JSONB(none_as_null=True), nullable=False, default=list,
                             server_default=text("'[]'::jsonb"),
                             comment='Structure keys being considered, e.g. ["cash_purchase", "earn_out"]')
    value_propositions = Column(JSONB(none_as_null=True), nullable=False, default=dict,
                                server_default=text("'{}'::jsonb"),
                                comment="Value analysis per structure: {structure_key: text}")
    marketing_answers = Column(JSONB(none_as_null=True), nullable=False, default=dict,
                               server_default=text("'{}'::jsonb"),
                               comment="Marketing plan answers: {question_key: text}")
    issues = Column(JSONB(none_as_null=True), nullable=False, default=dict,
                    server_default=text("'{}'::jsonb"),
                    comment='Issues to address: {issue_key: {"addressed": bool, "note": text}}')
    updated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_sale_planner_updated_by'),
        nullable=True, comment="Who last changed the planner",
    )

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', name='uq_engagement_sale_planner_engagement'),
    )

    def __repr__(self):
        return f"<EngagementSalePlanner {self.engagement_id}>"


class EngagementProgramCloseout(Base):
    """
    The Close-out stage's decisions and who closed the program, one row per
    engagement. closed_at NULL means the program is still open.
    """
    __tablename__ = "engagement_program_closeout"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey('engagements.id', ondelete='CASCADE', name='fk_engagement_program_closeout_engagement'),
        nullable=False,
    )
    fresh_appraisal_required = Column(Boolean, nullable=False, server_default=text('false'),
                                      comment="A fresh appraisal is required before listing")
    referred_to_benchmark = Column(Boolean, nullable=False, server_default=text('false'),
                                   comment="Client referred to Benchmark Business Sales for listing")
    ongoing_assistance = Column(Text, nullable=True, comment="The ongoing assistance agreed, if any")

    closed_at = Column(DateTime, nullable=True, comment="When the program was closed; NULL while open")
    closed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_program_closeout_closed_by'),
        nullable=True, comment="Who closed the program (the impersonated user, if any)",
    )
    closed_by_original_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL', name='fk_engagement_program_closeout_closed_by_original'),
        nullable=True, comment="The real user behind closed_by_user_id when an admin was impersonating",
    )

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('engagement_id', name='uq_engagement_program_closeout_engagement'),
    )

    def __repr__(self):
        return f"<EngagementProgramCloseout {self.engagement_id} closed={self.closed_at is not None}>"
