"""add Sale Ready sale planner and program close-out

Revision ID: add_sale_ready_planner_closeout
Revises: add_sale_ready_task_fields
Create Date: 2026-09-19

Two new per-engagement tables for the Sale Ready stages that have their own
screen (program_stage.ui_variant):

- engagement_sale_planner (SALE_PLANNER): the sale decisions. Answers are
  stored by the stable keys in program_stage.ui_config (files/sale_ready/
  sale_planner.json), so a relabelled option or question keeps its answer.
    sale_type           a sale_types key, e.g. 'share_sale'
    sale_structures     ["cash_purchase", "earn_out", ...]
    value_propositions  {structure_key: text}
    marketing_answers   {question_key: text}
    issues              {issue_key: {"addressed": bool, "note": text}}
- engagement_program_closeout (CLOSEOUT): the close-out decisions and who
  closed the program. The original user is recorded when an admin impersonates.

One row per engagement in each, enforced by a UNIQUE constraint on
engagement_id (which also serves as its index). Rows go with their engagement
(ON DELETE CASCADE); a deleted user only unlinks (ON DELETE SET NULL).

Purely additive: two new tables, nothing existing is altered and no data is
written. Downgrade drops both tables, so any planner answers or close-out
decisions recorded after the upgrade are lost.

Written with inspector guards to match add_sale_ready_engagement_state,
because several environments have drifted from the migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_planner_closeout'
down_revision = 'add_sale_ready_task_fields'
branch_labels = None
depends_on = None

_PLANNER = 'engagement_sale_planner'
_CLOSEOUT = 'engagement_program_closeout'


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guards below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _offline() or not _has_table(_PLANNER):
        op.create_table(
            _PLANNER,
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
            sa.Column('sale_type', sa.String(30), nullable=True,
                      comment="A sale_types key from the Sale Planner stage's ui_config, e.g. 'share_sale'"),
            sa.Column('sale_structures', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"),
                      comment="Structure keys being considered, e.g. [\"cash_purchase\", \"earn_out\"]"),
            sa.Column('value_propositions', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"),
                      comment="Value analysis per structure: {structure_key: text}"),
            sa.Column('marketing_answers', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"),
                      comment="Marketing plan answers: {question_key: text}"),
            sa.Column('issues', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"),
                      comment="Issues to address: {issue_key: {\"addressed\": bool, \"note\": text}}"),
            sa.Column('updated_by_user_id', UUID(as_uuid=True), nullable=True,
                      comment="Who last changed the planner"),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                    name='fk_engagement_sale_planner_engagement'),
            sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL',
                                    name='fk_engagement_sale_planner_updated_by'),
            sa.UniqueConstraint('engagement_id', name='uq_engagement_sale_planner_engagement'),
        )

    if _offline() or not _has_table(_CLOSEOUT):
        op.create_table(
            _CLOSEOUT,
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
            sa.Column('fresh_appraisal_required', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                      comment="A fresh appraisal is required before listing"),
            sa.Column('referred_to_benchmark', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                      comment="Client referred to Benchmark Business Sales for listing"),
            sa.Column('ongoing_assistance', sa.Text(), nullable=True,
                      comment="The ongoing assistance agreed, if any"),
            sa.Column('closed_at', sa.DateTime(), nullable=True,
                      comment="When the program was closed; NULL while open"),
            sa.Column('closed_by_user_id', UUID(as_uuid=True), nullable=True,
                      comment="Who closed the program (the impersonated user, if any)"),
            sa.Column('closed_by_original_user_id', UUID(as_uuid=True), nullable=True,
                      comment="The real user behind closed_by_user_id when an admin was impersonating"),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                    name='fk_engagement_program_closeout_engagement'),
            sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id'], ondelete='SET NULL',
                                    name='fk_engagement_program_closeout_closed_by'),
            sa.ForeignKeyConstraint(['closed_by_original_user_id'], ['users.id'], ondelete='SET NULL',
                                    name='fk_engagement_program_closeout_closed_by_original'),
            sa.UniqueConstraint('engagement_id', name='uq_engagement_program_closeout_engagement'),
        )


def downgrade() -> None:
    if _offline() or _has_table(_CLOSEOUT):
        op.drop_table(_CLOSEOUT)
    if _offline() or _has_table(_PLANNER):
        op.drop_table(_PLANNER)
