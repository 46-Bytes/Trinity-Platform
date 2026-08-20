"""add source_deliverable_id to tasks

Part A: an advisor clicks "Create tasks" on a module and one task is created per
deliverable. Nothing is automatic, one deliverable may carry several tasks, and
task state never touches deliverable state.

The column is a plain nullable UUID with no foreign key, deliberately. The id it
holds is the same polymorphic address the deliverables API uses - the LIBRARY id
for a preset (an untouched preset has no instance row, so it has no instance id)
and the INSTANCE id for an advisor-added deliverable. That is two tables, so no
single FK can express it.

The absence of a constraint is also what makes the Part A rule hold: scoping a
deliverable out, or removing an advisor-added one, leaves its tasks standing.
EngagementModuleDeliverable.library_deliverable_id is ondelete='CASCADE', so an
FK here would have deleted a client's tasks the first time a preset was retired.

Indexed because the deliverables read counts tasks per deliverable on every
fetch.

Written with inspector guards to match add_card_tables_and_deliverable_session,
because several environments have drifted from the migration history.

Revision ID: add_task_source_deliverable
Revises: add_tables_and_session
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_task_source_deliverable'
down_revision = 'add_tables_and_session'
branch_labels = None
depends_on = None

_TABLE = 'tasks'
_COLUMN = 'source_deliverable_id'
_INDEX = 'ix_tasks_source_deliverable_id'
_COMMENT = (
    "Deliverable this task was generated from. Polymorphic and unconstrained: the library id "
    "for a preset, the instance id for an advisor-added deliverable. No FK, so tasks survive "
    "their deliverable being scoped out, removed or retired"
)


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


def upgrade() -> None:
    if _offline() or not _has_column(_TABLE, _COLUMN):
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, UUID(as_uuid=True), nullable=True, comment=_COMMENT),
        )
    if _offline() or not _has_index(_TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    if _offline() or _has_index(_TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _offline() or _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
