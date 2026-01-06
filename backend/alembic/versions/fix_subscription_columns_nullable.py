"""fix subscription columns to be nullable

Revision ID: fix_subscription_cols
Revises: fix_price_nullable
Create Date: 2026-01-06 08:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_subscription_cols'
down_revision = 'fix_price_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make unused columns nullable - force update."""
    # Use raw SQL to ensure columns are made nullable
    op.execute("""
        DO $$
        BEGIN
            -- Make price nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='price' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN price DROP NOT NULL;
            END IF;
            
            -- Make start_date nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='start_date' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN start_date DROP NOT NULL;
            END IF;
            
            -- Make end_date nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='end_date' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN end_date DROP NOT NULL;
            END IF;
            
            -- Make billing_period nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='billing_period' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN billing_period DROP NOT NULL;
            END IF;
            
            -- Make currency nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='currency' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN currency DROP NOT NULL;
            END IF;
            
            -- Make next_billing_date nullable
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='next_billing_date' AND is_nullable='NO') THEN
                ALTER TABLE subscriptions ALTER COLUMN next_billing_date DROP NOT NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Restore NOT NULL constraints if needed."""
    op.execute("""
        DO $$
        BEGIN
            -- Restore NOT NULL constraints (you may need to update existing NULL values first)
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='start_date' AND is_nullable='YES') THEN
                ALTER TABLE subscriptions ALTER COLUMN start_date SET NOT NULL;
            END IF;
            
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='subscriptions' AND column_name='price' AND is_nullable='YES') THEN
                ALTER TABLE subscriptions ALTER COLUMN price SET NOT NULL;
            END IF;
        END $$;
    """)

