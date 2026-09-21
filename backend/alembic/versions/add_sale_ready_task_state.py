"""add Sale Ready per-task state (N/A, blocked)

Revision ID: add_sale_ready_task_state
Revises: add_sale_ready_planner_closeout
Create Date: 2026-09-21

The Sale Ready mockup cycles a task through done, not required (N/A) and
blocked. The client confirmed those two extra states are wanted for Sale Ready
only, never globally (C7), so they are NOT added to `tasks.status`: that column
is shared with diagnostics, Value Builder deliverables and the engagement Tasks
tab, whose counters and badges know exactly four values.

Instead one nullable column carries the Sale Ready state alongside the existing
status:

    NULL              ordinary task; `status` means what it always meant
    'not_applicable'  marked not required - counts as resolved for stage QA
    'blocked'         cannot proceed - counts as OPEN for stage QA

`status` keeps its own meaning throughout, so a task marked not applicable stays
'pending' for every non-Sale Ready reader and nothing outside Sale Ready changes
behaviour. Allowed values are validated in app/services/sale_ready_rules.py,
matching the rest of app/models (no CheckConstraints).

Additive and nullable, so Postgres adds it without rewriting the table and every
existing task reads NULL. No index: the column is only ever read alongside the
rows already fetched by ix_tasks_engagement_module_section.

Downgrade drops the column, losing any N/A or blocked marks; the tasks and their
statuses are untouched.

Written with inspector guards to match add_sale_ready_task_fields, because
several environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_task_state'
down_revision = 'add_sale_ready_planner_closeout'
branch_labels = None
depends_on = None

_TABLE = 'tasks'
_COLUMN = 'sale_ready_state'


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guard below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _has_column(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return name in {c['name'] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _offline() or not _has_column(_TABLE, _COLUMN):
        op.add_column(_TABLE, sa.Column(
            _COLUMN, sa.String(20), nullable=True,
            comment="Sale Ready only: 'not_applicable' or 'blocked'; NULL for every other task",
        ))


def downgrade() -> None:
    if _offline() or _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
