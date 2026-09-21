"""add Sale Ready program template columns

Revision ID: add_sale_ready_program_templates
Revises: add_media_engagement_id
Create Date: 2026-09-18

Migration A of three for the Sale Ready program. Extends the template tables
that add_sale_ready_program_tables created in July without their application
code. They hold no rows on any environment we know of; the guard below makes
that a checked fact before a required column is added.

- program_stage: display code (P1-P7), when a stage's tasks are created, and
  the markers for the Sale Planner and Close-out screens.
- program_task_template: a stable key per template so the seed can re-run
  without duplicating, and the phase sub-group title ("Diagnostic Completion").
- program_dd_template: module_code renamed to stage_code, because DD items also
  belong to the Appraisal and Transition phases; stable key and category /
  sub-item codes.

Additive apart from one column rename and one index rename. No data changes.

Downgrade reverses every step. It drops the added columns, so once templates
are seeded their keys, codes and group titles are lost; the rows themselves
stay, back under module_code.

Written with inspector guards to match add_media_engagement_id, because several
environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_program_templates'
down_revision = 'add_media_engagement_id'
branch_labels = None
depends_on = None

_STAGE = 'program_stage'
_TASK_TEMPLATE = 'program_task_template'
_DD_TEMPLATE = 'program_dd_template'

_TASK_TEMPLATE_UQ = 'uq_program_task_template_type_stage_key'
_DD_TEMPLATE_UQ = 'uq_program_dd_template_type_item_key'
_DD_INDEX_OLD = 'ix_program_dd_template_type_module'
_DD_INDEX_NEW = 'ix_program_dd_template_type_stage'

# (name, type, nullable, server_default, comment)
_STAGE_COLUMNS = [
    ('display_code', sa.String(10), True, None, "Code shown on the stage card: P1-P7 for phases, M1-M8 for modules"),
    ('task_creation', sa.String(30), False, 'on_start',
     "When template tasks are created: 'on_engagement_create' (phases) or 'on_start' (modules)"),
    ('ui_variant', sa.String(30), True, None, "Stage with its own screen: 'sale_planner', 'closeout', or NULL"),
    ('ui_config', JSONB, True, None, "Screen configuration, e.g. the Sale Planner's option lists and questions"),
]
_TASK_TEMPLATE_COLUMNS = [
    ('template_key', sa.String(100), False, None, "Stable key within the stage, e.g. 'M1-MUST-03'; the seed upserts on it"),
    ('group_title', sa.String(255), True, None, "Sub-group heading for phase tasks, e.g. 'Diagnostic Completion'"),
]
_DD_TEMPLATE_COLUMNS = [
    ('item_key', sa.String(100), False, None, "Stable key for the checklist item, e.g. 'DD-029'"),
    ('category_code', sa.String(10), False, None, "Category number, e.g. '3'"),
    ('sub_item_code', sa.String(10), False, None, "Sub-item number, e.g. '3.1'; one Drive folder per sub-item later"),
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


def _assert_empty(table: str) -> None:
    """
    Abort rather than add a required column to a table that has rows. These
    tables were created without any code that writes to them, so rows here
    would mean an unknown writer - worth stopping for, not guessing around.
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
    # program_stage: everything nullable or defaulted, so safe with or without rows.
    _add_columns(_STAGE, _STAGE_COLUMNS)

    _add_columns(_TASK_TEMPLATE, _TASK_TEMPLATE_COLUMNS)
    if _offline() or not _has_unique(_TASK_TEMPLATE, _TASK_TEMPLATE_UQ):
        op.create_unique_constraint(
            _TASK_TEMPLATE_UQ, _TASK_TEMPLATE, ['program_type', 'stage_code', 'template_key'],
        )

    _rename_column(_DD_TEMPLATE, 'module_code', 'stage_code')
    _rename_index(_DD_TEMPLATE, _DD_INDEX_OLD, _DD_INDEX_NEW)
    op.alter_column(
        _DD_TEMPLATE, 'stage_code', existing_type=sa.String(30), existing_nullable=False,
        comment="Stage the item belongs to: a module (M1-M8) or a phase (APPRAISAL, TRANSITION)",
    )
    _add_columns(_DD_TEMPLATE, _DD_TEMPLATE_COLUMNS)
    if _offline() or not _has_unique(_DD_TEMPLATE, _DD_TEMPLATE_UQ):
        op.create_unique_constraint(_DD_TEMPLATE_UQ, _DD_TEMPLATE, ['program_type', 'item_key'])


def downgrade() -> None:
    if _offline() or _has_unique(_DD_TEMPLATE, _DD_TEMPLATE_UQ):
        op.drop_constraint(_DD_TEMPLATE_UQ, _DD_TEMPLATE, type_='unique')
    _drop_columns(_DD_TEMPLATE, _DD_TEMPLATE_COLUMNS)
    _rename_index(_DD_TEMPLATE, _DD_INDEX_NEW, _DD_INDEX_OLD)
    _rename_column(_DD_TEMPLATE, 'stage_code', 'module_code')
    # The original column had no comment.
    op.alter_column(_DD_TEMPLATE, 'module_code', existing_type=sa.String(30), existing_nullable=False, comment=None)

    if _offline() or _has_unique(_TASK_TEMPLATE, _TASK_TEMPLATE_UQ):
        op.drop_constraint(_TASK_TEMPLATE_UQ, _TASK_TEMPLATE, type_='unique')
    _drop_columns(_TASK_TEMPLATE, _TASK_TEMPLATE_COLUMNS)

    _drop_columns(_STAGE, _STAGE_COLUMNS)
