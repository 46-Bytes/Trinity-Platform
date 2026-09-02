"""add tables to program_module_content and session to program_module_deliverable

Specification Part H (V7 Sales & Marketing) brings two things nothing could hold.

program_module_content.tables carries reference matrices the advisor reads. V7's
is four business model shapes against nine dimensions that vary by shape, and it
decides how the whole module runs. Stored as generic columns and rows rather
than nine named fields, so a different matrix in a later module needs no further
migration.

program_module_deliverable.session records which session of a multi-session
module produces a deliverable. V7 is the first module with more than two
sessions and the first to map its deliverables onto them. Free text, because the
spec's own values include 'pre-1' and '2 or 3', neither of which is a session.

Both nullable, no backfill - the seed script populates them from the fixture.

Written with inspector guards to match merge_card_notes, because several
environments have drifted from the migration history.

Revision ID: add_tables_and_session
Revises: merge_card_notes
Create Date: 2026-08-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_tables_and_session'
down_revision = 'merge_card_notes'
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ('program_module_content', 'tables', JSONB,
     "[{key, title, intro, section, columns: [{key, label}], rows: [{key, label, cells: [text]}]}] "
     "reference matrices; cells align to columns by index"),
    ('program_module_deliverable', 'session', sa.String(50),
     "Which session of a multi-session module produces this. Free text - the spec also uses "
     "'pre-1' and '2 or 3', neither of which is a session"),
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
    for table, name, type_, comment in _NEW_COLUMNS:
        if _offline() or not _has_column(table, name):
            op.add_column(table, sa.Column(name, type_, nullable=True, comment=comment))


def downgrade() -> None:
    for table, name, _type, _comment in reversed(_NEW_COLUMNS):
        if _offline() or _has_column(table, name):
            op.drop_column(table, name)
