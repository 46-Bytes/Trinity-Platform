"""add is_deleted to users

Revision ID: add_is_deleted_to_users
Revises: add_assigned_to_user_ids
Create Date: 2025-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_deleted_to_users'
down_revision = 'add_assigned_to_user_ids'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_deleted boolean column to users table
    op.add_column('users', 
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false',
                  comment='Whether the user has been soft deleted')
    )


def downgrade() -> None:
    # Remove is_deleted column
    op.drop_column('users', 'is_deleted')

