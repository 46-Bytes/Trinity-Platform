"""add business_name to users

Revision ID: add_business_name_to_users
Revises: add_sbp_table
Create Date: 2026-04-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_business_name_to_users'
down_revision = 'a86594b81fbd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('business_name', sa.String(255), nullable=True, comment="Client's business name"))


def downgrade() -> None:
    op.drop_column('users', 'business_name')
