"""add is_deleted

Revision ID: d7ffe8426a29
Revises: add_is_deleted_to_users
Create Date: 2026-02-04 16:50:25.547373

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7ffe8426a29'
down_revision = 'add_is_deleted_to_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_deleted boolean column to engagements table for soft delete
    op.add_column(
        'engagements',
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Whether the engagement has been soft deleted',
        ),
    )


def downgrade() -> None:
    # Remove is_deleted column from engagements table
    op.drop_column('engagements', 'is_deleted')



