"""add module_notes to program_module_content

Specification Part D (V3 Leadership & Communications) carries a titled note -
"Where there is no leadership layer" - explaining how the module runs for a
client with no managers at all. It sits between Core outcomes and Required
inputs and concerns the whole module, so section_notes does not fit: those are
untitled prose keyed to one named section, and storing it there would drop the
title that carries its framing.

Shape: [{key, title, text}]. Nullable, no backfill - the seed script populates
it from the fixture.

Written with inspector guards to match add_between_sessions_notes, because
several environments have drifted from the migration history.

Revision ID: add_module_notes
Revises: add_between_sessions_notes
Create Date: 2026-08-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_module_notes'
down_revision = 'add_between_sessions_notes'
branch_labels = None
depends_on = None

_TABLE = 'program_module_content'
_COLUMN = 'module_notes'
_COMMENT = (
    "[{key, title, text}] titled guidance about the module as a whole rather than about one of "
    "its sections. Distinct from section_notes: those are untitled and belong to a named section"
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


def upgrade() -> None:
    if _offline() or not _has_column(_TABLE, _COLUMN):
        op.add_column(_TABLE, sa.Column(_COLUMN, JSONB, nullable=True, comment=_COMMENT))


def downgrade() -> None:
    if _offline() or _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
