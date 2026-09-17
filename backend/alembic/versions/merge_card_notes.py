"""merge section_notes and module_notes into one notes column

Notes were split across two columns: section_notes held untitled prose keyed by
section, module_notes held titled prose about the module as a whole. That split
survived until specification Part E, whose "Referral to the Talent team" note is
titled AND attached to the Guardrails section - neither column could hold it.

Replaced by one notes column, [{key, title, text, section}], where title and
section are independently optional. V4 alone uses three of the four
combinations.

No data migration: the seed script rewrites every row on every run and is the
only writer to this table, so re-running it after upgrading restores all
content in the merged shape. The downgrade recreates the two columns empty for
the same reason.

Written with inspector guards to match add_module_notes, because several
environments have drifted from the migration history.

Revision ID: merge_card_notes
Revises: add_module_notes
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'merge_card_notes'
down_revision = 'add_module_notes'
branch_labels = None
depends_on = None

_TABLE = 'program_module_content'
_NEW = 'notes'
_OLD = ('section_notes', 'module_notes')

_NEW_COMMENT = (
    "[{key, title, text, section}] prose that is not part of any list. `title` and `section` are "
    "both optional and independent: a note may be titled or not, and attached to a named section "
    "or to the module as a whole"
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
    if _offline() or not _has_column(_TABLE, _NEW):
        op.add_column(_TABLE, sa.Column(_NEW, JSONB, nullable=True, comment=_NEW_COMMENT))

    for name in _OLD:
        if _offline() or _has_column(_TABLE, name):
            op.drop_column(_TABLE, name)


def downgrade() -> None:
    for name in _OLD:
        if _offline() or not _has_column(_TABLE, name):
            op.add_column(_TABLE, sa.Column(name, JSONB, nullable=True))

    if _offline() or _has_column(_TABLE, _NEW):
        op.drop_column(_TABLE, _NEW)
