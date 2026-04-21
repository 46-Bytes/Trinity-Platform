"""Add google_drive_file_id to media table

Revision ID: add_google_drive_file_id
Revises: add_llm_provider_fields
Create Date: 2026-03-30

Adds google_drive_file_id column for Google Drive cloud backup integration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_google_drive_file_id'
down_revision = 'add_llm_provider_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('media', sa.Column('google_drive_file_id', sa.String(255), nullable=True,
                                     comment='Google Drive file ID for cloud backup'))
    op.create_index('ix_media_google_drive_file_id', 'media', ['google_drive_file_id'])


def downgrade():
    op.drop_index('ix_media_google_drive_file_id', table_name='media')
    op.drop_column('media', 'google_drive_file_id')
