"""merge program deliverable and sale ready heads

Two feature branches both descend from add_program_guide_tables:
  - add_program_deliverable_tables  (Value Builder deliverables)
  - add_sale_ready_program_tables   (Sale Ready program)

They are independent - different tables, no shared columns - so this is a plain
merge point with nothing to do. It exists so a database that has been migrated
along either branch can reach a single head.

Revision ID: merge_deliverable_sale_ready
Revises: add_program_deliverable_tables, add_sale_ready_program_tables
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_deliverable_sale_ready'
down_revision = ('add_program_deliverable_tables', 'add_sale_ready_program_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
