"""add_subscription_id_to_firms

Revision ID: c143e0142bb9
Revises: b2465e2f298a
Create Date: 2025-12-22 11:13:44.159497

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c143e0142bb9'
down_revision = 'b2465e2f298a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if firms table exists before trying to modify it
    # This allows the migration to run even if firms table hasn't been created yet
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'firms' in tables:
        # Add subscription_id column to firms table
        # Check if column already exists
        columns = [col['name'] for col in inspector.get_columns('firms')]
        if 'subscription_id' not in columns:
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
    # If firms table doesn't exist, skip this migration (it will be applied when firms table is created)


def downgrade() -> None:
    # Check if firms table exists before trying to modify it
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'firms' in tables:
        columns = [col['name'] for col in inspector.get_columns('firms')]
        if 'subscription_id' in columns:
            # Remove subscription_id column from firms table
            op.drop_constraint('firms_subscription_id_fkey', 'firms', type_='foreignkey')
            op.drop_index(op.f('ix_firms_subscription_id'), table_name='firms')
            op.drop_column('firms', 'subscription_id')



