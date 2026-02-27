"""add engagement_id, diagnostic_id, created_by_user_id, diagnostic_context to strategy_workbooks

Revision ID: sw_diagnostic_ctx
Revises: merge_strategy_workbooks
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'sw_diagnostic_ctx'
down_revision = 'merge_strategy_workbooks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'strategy_workbooks',
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=True, comment='Optional link to engagement'),
    )
    op.add_column(
        'strategy_workbooks',
        sa.Column('diagnostic_id', UUID(as_uuid=True), nullable=True, comment='When created from a completed diagnostic'),
    )
    op.add_column(
        'strategy_workbooks',
        sa.Column('created_by_user_id', UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'strategy_workbooks',
        sa.Column('diagnostic_context', JSONB, nullable=True, comment='Diagnostic report/ai_analysis used as context'),
    )

    # Foreign keys
    op.create_foreign_key(
        'fk_strategy_workbooks_engagement_id',
        'strategy_workbooks', 'engagements',
        ['engagement_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_strategy_workbooks_diagnostic_id',
        'strategy_workbooks', 'diagnostics',
        ['diagnostic_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_strategy_workbooks_created_by_user_id',
        'strategy_workbooks', 'users',
        ['created_by_user_id'], ['id'],
        ondelete='SET NULL',
    )

    # Indexes
    op.create_index('ix_strategy_workbooks_engagement_id', 'strategy_workbooks', ['engagement_id'])
    op.create_index('ix_strategy_workbooks_diagnostic_id', 'strategy_workbooks', ['diagnostic_id'])
    op.create_index('ix_strategy_workbooks_created_by_user_id', 'strategy_workbooks', ['created_by_user_id'])


def downgrade() -> None:
    op.drop_index('ix_strategy_workbooks_created_by_user_id', table_name='strategy_workbooks')
    op.drop_index('ix_strategy_workbooks_diagnostic_id', table_name='strategy_workbooks')
    op.drop_index('ix_strategy_workbooks_engagement_id', table_name='strategy_workbooks')

    op.drop_constraint('fk_strategy_workbooks_created_by_user_id', 'strategy_workbooks', type_='foreignkey')
    op.drop_constraint('fk_strategy_workbooks_diagnostic_id', 'strategy_workbooks', type_='foreignkey')
    op.drop_constraint('fk_strategy_workbooks_engagement_id', 'strategy_workbooks', type_='foreignkey')

    op.drop_column('strategy_workbooks', 'diagnostic_context')
    op.drop_column('strategy_workbooks', 'created_by_user_id')
    op.drop_column('strategy_workbooks', 'diagnostic_id')
    op.drop_column('strategy_workbooks', 'engagement_id')
