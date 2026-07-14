"""add help_video_categories and help_videos tables

Revision ID: add_help_videos_tables
Revises: partial_email_idx
Create Date: 2026-07-14

Creates the Help / Video User Guide tables: admin-managed categories and the
YouTube videos that belong to them (storing only the extracted video ID).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_help_videos_tables'
down_revision = 'partial_email_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'help_video_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_help_video_categories_position'), 'help_video_categories', ['position'])

    op.create_table(
        'help_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('youtube_video_id', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['help_video_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_help_videos_category_id'), 'help_videos', ['category_id'])
    op.create_index(op.f('ix_help_videos_created_by_user_id'), 'help_videos', ['created_by_user_id'])
    op.create_index(op.f('ix_help_videos_position'), 'help_videos', ['position'])


def downgrade() -> None:
    op.drop_index(op.f('ix_help_videos_position'), table_name='help_videos')
    op.drop_index(op.f('ix_help_videos_created_by_user_id'), table_name='help_videos')
    op.drop_index(op.f('ix_help_videos_category_id'), table_name='help_videos')
    op.drop_table('help_videos')

    op.drop_index(op.f('ix_help_video_categories_position'), table_name='help_video_categories')
    op.drop_table('help_video_categories')
