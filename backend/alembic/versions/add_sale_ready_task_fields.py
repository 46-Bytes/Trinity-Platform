"""add Sale Ready template link and notes to tasks

Revision ID: add_sale_ready_task_fields
Revises: add_sale_ready_engagement_state
Create Date: 2026-09-18

Migration C of three for the Sale Ready program. Sale Ready tasks live in the
existing tasks table, as the brief requires. The stage goes in module_reference
and the must-do / optional / client-specific group in section; both columns
already exist, so this only adds:

- source_task_template_id: the template a task was created from, so "Start
  module" can create each template's task once, however often it is clicked.
- notes: the per-task notes the program sheet and mockup both carry.

The one table here with live data. Both columns are nullable with no default,
so Postgres adds them without rewriting rows; every existing task keeps NULL
in both. The partial unique index only covers rows with a template link, so
no existing row can conflict with it. Value Builder deliverable tasks and
diagnostic tasks never read either column.

source_task_template_id has an FK, unlike source_deliverable_id: it points at
one table, and ON DELETE SET NULL means even a hard-deleted template only
unlinks its tasks. Templates are retired with is_active, never deleted.

The two indexes are built with a plain CREATE INDEX, which briefly blocks
writes to tasks. If staging's tasks table is large, build them CONCURRENTLY
in an autocommit block instead.

Downgrade drops both indexes, the FK and both columns. Notes written after the
upgrade are lost; the tasks themselves are untouched.

Written with inspector guards to match add_media_engagement_id, because several
environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_task_fields'
down_revision = 'add_sale_ready_engagement_state'
branch_labels = None
depends_on = None

_TABLE = 'tasks'
_TEMPLATE_COLUMN = 'source_task_template_id'
_NOTES_COLUMN = 'notes'
_FK = 'fk_tasks_source_task_template'
_REFERRED_TABLE = 'program_task_template'
_UNIQUE_INDEX = 'uq_tasks_engagement_source_template'
_GROUP_INDEX = 'ix_tasks_engagement_module_section'


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guards below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _has_column(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return name in {c['name'] for c in inspector.get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return name in {i['name'] for i in inspector.get_indexes(table)}


def _foreign_key_name(table: str, column: str, referred_table: str, referred_column: str = 'id'):
    """
    Name of the existing FK from `column` to referred_table.referred_column.
    All three must match, so an unrelated FK on the same column is not taken for
    this one; matching by target rather than name still finds a drifted name.
    """
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return None
    for fk in inspector.get_foreign_keys(table):
        if (
            fk.get('constrained_columns') == [column]
            and fk.get('referred_table') == referred_table
            and fk.get('referred_columns') == [referred_column]
        ):
            return fk.get('name')
    return None


def upgrade() -> None:
    if _offline() or not _has_column(_TABLE, _TEMPLATE_COLUMN):
        op.add_column(_TABLE, sa.Column(
            _TEMPLATE_COLUMN, UUID(as_uuid=True), nullable=True,
            comment="Sale Ready task template this task was created from; NULL for every other task",
        ))
    if _offline() or not _has_column(_TABLE, _NOTES_COLUMN):
        op.add_column(_TABLE, sa.Column(
            _NOTES_COLUMN, sa.Text(), nullable=True, comment="Free-text notes on the task",
        ))

    if _offline() or _foreign_key_name(_TABLE, _TEMPLATE_COLUMN, _REFERRED_TABLE) is None:
        op.create_foreign_key(
            _FK, _TABLE, _REFERRED_TABLE, [_TEMPLATE_COLUMN], ['id'], ondelete='SET NULL',
        )

    # One live task per template per engagement. Soft-deleted tasks fall out of
    # the index, so deleting a template task lets "Start" recreate it.
    if _offline() or not _has_index(_TABLE, _UNIQUE_INDEX):
        op.create_index(
            _UNIQUE_INDEX, _TABLE, ['engagement_id', _TEMPLATE_COLUMN], unique=True,
            postgresql_where=sa.text(f'{_TEMPLATE_COLUMN} IS NOT NULL AND is_deleted = false'),
        )

    # The stage view lists an engagement's tasks by stage and group.
    if _offline() or not _has_index(_TABLE, _GROUP_INDEX):
        op.create_index(_GROUP_INDEX, _TABLE, ['engagement_id', 'module_reference', 'section'])


def downgrade() -> None:
    if _offline() or _has_index(_TABLE, _GROUP_INDEX):
        op.drop_index(_GROUP_INDEX, table_name=_TABLE)
    if _offline() or _has_index(_TABLE, _UNIQUE_INDEX):
        op.drop_index(_UNIQUE_INDEX, table_name=_TABLE)

    if _offline():
        op.drop_constraint(_FK, _TABLE, type_='foreignkey')
    else:
        existing = _foreign_key_name(_TABLE, _TEMPLATE_COLUMN, _REFERRED_TABLE)
        if existing:
            op.drop_constraint(existing, _TABLE, type_='foreignkey')

    if _offline() or _has_column(_TABLE, _NOTES_COLUMN):
        op.drop_column(_TABLE, _NOTES_COLUMN)
    if _offline() or _has_column(_TABLE, _TEMPLATE_COLUMN):
        op.drop_column(_TABLE, _TEMPLATE_COLUMN)
