"""add_task_id_to_notes

Revision ID: 8c5d89835db8
Revises: 4ff8aece5340
Create Date: 2025-12-11 15:24:16.480255

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c5d89835db8'
down_revision = '4ff8aece5340'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add task_id column to notes table
    op.add_column('notes', sa.Column('task_id', sa.UUID(), nullable=True, comment='Optional: if note references a task'))
    op.create_index(op.f('ix_notes_task_id'), 'notes', ['task_id'], unique=False)
    op.create_foreign_key('fk_notes_task_id', 'notes', 'tasks', ['task_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Remove task_id column from notes table
    op.drop_constraint('fk_notes_task_id', 'notes', type_='foreignkey')
    op.drop_index(op.f('ix_notes_task_id'), table_name='notes')
    op.drop_column('notes', 'task_id')



