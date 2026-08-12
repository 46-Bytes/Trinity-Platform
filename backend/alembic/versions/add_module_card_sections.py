"""add the remaining module card sections and deliverable provenance

Specification Part A describes the module card as carrying "Purpose,
preparation, sessions, tools, deliverables, guardrails, quality standards".
Only purpose, preparation and tools had columns. Part B then adds focus, core
outcomes and post-session actions on top, plus per-deliverable provenance.

program_module_content gains:
    focus                 one-line statement of what the module concentrates on
    core_outcomes         [text, ...]
    preparation_summary   {owner, duration}
    sessions              the facilitation plan, including the question script
    post_session_actions  {owner, duration, items: [text, ...]}
    guardrails            {must_not: [text, ...], note}
    quality_standards     [text, ...]

program_module_deliverable gains:
    produced_by           'trinity_tool' | 'advisor' | 'client'
    produced_by_note      qualifier, e.g. 'advisor-refined'
    feeds                 [module_code, ...] later modules that consume it

All nullable, no backfill - the seed script populates them from the fixture.
preparation_checklist is deliberately left alone: its [].key is matched by
engagement_module_checklist_item.checklist_item_key, so reshaping it would
orphan tick-off state.

Written with inspector guards to match add_module_required_inputs, because
several environments have drifted from the migration history.

Revision ID: add_module_card_sections
Revises: add_module_required_inputs
Create Date: 2026-08-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_module_card_sections'
down_revision = 'add_module_required_inputs'
branch_labels = None
depends_on = None

_CONTENT = 'program_module_content'
_DELIVERABLE = 'program_module_deliverable'

_NEW_COLUMNS = [
    (_CONTENT, 'focus', sa.Text(),
     "One-line statement of what this module concentrates on"),
    (_CONTENT, 'core_outcomes', JSONB,
     "[text, ...] what is true once the module is done"),
    (_CONTENT, 'preparation_summary', JSONB,
     "{owner, duration} who prepares, and how long it takes"),
    (_CONTENT, 'sessions', JSONB,
     "[{key, title, duration, format, agenda: [{key, title, duration, detail, questions: [text, ...]}]}] "
     "the facilitation plan; `questions` is the advisor's prompt script for that agenda item"),
    (_CONTENT, 'post_session_actions', JSONB,
     "{owner, duration, items: [text, ...]} follow-up work after the session"),
    (_CONTENT, 'guardrails', JSONB,
     "{must_not: [text, ...], note} boundaries of profession rather than of module"),
    (_CONTENT, 'quality_standards', JSONB,
     "[text, ...] what good looks like for this module"),
    (_DELIVERABLE, 'produced_by', sa.String(50),
     "'trinity_tool' | 'advisor' | 'client' - the primary producer"),
    (_DELIVERABLE, 'produced_by_note', sa.String(255),
     "Qualifier on the producer, e.g. 'advisor-refined', 'advisor-reviewed'"),
    (_DELIVERABLE, 'feeds', JSONB,
     "[module_code, ...] later modules that consume this deliverable"),
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
