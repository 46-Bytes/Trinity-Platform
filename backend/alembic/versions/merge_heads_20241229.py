"""merge heads

Revision ID: merge_heads_20241229
Revises: e3edf1331520, 5f73818377e1
Create Date: 2025-12-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_20241229'
down_revision = ('e3edf1331520', '5f73818377e1')  # Merge both heads - tuple format for merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both migrations have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

