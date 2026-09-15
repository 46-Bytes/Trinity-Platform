"""add engagement_id to media

Revision ID: add_media_engagement_id
Revises: add_module_commencement
Create Date: 2026-09-14

Lets a file belong to an engagement directly. Until now the only route from a
file to an engagement was media -> diagnostic_media -> diagnostics.engagement_id,
so a document could only be uploaded from inside a diagnostic questionnaire.

Nullable, so no backfill: every existing row keeps reaching its engagement the
way it always has, and diagnostic associations are untouched. A column rather
than a join table because a file belongs to exactly one engagement.

ON DELETE SET NULL rather than CASCADE: engagements soft delete, and a hard
delete should orphan the row rather than silently destroy a client's document.

Written with inspector guards to match add_task_source_deliverable, because
several environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_media_engagement_id'
down_revision = 'add_module_commencement'
branch_labels = None
depends_on = None

_TABLE = 'media'
_COLUMN = 'engagement_id'
_INDEX = 'ix_media_engagement_id'
_FK = 'fk_media_engagement_id_engagements'
_COMMENT = (
    "Engagement this file was uploaded to, if it was uploaded outside a diagnostic. "
    "Null for diagnostic uploads, which reach their engagement through diagnostic_media"
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


def _foreign_key_name(table: str, column: str):
    """
    Name of the existing FK on `column`, whatever it happens to be called.
    Matched by column rather than by name so a drifted environment that created
    the constraint under a different name is still recognised.
    """
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return None
    for fk in inspector.get_foreign_keys(table):
        if fk.get('constrained_columns') == [column]:
            return fk.get('name')
    return None


def upgrade() -> None:
    # Column, FK and index are guarded independently: an environment may have
    # drifted into having any subset of the three.
    if _offline() or not _has_column(_TABLE, _COLUMN):
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, UUID(as_uuid=True), nullable=True, comment=_COMMENT),
        )

    if _offline() or _foreign_key_name(_TABLE, _COLUMN) is None:
        op.create_foreign_key(
            _FK, _TABLE, 'engagements', [_COLUMN], ['id'], ondelete='SET NULL'
        )

    if _offline() or not _has_index(_TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    if _offline() or _has_index(_TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)

    if _offline():
        op.drop_constraint(_FK, _TABLE, type_='foreignkey')
    else:
        existing_fk = _foreign_key_name(_TABLE, _COLUMN)
        if existing_fk:
            op.drop_constraint(existing_fk, _TABLE, type_='foreignkey')

    if _offline() or _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
