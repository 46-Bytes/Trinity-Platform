"""add_monthly_price_and_firm_id_to_subscriptions

Revision ID: add_monthly_price_firm_id
Revises: 67fb5521ba93
Create Date: 2026-01-05 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_monthly_price_firm_id'
down_revision = '67fb5521ba93'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing columns to subscriptions table if they don't exist."""
    from sqlalchemy import inspect
    from datetime import datetime
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'subscriptions' in tables:
        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        
        # Add monthly_price column if it doesn't exist
        if 'monthly_price' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'monthly_price',
                    sa.Numeric(precision=10, scale=2),
                    nullable=False,
                    server_default='0.00',
                    comment='Monthly subscription price'
                )
            )
        
        # Add current_period_start column if it doesn't exist
        if 'current_period_start' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'current_period_start',
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'),
                    comment='Start of current billing period'
                )
            )
        
        # Add current_period_end column if it doesn't exist
        if 'current_period_end' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'current_period_end',
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'),
                    comment='End of current billing period'
                )
            )
        
        # Add cancel_at_period_end column if it doesn't exist
        if 'cancel_at_period_end' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'cancel_at_period_end',
                    sa.Boolean(),
                    nullable=False,
                    server_default='false',
                    comment='Whether subscription will cancel at period end'
                )
            )
        
        # Add cancelled_at column if it doesn't exist
        if 'cancelled_at' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'cancelled_at',
                    sa.DateTime(),
                    nullable=True,
                    comment='When subscription was cancelled'
                )
            )
        
        # Add firm_id column if it doesn't exist
        if 'firm_id' not in columns:
            op.add_column(
                'subscriptions',
                sa.Column(
                    'firm_id',
                    postgresql.UUID(as_uuid=True),
                    nullable=True,
                    comment='Foreign key to firms (nullable - subscription can exist without a firm)'
                )
            )
            # Add foreign key constraint (only if firms table exists)
            if 'firms' in tables:
                op.create_foreign_key(
                    'subscriptions_firm_id_fkey',
                    'subscriptions',
                    'firms',
                    ['firm_id'],
                    ['id'],
                    ondelete='SET NULL'
                )
            # Add index (non-unique since multiple subscriptions can be unassigned)
            op.create_index('ix_subscriptions_firm_id', 'subscriptions', ['firm_id'], unique=False)
        else:
            # If firm_id exists, ensure it has the correct foreign key constraint
            if 'firms' in tables:
                constraints = [fk['name'] for fk in inspector.get_foreign_keys('subscriptions')]
                if 'subscriptions_firm_id_fkey' not in constraints:
                    op.create_foreign_key(
                        'subscriptions_firm_id_fkey',
                        'subscriptions',
                        'firms',
                        ['firm_id'],
                        ['id'],
                        ondelete='SET NULL'
                    )
            
            # Ensure index exists (non-unique)
            indexes = [idx['name'] for idx in inspector.get_indexes('subscriptions')]
            if 'ix_subscriptions_firm_id' not in indexes:
                op.create_index('ix_subscriptions_firm_id', 'subscriptions', ['firm_id'], unique=False)


def downgrade() -> None:
    """Remove added columns from subscriptions table."""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'subscriptions' in tables:
        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        
        if 'firm_id' in columns:
            # Drop foreign key constraint and index first
            constraints = [fk['name'] for fk in inspector.get_foreign_keys('subscriptions')]
            if 'subscriptions_firm_id_fkey' in constraints:
                op.drop_constraint('subscriptions_firm_id_fkey', 'subscriptions', type_='foreignkey')
            
            indexes = [idx['name'] for idx in inspector.get_indexes('subscriptions')]
            if 'ix_subscriptions_firm_id' in indexes:
                op.drop_index('ix_subscriptions_firm_id', table_name='subscriptions')
            
            op.drop_column('subscriptions', 'firm_id')
        
        if 'monthly_price' in columns:
            op.drop_column('subscriptions', 'monthly_price')
        
        if 'current_period_start' in columns:
            op.drop_column('subscriptions', 'current_period_start')
        
        if 'current_period_end' in columns:
            op.drop_column('subscriptions', 'current_period_end')
        
        if 'cancel_at_period_end' in columns:
            op.drop_column('subscriptions', 'cancel_at_period_end')
        
        if 'cancelled_at' in columns:
            op.drop_column('subscriptions', 'cancelled_at')

