"""add_impersonation_sessions

Revision ID: af13aec12199
Revises: remove_unique_sub_id
Create Date: 2026-01-15 16:42:09.989237

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'af13aec12199'
down_revision = 'remove_unique_sub_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create impersonation_sessions table
    op.create_table(
        'impersonation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for the impersonation session'),
        sa.Column('original_user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='The superadmin user who is impersonating'),
        sa.Column('impersonated_user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='The user being impersonated'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active', comment="Session status: 'active' or 'ended'"),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='When the impersonation session was created'),
        sa.Column('ended_at', sa.DateTime(), nullable=True, comment='When the impersonation session was ended'),
        sa.ForeignKeyConstraint(['original_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['impersonated_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_impersonation_original_user', 'impersonation_sessions', ['original_user_id'])
    op.create_index('idx_impersonation_impersonated_user', 'impersonation_sessions', ['impersonated_user_id'])
    op.create_index('idx_impersonation_status', 'impersonation_sessions', ['status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_impersonation_status', table_name='impersonation_sessions')
    op.drop_index('idx_impersonation_impersonated_user', table_name='impersonation_sessions')
    op.drop_index('idx_impersonation_original_user', table_name='impersonation_sessions')
    
    # Drop table
    op.drop_table('impersonation_sessions')