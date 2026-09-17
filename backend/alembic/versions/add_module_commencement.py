"""add engagement_module_commencement table

Revision ID: add_module_commencement
Revises: add_help_videos_tables
Create Date: 2026-09-14

Records that an advisor has formally started a module ("Commence Module"), so a
module can read In progress before any deliverable is ticked. Sparse: no row
means not commenced, so no backfill is needed and every existing module keeps
the status it derives today.

Written with inspector guards to match add_module_required_inputs, because
several environments have drifted from the migration history.

Because of that guard, upgrade() may find the table already present and skip
creating it. downgrade() must not drop a table this migration did not create,
so the creation is recorded durably in the table's COMMENT and downgrade drops
the table only when it finds that marker. A table that arrived some other way
carries a different comment (or none) and is left alone.

The marker is deliberately absent from the model: a drifted environment that
built the table from the metadata would otherwise carry it too, and downgrade
could not tell the two apart. Should autogenerate ever offer to drop the
comment, that only makes downgrade more conservative, never less.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_module_commencement'
down_revision = 'add_help_videos_tables'
branch_labels = None
depends_on = None

TABLE = 'engagement_module_commencement'
INDEX = 'ix_engagement_module_commencement_engagement_id'

# Proof that this migration created the table, not something else.
CREATED_MARKER = 'created by alembic revision add_module_commencement'


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guards below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def _created_by_this_migration() -> bool:
    """True only when the table carries this migration's creation marker."""
    comment = sa.inspect(op.get_bind()).get_table_comment(TABLE) or {}
    return comment.get('text') == CREATED_MARKER


def upgrade() -> None:
    if not _offline() and _has_table(TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('engagement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('module_code', sa.String(length=20), nullable=False),
        sa.Column('is_commenced', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('commenced_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('commenced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['commenced_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engagement_id', 'module_code', name='uq_engagement_module_commencement'),
        comment=CREATED_MARKER,
    )
    op.create_index(op.f(INDEX), TABLE, ['engagement_id'])


def downgrade() -> None:
    if _offline():
        op.drop_index(op.f(INDEX), table_name=TABLE)
        op.drop_table(TABLE)
        return

    # A table this migration did not create is left exactly as it was found.
    if not _has_table(TABLE) or not _created_by_this_migration():
        return

    op.drop_index(op.f(INDEX), table_name=TABLE)
    op.drop_table(TABLE)
