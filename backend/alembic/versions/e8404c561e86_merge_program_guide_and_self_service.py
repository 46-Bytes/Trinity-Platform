"""merge program guide and self service

Revision ID: e8404c561e86
Revises: add_program_guide_tables, f7a1b2c3d4e5
Create Date: 2026-07-29 15:02:21.652045

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8404c561e86'
down_revision = ('add_program_guide_tables', 'f7a1b2c3d4e5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass



