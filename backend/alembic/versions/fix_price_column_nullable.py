"""make price column nullable in subscriptions

Revision ID: fix_price_nullable
Revises: add_monthly_price_firm_id
Create Date: 2026-01-06 07:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fix_price_nullable'
down_revision = 'add_monthly_price_firm_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make unused columns nullable since we're using monthly_price instead."""
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'subscriptions' in tables:
        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        
        # Columns that exist in DB but not in our model - make them nullable
        columns_to_fix = [
            'price',
            'start_date',
            'end_date',
            'billing_period',
            'currency',
            'next_billing_date'
        ]
        
        for col_name in columns_to_fix:
            if col_name in columns:
                try:
                    # Try to make it nullable - will fail silently if already nullable or doesn't exist
                    op.alter_column('subscriptions', col_name, nullable=True)
                except Exception:
                    # Column might already be nullable or have constraints, skip it
                    pass


def downgrade() -> None:
    """Restore columns as NOT NULL if needed."""
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'subscriptions' in tables:
        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        
        # Restore NOT NULL constraints if columns exist
        if 'price' in columns:
            op.alter_column('subscriptions', 'price', nullable=False)
        if 'start_date' in columns:
            op.alter_column('subscriptions', 'start_date', nullable=False)

