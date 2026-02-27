"""merge bba_diagnostic_ctx and sw_diagnostic_ctx heads

Revision ID: merge_bba_sw_ctx
Revises: bba_diagnostic_ctx, sw_diagnostic_ctx
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_bba_sw_ctx'
down_revision = ('bba_diagnostic_ctx', 'sw_diagnostic_ctx')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration - no schema changes needed
    pass


def downgrade() -> None:
    # Merge migration - no schema changes needed
    pass
