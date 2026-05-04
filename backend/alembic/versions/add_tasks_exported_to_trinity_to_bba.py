"""add tasks_exported_to_trinity to bba

Revision ID: add_tasks_exported_to_trinity
Revises: add_business_name_to_users
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_tasks_exported_to_trinity'
down_revision = 'add_business_name_to_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'bba',
        sa.Column(
            'tasks_exported_to_trinity',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Whether task planner tasks have been exported to Trinity Tasks at least once',
        ),
    )


def downgrade() -> None:
    op.drop_column('bba', 'tasks_exported_to_trinity')
