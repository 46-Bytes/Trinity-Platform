"""merge all current heads

Revision ID: merge_all_current_heads
Revises: fix_subscription_cols, 7a0c72f39586
Create Date: 2025-01-15 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_current_heads'
down_revision = ('fix_subscription_cols', '7a0c72f39586')  # Merge all current heads
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both branches have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass


