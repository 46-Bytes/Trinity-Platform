"""add exclude_sale_readiness and draft_findings_edited to bba

Revision ID: add_bba_sale_ready_flags
Revises: add_tasks_exported_to_trinity
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_bba_sale_ready_flags'
down_revision = 'add_tasks_exported_to_trinity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bba')]

    if 'exclude_sale_readiness' not in columns:
        op.add_column(
            'bba',
            sa.Column(
                'exclude_sale_readiness',
                sa.Boolean(),
                nullable=False,
                server_default='false',
                comment='Whether to exclude sale-readiness from analysis',
            ),
        )

    if 'draft_findings_edited' not in columns:
        op.add_column(
            'bba',
            sa.Column(
                'draft_findings_edited',
                sa.Boolean(),
                nullable=False,
                server_default='false',
                comment='Whether user has edited draft findings',
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('bba')]

    if 'draft_findings_edited' in columns:
        op.drop_column('bba', 'draft_findings_edited')
    if 'exclude_sale_readiness' in columns:
        op.drop_column('bba', 'exclude_sale_readiness')
