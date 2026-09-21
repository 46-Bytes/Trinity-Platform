"""add Sale Ready engagement stage and DD item state

Revision ID: add_sale_ready_engagement_state
Revises: add_sale_ready_program_templates
Create Date: 2026-09-18

Migration B of three for the Sale Ready program. Extends the per-engagement
tables from add_sale_ready_program_tables, which hold no rows on any known
environment; the guard below checks that before a required column is added.

- engagement_stage_state: who started and completed a stage, and when. The
  brief makes Complete an advisor action, and audit-sensitive writes record the
  original user when an admin is impersonating.
- engagement_dd_item: module_code renamed to stage_code; each row linked to the
  checklist item it was copied from; the brief's four DD statuses (NULL = no
  status yet), gap handling, and the "review at M8" flag.

Additive apart from one column rename and two index renames. No data changes,
nothing dropped: the superseded 'completed', 'media_id' and 'file_link' columns
and 'priority_order' stay until a later, separately reviewed cleanup.

template_item_id is ON DELETE RESTRICT: checklist templates are retired with
is_active, never deleted, and a delete must not silently erase an engagement's
DD history.

Downgrade reverses every step and drops the added columns, so any statuses, gap
choices, flags and audit fields recorded after the upgrade are lost.

Written with inspector guards to match add_media_engagement_id, because several
environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_engagement_state'
down_revision = 'add_sale_ready_program_templates'
branch_labels = None
depends_on = None

_STAGE_STATE = 'engagement_stage_state'
_DD_ITEM = 'engagement_dd_item'

_DD_UQ = 'uq_engagement_dd_item_engagement_template'
_DD_STATUS_INDEX = 'ix_engagement_dd_item_engagement_status'
_DD_INDEX_RENAMES = [
    ('ix_engagement_dd_item_eng_module', 'ix_engagement_dd_item_eng_stage'),
    ('ix_engagement_dd_item_module_code', 'ix_engagement_dd_item_stage_code'),
]

# (name, type, nullable, server_default, comment)
_STAGE_STATE_COLUMNS = [
    ('started_at', sa.DateTime(), True, None, "When the advisor started the stage"),
    ('started_by_user_id', UUID(as_uuid=True), True, None, "Who started the stage"),
    ('completed_at', sa.DateTime(), True, None, "When the advisor marked the stage complete"),
    ('completed_by_user_id', UUID(as_uuid=True), True, None, "Who marked it complete (the impersonated user, if any)"),
    ('completed_by_original_user_id', UUID(as_uuid=True), True, None,
     "The real user behind completed_by_user_id when an admin was impersonating"),
]
_DD_ITEM_COLUMNS = [
    ('template_item_id', UUID(as_uuid=True), False, None, "Checklist template row this item was copied from"),
    ('item_key', sa.String(100), False, None, "Copied from the template, e.g. 'DD-029'"),
    ('category_code', sa.String(10), False, None, "Copied from the template, e.g. '3'"),
    ('sub_item_code', sa.String(10), False, None, "Copied from the template, e.g. '3.1'"),
    ('status', sa.String(20), True, None,
     "NULL (no status yet), 'yes', 'in_progress', 'no' or 'not_applicable'"),
    ('status_changed_at', sa.DateTime(), True, None, "When status last changed"),
    ('status_changed_by_user_id', UUID(as_uuid=True), True, None, "Who last changed status"),
    ('gap_handling', sa.String(20), True, None,
     "For a gap (status 'no'): 'fix', 'disclose' or 'refer'; NULL = not yet decided"),
    ('flag_for_m8', sa.Boolean(), False, sa.text('false'), "Flagged for re-review at Due Diligence Preparation"),
]

# (constraint name, table, column, referred table, ondelete)
_FOREIGN_KEYS = [
    ('fk_engagement_stage_state_started_by', _STAGE_STATE, 'started_by_user_id', 'users', 'SET NULL'),
    ('fk_engagement_stage_state_completed_by', _STAGE_STATE, 'completed_by_user_id', 'users', 'SET NULL'),
    ('fk_engagement_stage_state_completed_by_original', _STAGE_STATE, 'completed_by_original_user_id', 'users', 'SET NULL'),
    ('fk_engagement_dd_item_template_item', _DD_ITEM, 'template_item_id', 'program_dd_template', 'RESTRICT'),
    ('fk_engagement_dd_item_status_changed_by', _DD_ITEM, 'status_changed_by_user_id', 'users', 'SET NULL'),
]


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guards below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table: str, name: str) -> bool:
    inspector = _inspector()
    if table not in inspector.get_table_names():
        return False
    return name in {c['name'] for c in inspector.get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    inspector = _inspector()
    if table not in inspector.get_table_names():
        return False
    return name in {i['name'] for i in inspector.get_indexes(table)}


def _has_unique(table: str, name: str) -> bool:
    inspector = _inspector()
    if table not in inspector.get_table_names():
        return False
    return name in {u['name'] for u in inspector.get_unique_constraints(table)}


def _foreign_key_name(table: str, column: str, referred_table: str, referred_column: str = 'id'):
    """
    Name of the existing FK from `column` to referred_table.referred_column.
    All three must match, so an unrelated FK on the same column is not taken for
    this one; matching by target rather than name still finds a drifted name.
    """
    inspector = _inspector()
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


def _assert_empty(table: str) -> None:
    """
    Abort rather than add a required column to a table that has rows. Nothing
    in the application writes to this table yet, so rows would mean an unknown
    writer - worth stopping for, not guessing around.
    """
    if _offline():
        return
    count = op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar()
    if count:
        raise RuntimeError(
            f"{table} has {count} row(s); expected none. Inspect them before applying "
            f"{revision}: a required column cannot be added to existing rows."
        )


def _add_columns(table: str, columns) -> None:
    for name, type_, nullable, default, comment in columns:
        if _offline() or not _has_column(table, name):
            if not nullable and default is None:
                _assert_empty(table)
            op.add_column(table, sa.Column(
                name, type_, nullable=nullable, server_default=default, comment=comment,
            ))


def _drop_columns(table: str, columns) -> None:
    for name, *_ in reversed(columns):
        if _offline() or _has_column(table, name):
            op.drop_column(table, name)


def _rename_column(table: str, old: str, new: str) -> None:
    if _offline():
        op.alter_column(table, old, new_column_name=new)
        return
    has_old, has_new = _has_column(table, old), _has_column(table, new)
    if has_old and has_new:
        raise RuntimeError(f"{table} has both {old} and {new}; resolve the drift by hand")
    if has_old:
        op.alter_column(table, old, new_column_name=new)


def _rename_index(table: str, old: str, new: str) -> None:
    """
    Rename only from a known state: old present and new absent. New present
    alone means already renamed; any other combination is drift to fix by hand.
    """
    if _offline():
        op.execute(f'ALTER INDEX {old} RENAME TO {new}')
        return
    has_old, has_new = _has_index(table, old), _has_index(table, new)
    if has_old and not has_new:
        op.execute(f'ALTER INDEX {old} RENAME TO {new}')
    elif has_new and not has_old:
        return
    elif has_old and has_new:
        raise RuntimeError(f"{table} has both indexes {old} and {new}; resolve the drift by hand")
    else:
        raise RuntimeError(f"{table} has neither index {old} nor {new}; resolve the drift by hand")


def upgrade() -> None:
    # engagement_stage_state: all nullable, so safe with or without rows.
    _add_columns(_STAGE_STATE, _STAGE_STATE_COLUMNS)

    _rename_column(_DD_ITEM, 'module_code', 'stage_code')
    for old, new in _DD_INDEX_RENAMES:
        _rename_index(_DD_ITEM, old, new)
    _add_columns(_DD_ITEM, _DD_ITEM_COLUMNS)

    for name, table, column, referred, ondelete in _FOREIGN_KEYS:
        if _offline() or _foreign_key_name(table, column, referred) is None:
            op.create_foreign_key(name, table, referred, [column], ['id'], ondelete=ondelete)

    if _offline() or not _has_unique(_DD_ITEM, _DD_UQ):
        op.create_unique_constraint(_DD_UQ, _DD_ITEM, ['engagement_id', 'template_item_id'])
    if _offline() or not _has_index(_DD_ITEM, _DD_STATUS_INDEX):
        op.create_index(_DD_STATUS_INDEX, _DD_ITEM, ['engagement_id', 'status'])


def downgrade() -> None:
    if _offline() or _has_index(_DD_ITEM, _DD_STATUS_INDEX):
        op.drop_index(_DD_STATUS_INDEX, table_name=_DD_ITEM)
    if _offline() or _has_unique(_DD_ITEM, _DD_UQ):
        op.drop_constraint(_DD_UQ, _DD_ITEM, type_='unique')

    for name, table, column, referred, _ondelete in reversed(_FOREIGN_KEYS):
        if _offline():
            op.drop_constraint(name, table, type_='foreignkey')
        else:
            existing = _foreign_key_name(table, column, referred)
            if existing:
                op.drop_constraint(existing, table, type_='foreignkey')

    _drop_columns(_DD_ITEM, _DD_ITEM_COLUMNS)
    for old, new in reversed(_DD_INDEX_RENAMES):
        _rename_index(_DD_ITEM, new, old)
    _rename_column(_DD_ITEM, 'stage_code', 'module_code')

    _drop_columns(_STAGE_STATE, _STAGE_STATE_COLUMNS)
