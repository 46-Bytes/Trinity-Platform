"""add presentation slides column

Revision ID: b7f4c3e1a2d8
Revises: a8d3b2d2caf9
Create Date: 2026-02-11 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b7f4c3e1a2d8'
down_revision = 'a8d3b2d2caf9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'bba',
        sa.Column(
            'presentation_slides',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                'Phase 3 presentation slide content. Contains a slides array '
                'with typed slide objects (title, executive_summary, structure, '
                'recommendation, timeline, next_steps) each with an approved flag.'
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column('bba', 'presentation_slides')
