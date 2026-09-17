"""merge roles matrix and pd scorecard with program deliverables

Revision ID: merge_roles_matrix_deliverables
Revises: add_program_deliverable_tables, drop_redundant_uniques
Create Date: 2026-08-27 17:05:32.601311

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_roles_matrix_deliverables'
down_revision = ('add_program_deliverable_tables', 'drop_redundant_uniques')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass



