"""add employee_plan to strategic_business_plans

Revision ID: add_employee_plan_to_sbp
Revises: add_bba_sale_ready_flags
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_employee_plan_to_sbp'
down_revision = 'add_bba_sale_ready_flags'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('strategic_business_plans')]

    if 'employee_plan' not in columns:
        op.add_column(
            'strategic_business_plans',
            sa.Column(
                'employee_plan',
                JSONB,
                nullable=True,
                comment='Advisor-edited employee document: {sections: [{key, title, content, included}]}',
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('strategic_business_plans')]

    if 'employee_plan' in columns:
        op.drop_column('strategic_business_plans', 'employee_plan')
