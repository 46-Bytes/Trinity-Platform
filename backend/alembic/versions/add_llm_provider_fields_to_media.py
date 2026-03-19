"""Add generic LLM provider fields to media table

Revision ID: 9267fb9f2c3b
Revises: f227a49caf86
Create Date: 2026-03-18

Adds llm_file_id, llm_provider, and llm_uploaded_at columns
to support provider-agnostic LLM file storage (Claude, OpenAI, etc.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9267fb9f2c3b'
down_revision = 'f227a49caf86'
branch_labels = None
depends_on = None


def upgrade():
    # Add generic LLM columns
    op.add_column('media', sa.Column('llm_file_id', sa.String(255), nullable=True))
    op.add_column('media', sa.Column('llm_provider', sa.String(50), nullable=True))
    op.add_column('media', sa.Column('llm_uploaded_at', sa.DateTime, nullable=True))
    op.create_index('ix_media_llm_file_id', 'media', ['llm_file_id'])

    # Backfill: copy existing OpenAI data to new generic columns
    op.execute("""
        UPDATE media
        SET llm_file_id = openai_file_id,
            llm_provider = 'openai',
            llm_uploaded_at = openai_uploaded_at
        WHERE openai_file_id IS NOT NULL
    """)


def downgrade():
    op.drop_index('ix_media_llm_file_id', table_name='media')
    op.drop_column('media', 'llm_uploaded_at')
    op.drop_column('media', 'llm_provider')
    op.drop_column('media', 'llm_file_id')
