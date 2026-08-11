"""add required_inputs to program_module_content

Adds the module card's required-inputs list, which the spec labels per item as
'Held in Trinity', 'Advisor to upload' or 'From an earlier module'. The
earlier-module case also carries a fallback, because the spec is explicit that
no module may assume another has already run.

Shape: [{key, label, source, fallback}] with source in
'trinity' | 'advisor_upload' | 'earlier_module'. Nullable, no backfill - the
seed script populates it from the fixture.

Written with inspector guards to match add_program_deliverable_tables, because
several environments have drifted from the migration history.

Revision ID: add_module_required_inputs
Revises: merge_deliverable_sale_ready
Create Date: 2026-08-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_module_required_inputs'
down_revision = 'merge_deliverable_sale_ready'
branch_labels = None
depends_on = None

_TABLE = 'program_module_content'
_COLUMN = 'required_inputs'


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


def upgrade() -> None:
    if _offline() or not _has_column(_TABLE, _COLUMN):
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                JSONB,
                nullable=True,
                comment="[{key, label, source, fallback}] where source is "
                        "'trinity'|'advisor_upload'|'earlier_module'; fallback states what to do "
                        "when an earlier-module input is absent, since no module may assume another has run",
            ),
        )


def downgrade() -> None:
    if _offline() or _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
