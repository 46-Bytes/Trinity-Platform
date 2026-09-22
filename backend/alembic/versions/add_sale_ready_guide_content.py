"""add Sale Ready program guide content and its per-engagement snapshot

Revision ID: add_sale_ready_guide_content
Revises: add_sale_ready_task_state
Create Date: 2026-09-22

Sale Ready Management lets an admin edit the program guide, the task templates
and the DD checklist for future engagements. The templates already had tables;
the guide did not - its text lived in the frontend. This adds the three things
it needs:

- program_stage.guide: the master guide for one stage, as
  {purpose, steps[], watch[], templates[], run_with}. Nullable, so a stage with
  nothing authored yet falls back to the frontend constants until it is seeded.
- program_guide_content: the guide content that is not attached to a stage -
  the workflow steps and the program rules - as {workflow[], rules[]}. One row
  per program_type. (Not to be confused with program_module_content, the Value
  Builder module library that scripts/seed_program_guide_content.py fills.)
- engagement_sale_ready_guide: one engagement's frozen copy of the whole guide,
  {program: {...}, stages: {<stage_code>: {...}}}, written once when the
  engagement is first initialized and never updated. This is what makes an
  admin's edit reach future engagements only: a live engagement reads its own
  snapshot, exactly as its tasks and DD items are copies taken at creation.

Purely additive. One nullable column with no default, so Postgres adds it
without rewriting program_stage, and two new tables. Nothing existing is
altered and no data is written or migrated - the guide content is loaded
afterwards by scripts/seed_sale_ready_program.py, and engagements that predate
snapshots are filled in by scripts/backfill_sale_ready_guide.py.

One row per engagement in engagement_sale_ready_guide, enforced by a UNIQUE
constraint on engagement_id which also serves as its index (no separate index,
matching engagement_sale_planner and engagement_program_closeout). Snapshots go
with their engagement (ON DELETE CASCADE).

Downgrade drops both tables and the column. Any guide content authored through
Sale Ready Management after the upgrade is lost, as is every engagement's
frozen copy; the stages, templates, tasks and DD items themselves are untouched,
and the frontend falls back to its constants.

Deliberately written WITHOUT the inspector guards that several neighbouring
migrations carry. Those guard objects that predate their own migration -
add_sale_ready_program_templates, for instance, extends tables that
add_sale_ready_program_tables created months earlier without application code,
and environments drifted around them. Nothing here has that history: neither
table, nor the guide column, appears in any migration, branch or commit before
this one, so there is no state to be tolerant of. Plain DDL is therefore the
safer choice - if one of these objects somehow already exists, this fails
loudly rather than skipping it and leaving alembic_version claiming a schema
that is not there. If you are about to add a guard here, check first whether
the object really can pre-exist; if it can, something has gone wrong upstream
and should be looked at rather than tolerated.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = 'add_sale_ready_guide_content'
down_revision = 'add_sale_ready_task_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable with no default: existing rows keep NULL and the table is not
    # rewritten. program_stage holds 15 rows, so this is cheap either way.
    op.add_column('program_stage', sa.Column(
        'guide', JSONB(), nullable=True,
        comment="Admin-editable stage guide: purpose, steps, watch, templates, run_with",
    ))

    op.create_table(
        'program_guide_content',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('program_type', sa.String(100), nullable=False),
        sa.Column('content', JSONB(), nullable=False,
                  comment="{'workflow': [{stage,label}], 'rules': [{title,body}]}"),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('program_type', name='uq_program_guide_content_type'),
    )

    op.create_table(
        'engagement_sale_ready_guide',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
        sa.Column('content', JSONB(), nullable=False,
                  comment="{'program': {workflow, rules}, 'stages': {<stage_code>: {...}}}"),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                name='fk_engagement_sale_ready_guide_engagement'),
        # Also the index on engagement_id; one snapshot per engagement.
        sa.UniqueConstraint('engagement_id', name='uq_engagement_sale_ready_guide_engagement'),
    )


def downgrade() -> None:
    op.drop_table('engagement_sale_ready_guide')
    op.drop_table('program_guide_content')
    op.drop_column('program_stage', 'guide')
