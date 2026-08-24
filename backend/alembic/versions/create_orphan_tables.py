"""create advisor_client and bba tables

Revision ID: create_orphan_tables
Revises: remove_unique_sub_id
Create Date: 2026-08-24

Both tables are declared in the models but no migration ever created them - they
only ever existed in databases where they were created out-of-band. As a result
`alembic upgrade head` against an empty database failed at
a8d3b2d2caf9_add_bba_task_planner_columns with:

    relation "advisor_client" does not exist

This creates them in their ORIGINAL shape - the model columns minus the 18 that
later migrations add to bba - so every subsequent add_column in the chain still
applies normally. It is inserted before add_bba_report_columns, the first
revision that references bba.

Guarded by a table-existence check, so it is a no-op on databases that already
have the tables.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'create_orphan_tables'
down_revision = 'remove_unique_sub_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    tables = inspect(conn).get_table_names()

    if 'advisor_client' not in tables:
        op.create_table(
            'advisor_client',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True,
                      comment='Unique identifier for the association'),
            sa.Column('advisor_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False,
                      comment='Foreign key to users table (advisor)'),
            sa.Column('client_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False,
                      comment='Foreign key to users table (client)'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='active',
                      comment='Association status: active, inactive, suspended'),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false',
                      comment='Whether this record has been soft deleted'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP'),
                      comment='When the association was created'),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP'),
                      comment='When the association was last updated'),
            sa.UniqueConstraint('advisor_id', 'client_id', name='uq_advisor_client'),
        )
        op.create_index('ix_advisor_client_advisor_id', 'advisor_client', ['advisor_id'])
        op.create_index('ix_advisor_client_client_id', 'advisor_client', ['client_id'])
        op.create_index('ix_advisor_client_status', 'advisor_client', ['status'])

    if 'bba' not in tables:
        op.create_table(
            'bba',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
            sa.Column('engagement_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=True),
            sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='uploaded'),
            sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('file_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('client_name', sa.String(length=255), nullable=True),
            sa.Column('industry', sa.String(length=255), nullable=True),
            sa.Column('company_size', sa.String(length=50), nullable=True),
            sa.Column('locations', sa.String(length=500), nullable=True),
            sa.Column('exclusions', sa.Text(), nullable=True),
            sa.Column('constraints', sa.Text(), nullable=True),
            sa.Column('preferred_ranking', sa.Text(), nullable=True),
            sa.Column('strategic_priorities', sa.Text(), nullable=True),
            sa.Column('draft_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('expanded_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('snapshot_table', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('ai_model_used', sa.String(length=100), nullable=True),
            sa.Column('ai_tokens_used', sa.Integer(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false',
                      comment='Whether this record has been soft deleted'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('questionnaire_completed_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_bba_engagement_id', 'bba', ['engagement_id'])
        op.create_index('ix_bba_created_by_user_id', 'bba', ['created_by_user_id'])
        op.create_index('ix_bba_status', 'bba', ['status'])


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    tables = inspect(conn).get_table_names()

    if 'bba' in tables:
        op.drop_table('bba')
    if 'advisor_client' in tables:
        op.drop_table('advisor_client')
