"""add celery_task_id to diagnostics

Revision ID: 1902d32c0ce6
Revises: 103dd474bf97
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1902d32c0ce6'
down_revision = '103dd474bf97'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('diagnostics', sa.Column('celery_task_id', sa.String(255), nullable=True,
                                           comment='Celery task ID for cancellation/tracking'))


def downgrade() -> None:
    op.drop_column('diagnostics', 'celery_task_id')
