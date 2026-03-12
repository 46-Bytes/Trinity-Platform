"""Add dual provider file ID columns (openai + anthropic)

Revision ID: rename_openai_to_llm
Revises: f227a49caf86
Create Date: 2026-03-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'rename_openai_to_llm'
down_revision = 'f227a49caf86'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename openai_file_id -> anthropic_file_id (existing data was uploaded to Anthropic)
    op.alter_column('media', 'openai_file_id', new_column_name='anthropic_file_id')
    op.alter_column('media', 'openai_purpose', new_column_name='llm_purpose')
    op.alter_column('media', 'openai_uploaded_at', new_column_name='anthropic_uploaded_at')

    # Replace old index with provider-specific index
    op.drop_index('ix_media_openai_file_id', table_name='media')
    op.create_index('ix_media_anthropic_file_id', 'media', ['anthropic_file_id'], unique=True)

    # Add OpenAI columns (empty for now, populated when provider is switched to OpenAI)
    op.add_column('media', sa.Column('openai_file_id', sa.String(255), nullable=True))
    op.add_column('media', sa.Column('openai_uploaded_at', sa.DateTime(), nullable=True))
    op.create_index('ix_media_openai_file_id', 'media', ['openai_file_id'], unique=True)


def downgrade() -> None:
    # Drop OpenAI columns
    op.drop_index('ix_media_openai_file_id', table_name='media')
    op.drop_column('media', 'openai_uploaded_at')
    op.drop_column('media', 'openai_file_id')

    # Rename back to original openai_* columns
    op.drop_index('ix_media_anthropic_file_id', table_name='media')
    op.alter_column('media', 'anthropic_file_id', new_column_name='openai_file_id')
    op.alter_column('media', 'llm_purpose', new_column_name='openai_purpose')
    op.alter_column('media', 'anthropic_uploaded_at', new_column_name='openai_uploaded_at')
    op.create_index('ix_media_openai_file_id', 'media', ['openai_file_id'], unique=True)
