"""add sale ready program tables

Revision ID: add_sale_ready_program_tables
Revises: add_program_guide_tables
Create Date: 2026-07-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_program_tables'
down_revision = 'add_program_guide_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- Shared tasks table: section tag for program grouping ----
    op.add_column('tasks', sa.Column('section', sa.String(20), nullable=True))

    # ---- Template tables ----
    op.create_table(
        'program_stage',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('stage_code', sa.String(30), nullable=False),
        sa.Column('stage_type', sa.String(20), nullable=False),
        sa.Column('default_order', sa.Integer, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('program_type', 'stage_code', name='uq_program_stage_type_code'),
    )
    op.create_index('ix_program_stage_type_order', 'program_stage', ['program_type', 'default_order'])

    op.create_table(
        'program_task_template',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('stage_code', sa.String(30), nullable=False),
        sa.Column('section', sa.String(20), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('default_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('due_offset_days', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_program_task_template_type_stage', 'program_task_template', ['program_type', 'stage_code'])

    op.create_table(
        'program_dd_template',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('module_code', sa.String(30), nullable=False),
        sa.Column('category', sa.String(255), nullable=False),
        sa.Column('sub_item', sa.Text, nullable=True),
        sa.Column('document_required', sa.Text, nullable=True),
        sa.Column('action_step', sa.Text, nullable=True),
        sa.Column('default_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_program_dd_template_type_module', 'program_dd_template', ['program_type', 'module_code'])

    # ---- Runtime state tables ----
    op.create_table(
        'engagement_stage_state',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('stage_code', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='not_started'),
        sa.Column('start_date', sa.Date, nullable=True),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('lead_advisor_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority_order', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('engagement_id', 'stage_code', name='uq_engagement_stage_state'),
    )

    op.create_table(
        'engagement_dd_item',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('module_code', sa.String(30), nullable=False, index=True),
        sa.Column('category', sa.String(255), nullable=False),
        sa.Column('sub_item', sa.Text, nullable=True),
        sa.Column('document_required', sa.Text, nullable=True),
        sa.Column('action_step', sa.Text, nullable=True),
        sa.Column('responsible_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('completed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('date_completed', sa.Date, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('media_id', UUID(as_uuid=True), sa.ForeignKey('media.id', ondelete='SET NULL'), nullable=True),
        sa.Column('file_link', sa.Text, nullable=True),
        sa.Column('display_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_engagement_dd_item_eng_module', 'engagement_dd_item', ['engagement_id', 'module_code'])

    op.create_table(
        'engagement_document_register_entry',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('stage_code', sa.String(30), nullable=False, index=True),
        sa.Column('document_name', sa.String(255), nullable=False),
        sa.Column('creation_date', sa.Date, nullable=True),
        sa.Column('document_id', sa.String(255), nullable=True),
        sa.Column('renewal_date', sa.Date, nullable=True),
        sa.Column('renewal_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('media_id', UUID(as_uuid=True), sa.ForeignKey('media.id', ondelete='SET NULL'), nullable=True),
        sa.Column('file_link', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_engagement_doc_register_eng_stage', 'engagement_document_register_entry', ['engagement_id', 'stage_code'])


def downgrade() -> None:
    op.drop_index('ix_engagement_doc_register_eng_stage', table_name='engagement_document_register_entry')
    op.drop_table('engagement_document_register_entry')
    op.drop_index('ix_engagement_dd_item_eng_module', table_name='engagement_dd_item')
    op.drop_table('engagement_dd_item')
    op.drop_table('engagement_stage_state')
    op.drop_index('ix_program_dd_template_type_module', table_name='program_dd_template')
    op.drop_table('program_dd_template')
    op.drop_index('ix_program_task_template_type_stage', table_name='program_task_template')
    op.drop_table('program_task_template')
    op.drop_index('ix_program_stage_type_order', table_name='program_stage')
    op.drop_table('program_stage')
    op.drop_column('tasks', 'section')
