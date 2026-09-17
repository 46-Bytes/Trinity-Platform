"""add pd_scorecards and pd_scorecard_roles tables

Revision ID: 50f7a483da0a
Revises: 5cba10191710
Create Date: 2026-08-18 11:44:34.943581

Autogenerate also picked up unrelated drift between the models and the database
(column comments, redundant unique constraints, and dropped columns on users,
subscriptions, firms and strategy_workbooks). All of it has been removed — this
revision creates the two new tables and nothing else.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '50f7a483da0a'
down_revision = '5cba10191710'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('pd_scorecards',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('engagement_id', sa.UUID(), nullable=True, comment='Optional link to engagement'),
    sa.Column('created_by_user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), server_default='inputs', nullable=False, comment='inputs, roles_identified, in_progress, completed'),
    sa.Column('current_step', sa.Integer(), nullable=True, comment='Current step the user is on (1-4)'),
    sa.Column('max_step_reached', sa.Integer(), nullable=True, comment='Maximum step the user has reached (1-4)'),
    sa.Column('client_name', sa.String(length=255), nullable=True, comment='Business name shown in the PD header'),
    sa.Column('fy_range', sa.String(length=50), nullable=True, comment="Financial year range for transition sections, e.g. 'FY25-27'"),
    sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of Claude file_ids for the uploaded matrix and reference PDs'),
    sa.Column('file_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Mapping of filename to file_id: {'matrix.xlsx': 'file-abc123'}"),
    sa.Column('stored_files', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Mapping of filename to relative storage path: {'matrix.xlsx': 'pd_id/matrix.xlsx'}"),
    sa.Column('reference_pd_files', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Filenames flagged as tone-only reference PDs: ['old-ceo-pd.docx']"),
    sa.Column('pasted_notes', sa.Text(), nullable=True, comment='Pasted matrix content or extra notes'),
    sa.Column('matrix_rows', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Source matrix rows. Each row matches the Job Roles columns: name, role_description, time, priorities, retain, gain, lose, action, resp, when'),
    sa.Column('ai_model_used', sa.String(length=100), nullable=True, comment='AI model used'),
    sa.Column('ai_tokens_used', sa.Integer(), nullable=True, comment='Total tokens used in AI processing'),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='Whether this record has been soft deleted'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True, comment='When every included role was first approved'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_pd_scorecards_created_by_user_id'), 'pd_scorecards', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_pd_scorecards_engagement_id'), 'pd_scorecards', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_pd_scorecards_status'), 'pd_scorecards', ['status'], unique=False)
    op.create_table('pd_scorecard_roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('pd_scorecard_id', sa.UUID(), nullable=False),
    sa.Column('role_title', sa.String(length=255), nullable=False, comment="Role name, e.g. 'General Manager'"),
    sa.Column('person_name', sa.String(length=255), nullable=True, comment='Person currently in the role, where known'),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('included', sa.Boolean(), server_default='true', nullable=False, comment='Whether the advisor confirmed this role for the build'),
    sa.Column('source_responsibilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Matrix rows attributed to this role, grouped by retain, gain and lose'),
    sa.Column('pd_content', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='The seven PD sections'),
    sa.Column('pd_status', sa.String(length=50), server_default='not_started', nullable=False, comment='not_started, draft, approved'),
    sa.Column('pd_approved_at', sa.DateTime(), nullable=True),
    sa.Column('scorecard_content', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='The four scorecard sections'),
    sa.Column('scorecard_status', sa.String(length=50), server_default='not_started', nullable=False, comment='not_started, draft, approved'),
    sa.Column('scorecard_approved_at', sa.DateTime(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='Whether this record has been soft deleted'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['pd_scorecard_id'], ['pd_scorecards.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_index('ix_pd_scorecard_roles_parent_order', 'pd_scorecard_roles', ['pd_scorecard_id', 'sort_order'], unique=False)
    op.create_index(op.f('ix_pd_scorecard_roles_pd_scorecard_id'), 'pd_scorecard_roles', ['pd_scorecard_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pd_scorecard_roles_pd_scorecard_id'), table_name='pd_scorecard_roles')
    op.drop_index('ix_pd_scorecard_roles_parent_order', table_name='pd_scorecard_roles')
    op.drop_table('pd_scorecard_roles')
    op.drop_index(op.f('ix_pd_scorecards_status'), table_name='pd_scorecards')
    op.drop_index(op.f('ix_pd_scorecards_engagement_id'), table_name='pd_scorecards')
    op.drop_index(op.f('ix_pd_scorecards_created_by_user_id'), table_name='pd_scorecards')
    op.drop_table('pd_scorecards')
