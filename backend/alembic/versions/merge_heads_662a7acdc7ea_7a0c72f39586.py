"""merge heads 662a7acdc7ea and 7a0c72f39586

Revision ID: a1b2c3d4e5f6
Revises: 662a7acdc7ea, 7a0c72f39586
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = ('662a7acdc7ea', '7a0c72f39586')
# This merge migration combines the two branch heads
# Next migration: create_firms_subs (creates firms and subscriptions tables)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both branches have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

