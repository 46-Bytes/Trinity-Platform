"""merge heads b7f4c3e1a2d8 and add_read_by_to_notes

Revision ID: merge_b7f4c3e1a2d8_add_read_by
Revises: b7f4c3e1a2d8, add_read_by_to_notes
Create Date: 2026-02-11 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_b7f4c3e1a2d8_add_read_by'
down_revision = ('b7f4c3e1a2d8', 'add_read_by_to_notes')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration - no schema changes needed
    # Both branches have already been applied
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes needed
    pass

