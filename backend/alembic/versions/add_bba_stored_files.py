"""add bba stored_files column for persisted uploads

Revision ID: add_bba_stored_files
Revises: add_step_progress_bba
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_bba_stored_files'
down_revision = 'add_step_progress_bba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'bba',
        sa.Column(
            'stored_files',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Mapping of filename to relative storage path for persisted uploads: {'doc.pdf': 'project_id/doc.pdf'}"
        )
    )


def downgrade() -> None:
    op.drop_column('bba', 'stored_files')
