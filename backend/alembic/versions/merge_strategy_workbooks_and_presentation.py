"""merge strategy workbooks and bba stored files

Revision ID: merge_strategy_workbooks
Revises: add_strategy_workbooks, 1e095a9ba82f
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_strategy_workbooks'
down_revision = ('add_strategy_workbooks', '1e095a9ba82f')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both branches are now merged into one
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

