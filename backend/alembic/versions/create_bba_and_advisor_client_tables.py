"""create bba and advisor_client tables

Revision ID: create_bba_advisor_client
Revises: remove_unique_sub_id
Create Date: 2026-07-31

Both tables were originally created by hand on the shared dev database and no
migration ever created them, so `alembic upgrade head` on a fresh database blew
up at 'a8d3b2d2caf9' with `relation "advisor_client" does not exist`. This
revision creates them in their original shape; every later revision then layers
its columns on top exactly as before.

Idempotent: skips a table that already exists, so databases that were migrated
before this revision landed are unaffected.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'create_bba_advisor_client'
down_revision = 'remove_unique_sub_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = sa.inspect(conn).get_table_names()

    if 'advisor_client' not in tables:
        op.create_table(
            'advisor_client',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                      comment='Unique identifier for the association'),
            sa.Column('advisor_id', postgresql.UUID(as_uuid=True), nullable=False,
                      comment='Foreign key to users table (advisor)'),
            sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False,
                      comment='Foreign key to users table (client)'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='active',
                      comment='Association status: active, inactive, suspended'),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP'),
                      comment='When the association was created'),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP'),
                      comment='When the association was last updated'),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['advisor_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['client_id'], ['users.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('advisor_id', 'client_id', name='uq_advisor_client'),
        )
        op.create_index('ix_advisor_client_advisor_id', 'advisor_client', ['advisor_id'])
        op.create_index('ix_advisor_client_client_id', 'advisor_client', ['client_id'])
        op.create_index('ix_advisor_client_status', 'advisor_client', ['status'])

    if 'bba' not in tables:
        op.create_table(
            'bba',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('engagement_id', postgresql.UUID(as_uuid=True), nullable=True,
                      comment='Optional link to engagement'),
            sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='uploaded',
                      comment='uploaded, questionnaire_completed, draft_findings, '
                              'expanded_findings, completed'),
            # Step 1: File uploads
            sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                      comment="List of OpenAI file_ids: ['file-abc123', 'file-xyz789']"),
            sa.Column('file_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                      comment="Mapping of filename to file_id: {'doc.pdf': 'file-abc123'}"),
            # Step 2: Context capture (questionnaire)
            sa.Column('client_name', sa.String(length=255), nullable=True),
            sa.Column('industry', sa.String(length=255), nullable=True),
            sa.Column('company_size', sa.String(length=50), nullable=True,
                      comment='startup, small, medium, large, enterprise'),
            sa.Column('locations', sa.String(length=500), nullable=True),
            sa.Column('exclusions', sa.Text(), nullable=True,
                      comment='Areas or topics to exclude from analysis'),
            sa.Column('constraints', sa.Text(), nullable=True,
                      comment='Constraints or limitations to consider'),
            sa.Column('preferred_ranking', sa.Text(), nullable=True,
                      comment='How findings should be ranked'),
            sa.Column('strategic_priorities', sa.Text(), nullable=True,
                      comment='Strategic priorities for next 12 months'),
            # Step 3-5: Findings
            sa.Column('draft_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                      comment='Ranked list of top findings with summaries'),
            sa.Column('expanded_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                      comment='Expanded findings with detailed paragraphs'),
            sa.Column('snapshot_table', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                      comment='Three-column table: Priority Area | Key Findings | Recommendations'),
            # AI metadata
            sa.Column('ai_model_used', sa.String(length=100), nullable=True,
                      comment='AI model used for analysis'),
            sa.Column('ai_tokens_used', sa.Integer(), nullable=True,
                      comment='Total tokens used in AI processing'),
            # Timestamps
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('questionnaire_completed_at', sa.DateTime(), nullable=True,
                      comment='When questionnaire was completed'),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_bba_engagement_id', 'bba', ['engagement_id'])
        op.create_index('ix_bba_created_by_user_id', 'bba', ['created_by_user_id'])
        op.create_index('ix_bba_status', 'bba', ['status'])


def downgrade() -> None:
    conn = op.get_bind()
    tables = sa.inspect(conn).get_table_names()

    if 'bba' in tables:
        op.drop_table('bba')
    if 'advisor_client' in tables:
        op.drop_table('advisor_client')
