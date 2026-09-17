"""add roles_matrices table

Revision ID: 5cba10191710
Revises: 45bdcc478ace
Create Date: 2026-08-06 11:58:03.974702

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5cba10191710'
down_revision = '45bdcc478ace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('roles_matrices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('engagement_id', sa.UUID(), nullable=True, comment='Optional link to engagement'),
    sa.Column('created_by_user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), server_default='inputs', nullable=False, comment='inputs, extracted, matrix_built, completed'),
    sa.Column('current_step', sa.Integer(), nullable=True, comment='Current step the user is on (1-4)'),
    sa.Column('max_step_reached', sa.Integer(), nullable=True, comment='Maximum step the user has reached (1-4)'),
    sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='List of Claude file_ids for uploaded PDs/notes'),
    sa.Column('file_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Mapping of filename to file_id: {'pd.pdf': 'file-abc123'}"),
    sa.Column('stored_files', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Mapping of filename to relative storage path: {'pd.pdf': 'matrix_id/pd.pdf'}"),
    sa.Column('staff', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Key staff: [{'name': 'Scott', 'role_title': 'Director'}]"),
    sa.Column('included_roles', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Roles confirmed for inclusion in the matrix: ['Director', ...]"),
    sa.Column('pasted_notes', sa.Text(), nullable=True, comment='Pasted responsibilities lists, org chart text or notes'),
    sa.Column('extracted_responsibilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Per-person responsibilities extracted from the inputs'),
    sa.Column('matrix_rows', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Ordered matrix rows. Each row matches the Job Roles columns: name, role_description, time, priorities, retain, gain, lose, action, resp, when'),
    sa.Column('matrix_edited', sa.Boolean(), server_default='false', nullable=False, comment='Whether the advisor has edited the generated matrix'),
    sa.Column('ai_model_used', sa.String(length=100), nullable=True, comment='AI model used'),
    sa.Column('ai_tokens_used', sa.Integer(), nullable=True, comment='Total tokens used in AI processing'),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='Whether this record has been soft deleted'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True, comment='When the matrix was first exported'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_roles_matrices_created_by_user_id'), 'roles_matrices', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_roles_matrices_engagement_id'), 'roles_matrices', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_roles_matrices_status'), 'roles_matrices', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_roles_matrices_status'), table_name='roles_matrices')
    op.drop_index(op.f('ix_roles_matrices_engagement_id'), table_name='roles_matrices')
    op.drop_index(op.f('ix_roles_matrices_created_by_user_id'), table_name='roles_matrices')
    op.drop_table('roles_matrices')
