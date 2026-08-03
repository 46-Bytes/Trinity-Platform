"""add program deliverable tables

Adds the deliverables subsystem for module-based programs (Value Builder):
  - program_module_deliverable      - shared library of preset deliverables,
                                      authored once per module
  - engagement_module_deliverable   - sparse per-engagement instances carrying
                                      completion and scope state, and also the
                                      home for advisor-added deliverables

Structure only. No data migration: ProgramModuleContent.deliverables (a JSONB
array of bare placeholder strings) is deliberately left in place and untouched,
and the library is populated by the seed script once real content lands.

Written with inspector guards to match f7a1b2c3d4e5, because several
environments have drifted from the migration history.

Revision ID: add_program_deliverable_tables
Revises: e8404c561e86
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_program_deliverable_tables'
down_revision = 'e8404c561e86'
branch_labels = None
depends_on = None


def _offline() -> bool:
    """
    Offline (--sql) mode has no live connection to inspect, so the guards below
    cannot run. Emit the full DDL unconditionally there.
    """
    return op.get_context().as_sql


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {i['name'] for i in _inspector().get_indexes(table)}


def _should_create_table(name: str) -> bool:
    return _offline() or not _has_table(name)


def _should_create_index(table: str, name: str) -> bool:
    return _offline() or not _has_index(table, name)


def _should_drop_table(name: str) -> bool:
    return _offline() or _has_table(name)


def _should_drop_index(table: str, name: str) -> bool:
    return _offline() or _has_index(table, name)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. program_module_deliverable - the preset library
    # ------------------------------------------------------------------
    if _should_create_table('program_module_deliverable'):
        op.create_table(
            'program_module_deliverable',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('program_type', sa.String(100), nullable=False,
                      comment="e.g. 'value_builder' - matches Engagement.tool"),
            sa.Column('module_code', sa.String(20), nullable=False,
                      comment="e.g. 'M0', 'V1'..'V11', 'M12'"),
            sa.Column('deliverable_key', sa.String(100), nullable=False,
                      comment="Stable slug for this deliverable within the module"),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text, nullable=True,
                      comment="Optional longer explanation of the deliverable"),
            sa.Column('is_mandatory', sa.Boolean, nullable=False, server_default='true',
                      comment="Mandatory/optional flag for this preset; the only source of truth - instances never override it"),
            sa.Column('display_order', sa.Integer, nullable=False,
                      comment="Author-defined sequence within (program_type, module_code)"),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='true',
                      comment="False retires the preset without deleting it"),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint('program_type', 'module_code', 'deliverable_key',
                                name='uq_program_module_deliverable_type_module_key'),
        )

    if _should_create_index('program_module_deliverable', 'ix_program_module_deliverable_type_module_order'):
        op.create_index(
            'ix_program_module_deliverable_type_module_order',
            'program_module_deliverable',
            ['program_type', 'module_code', 'display_order'],
        )

    # ------------------------------------------------------------------
    # 2. engagement_module_deliverable - sparse per-engagement instances
    #
    # A row exists only once a deliverable has been ticked off or scoped out;
    # an absent row means "incomplete and in scope". library_deliverable_id
    # discriminates preset instances (NOT NULL) from advisor-added
    # deliverables (NULL).
    # ------------------------------------------------------------------
    if _should_create_table('engagement_module_deliverable'):
        op.create_table(
            'engagement_module_deliverable',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('engagement_id', UUID(as_uuid=True),
                      sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('module_code', sa.String(20), nullable=False,
                      comment="Denormalised for presets; authoritative for advisor-added rows, which have no library row"),
            sa.Column('library_deliverable_id', UUID(as_uuid=True),
                      sa.ForeignKey('program_module_deliverable.id', ondelete='CASCADE'), nullable=True,
                      comment="NOT NULL for a preset instance, NULL for an advisor-added deliverable"),

            sa.Column('title', sa.String(255), nullable=True,
                      comment="Advisor-added deliverables only; MUST be NULL for presets, which read program_module_deliverable.title"),
            sa.Column('description', sa.Text, nullable=True,
                      comment="Advisor-added deliverables only; MUST be NULL for presets"),
            sa.Column('is_mandatory', sa.Boolean, nullable=True,
                      comment="Mandatory/optional flag for advisor-added deliverables only; MUST be NULL for presets, which read program_module_deliverable.is_mandatory"),

            sa.Column('is_complete', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('completed_by_user_id', UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('completed_at', sa.DateTime, nullable=True),

            sa.Column('is_in_scope', sa.Boolean, nullable=False, server_default='true',
                      comment="False means scoped out: retained on the engagement but excluded from completion"),
            sa.Column('scoped_out_by_user_id', UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('scoped_out_at', sa.DateTime, nullable=True),

            sa.Column('created_by_user_id', UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True,
                      comment="Author of an advisor-added deliverable"),

            sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false',
                      comment="Advisor-added deliverables only; presets are scoped out, never deleted"),

            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),

            # Postgres treats NULLs as distinct in a unique index, so this
            # enforces exactly one instance row per (engagement, preset) while
            # placing no limit on advisor-added rows.
            sa.UniqueConstraint('engagement_id', 'library_deliverable_id',
                                name='uq_engagement_module_deliverable_engagement_library'),
        )

    if _should_create_index('engagement_module_deliverable', 'ix_engagement_module_deliverable_engagement_module'):
        op.create_index(
            'ix_engagement_module_deliverable_engagement_module',
            'engagement_module_deliverable',
            ['engagement_id', 'module_code'],
        )


def downgrade() -> None:
    if _should_drop_index('engagement_module_deliverable', 'ix_engagement_module_deliverable_engagement_module'):
        op.drop_index('ix_engagement_module_deliverable_engagement_module', table_name='engagement_module_deliverable')
    if _should_drop_table('engagement_module_deliverable'):
        op.drop_table('engagement_module_deliverable')

    if _should_drop_index('program_module_deliverable', 'ix_program_module_deliverable_type_module_order'):
        op.drop_index('ix_program_module_deliverable_type_module_order', table_name='program_module_deliverable')
    if _should_drop_table('program_module_deliverable'):
        op.drop_table('program_module_deliverable')
