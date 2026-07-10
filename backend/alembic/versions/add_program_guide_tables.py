"""add program guide tables

Revision ID: add_program_guide_tables
Revises: 45bdcc478ace
Create Date: 2026-07-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'add_program_guide_tables'
down_revision = '45bdcc478ace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'program_module_content',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('module_code', sa.String(20), nullable=False),
        sa.Column('display_order', sa.Integer, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('purpose', sa.Text, nullable=True),
        sa.Column('preparation_checklist', JSONB, nullable=True),
        sa.Column('recommended_tools', JSONB, nullable=True),
        sa.Column('deliverables', JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('program_type', 'module_code', name='uq_program_module_content_type_code'),
    )
    op.create_index(
        'ix_program_module_content_type_order',
        'program_module_content',
        ['program_type', 'display_order'],
    )

    op.create_table(
        'engagement_program_module_state',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('custom_order', JSONB, nullable=True),
        sa.Column('custom_order_set_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('custom_order_set_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        'engagement_module_checklist_item',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('module_code', sa.String(20), nullable=False),
        sa.Column('checklist_item_key', sa.String(100), nullable=False),
        sa.Column('is_checked', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('checked_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('checked_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('engagement_id', 'module_code', 'checklist_item_key', name='uq_engagement_module_checklist_item'),
    )


def downgrade() -> None:
    op.drop_table('engagement_module_checklist_item')
    op.drop_table('engagement_program_module_state')
    op.drop_index('ix_program_module_content_type_order', table_name='program_module_content')
    op.drop_table('program_module_content')
