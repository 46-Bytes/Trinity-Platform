"""add is_deleted to child models

Revision ID: add_is_deleted_to_child_models
Revises: add_employee_plan_to_sbp
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_is_deleted_to_child_models'
down_revision = 'add_employee_plan_to_sbp'
branch_labels = None
depends_on = None

TABLES = [
    'diagnostics',
    'tasks',
    'notes',
    'conversations',
    'messages',
    'advisor_client',
    'bba',
    'strategy_workbooks',
    'strategic_business_plans',
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in TABLES:
        columns = [col['name'] for col in inspector.get_columns(table)]
        if 'is_deleted' not in columns:
            op.add_column(
                table,
                sa.Column(
                    'is_deleted',
                    sa.Boolean(),
                    nullable=False,
                    server_default='false',
                    comment='Whether this record has been soft deleted',
                ),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in TABLES:
        columns = [col['name'] for col in inspector.get_columns(table)]
        if 'is_deleted' in columns:
            op.drop_column(table, 'is_deleted')
