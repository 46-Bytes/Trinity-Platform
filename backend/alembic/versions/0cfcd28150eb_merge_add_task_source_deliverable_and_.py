"""merge add_task_source_deliverable and merge_roles_matrix_deliverables heads

Revision ID: 0cfcd28150eb
Revises: add_task_source_deliverable, merge_roles_matrix_deliverables
Create Date: 2026-08-29 00:32:26.731528

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0cfcd28150eb'
down_revision = ('add_task_source_deliverable', 'merge_roles_matrix_deliverables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass



