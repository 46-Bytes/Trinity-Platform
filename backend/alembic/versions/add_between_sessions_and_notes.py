"""add between_sessions and section_notes to program_module_content

Specification Part C (V2 Strategy & Planning) runs two sessions with work in
between - generating the Strategic Business Plan from the first session's
workbook before walking the client through it at the second. That phase had
nowhere to live.

Part C also attaches prose to whole sections rather than to their items: a note
on required inputs explaining why uploading source material matters, and one on
deliverables explaining what the plan template already covers. section_notes is
keyed by section name rather than being a column per note, because modules
differ in which sections carry one and there are nine specification parts still
to arrive.

Both nullable, no backfill - the seed script populates them from the fixture.

Written with inspector guards to match add_module_card_sections, because
several environments have drifted from the migration history.

Revision ID: add_between_sessions_notes
Revises: add_module_card_sections
Create Date: 2026-08-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_between_sessions_notes'
down_revision = 'add_module_card_sections'
branch_labels = None
depends_on = None

_TABLE = 'program_module_content'

_NEW_COLUMNS = [
    ('between_sessions', JSONB,
     "{owner, duration, items: [text, ...]} work done between two sessions"),
    ('section_notes', JSONB,
     "{section_name: text} prose attached to a whole section rather than to one of its items"),
]


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
    for name, type_, comment in _NEW_COLUMNS:
        if _offline() or not _has_column(_TABLE, name):
            op.add_column(_TABLE, sa.Column(name, type_, nullable=True, comment=comment))


def downgrade() -> None:
    for name, _type, _comment in reversed(_NEW_COLUMNS):
        if _offline() or _has_column(_TABLE, name):
            op.drop_column(_TABLE, name)
