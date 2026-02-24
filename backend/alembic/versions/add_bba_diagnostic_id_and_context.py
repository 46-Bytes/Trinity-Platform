"""add diagnostic_id and diagnostic_context to bba

Revision ID: bba_diagnostic_ctx
Revises: add_step_progress_bba
Create Date: 2026-02-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'bba_diagnostic_ctx'
down_revision = '1e095a9ba82f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'bba',
        sa.Column(
            'diagnostic_id',
            UUID(as_uuid=True),
            sa.ForeignKey('diagnostics.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
            comment='When created from a completed diagnostic, link to that diagnostic',
        ),
    )
    op.add_column(
        'bba',
        sa.Column(
            'diagnostic_context',
            JSONB(),
            nullable=True,
            comment='Diagnostic report/summary used as context (e.g. report_html or ai_analysis subset)',
        ),
    )


def downgrade() -> None:
    op.drop_column('bba', 'diagnostic_context')
    op.drop_column('bba', 'diagnostic_id')
