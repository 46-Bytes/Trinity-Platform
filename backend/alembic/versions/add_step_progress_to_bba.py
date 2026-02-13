"""add step progress to bba

Revision ID: add_step_progress_bba
Revises: merge_b7f4c3e1a2d8_add_read_by
Create Date: 2026-02-11 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_step_progress_bba'
down_revision = 'merge_b7f4c3e1a2d8_add_read_by'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add current_step column
    op.add_column(
        'bba',
        sa.Column(
            'current_step',
            sa.Integer(),
            nullable=True,
            comment='Current step the user is on (1-9)',
        ),
    )
    
    # Add max_step_reached column
    op.add_column(
        'bba',
        sa.Column(
            'max_step_reached',
            sa.Integer(),
            nullable=True,
            comment='Maximum step the user has reached (1-9)',
        ),
    )


def downgrade() -> None:
    op.drop_column('bba', 'max_step_reached')
    op.drop_column('bba', 'current_step')

