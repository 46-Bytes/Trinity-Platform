"""add drive_file_id to strategy_workbook

Revision ID: a86594b81fbd
Revises: add_sbp_table
Create Date: 2026-04-21 16:24:13.391326

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a86594b81fbd'
down_revision = 'add_sbp_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('strategy_workbooks', sa.Column('drive_file_id', sa.Text(), nullable=True, comment='Google Drive file ID for the generated workbook'))


def downgrade() -> None:
    op.drop_column('strategy_workbooks', 'drive_file_id')
