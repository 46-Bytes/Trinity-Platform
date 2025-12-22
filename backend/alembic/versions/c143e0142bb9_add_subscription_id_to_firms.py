"""add_subscription_id_to_firms

Revision ID: c143e0142bb9
Revises: 686ebbdaca62
Create Date: 2025-12-22 11:13:44.159497

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c143e0142bb9'
down_revision = '686ebbdaca62'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add subscription_id column to firms table
    op.add_column('firms', 
        sa.Column('subscription_id', 
                  postgresql.UUID(as_uuid=True), 
                  nullable=True,
                  comment='Foreign key to subscriptions'))
    op.create_index(op.f('ix_firms_subscription_id'), 'firms', ['subscription_id'], unique=True)
    op.create_foreign_key(
        'firms_subscription_id_fkey',
        'firms', 'subscriptions',
        ['subscription_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove subscription_id column from firms table
    op.drop_constraint('firms_subscription_id_fkey', 'firms', type_='foreignkey')
    op.drop_index(op.f('ix_firms_subscription_id'), table_name='firms')
    op.drop_column('firms', 'subscription_id')



