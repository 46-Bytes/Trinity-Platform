"""add assigned_to_user_ids to tasks

Revision ID: add_assigned_to_user_ids
Revises: af13aec12199
Create Date: 2025-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID


# revision identifiers, used by Alembic.
revision = 'add_assigned_to_user_ids'
down_revision = 'af13aec12199'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add assigned_to_user_ids array column to tasks table
    op.add_column('tasks', 
        sa.Column('assigned_to_user_ids', ARRAY(UUID(as_uuid=True)), nullable=True, 
                  comment='Array of user IDs assigned to this task (for multiple assignments, e.g., all advisors in engagement)')
    )
    # Create index for better query performance
    op.create_index('ix_tasks_assigned_to_user_ids', 'tasks', ['assigned_to_user_ids'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    # Remove index first
    op.drop_index('ix_tasks_assigned_to_user_ids', table_name='tasks', postgresql_using='gin')
    # Remove column
    op.drop_column('tasks', 'assigned_to_user_ids')

