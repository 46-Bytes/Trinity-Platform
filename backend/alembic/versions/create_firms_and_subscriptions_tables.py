"""create firms and subscriptions tables

Revision ID: create_firms_subs
Revises: 662a7acdc7ea
Create Date: 2025-01-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'create_firms_subs'
down_revision = 'a1b2c3d4e5f6'  # After the merge migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if tables already exist
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    # Create subscriptions table first (firms depends on it)
    if 'subscriptions' not in tables:
        op.create_table('subscriptions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('plan_name', sa.String(length=50), nullable=False, comment="Subscription plan name (e.g., 'professional', 'enterprise')"),
            sa.Column('seat_count', sa.Integer(), nullable=False, comment='Number of seats in the subscription'),
            sa.Column('monthly_price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Monthly subscription price'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='active', comment='Subscription status: active, cancelled, past_due, trialing'),
            sa.Column('current_period_start', sa.DateTime(), nullable=False, comment='Start of current billing period'),
            sa.Column('current_period_end', sa.DateTime(), nullable=False, comment='End of current billing period'),
            sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True, unique=True, comment='Stripe subscription ID'),
            sa.Column('stripe_customer_id', sa.String(length=255), nullable=True, comment='Stripe customer ID'),
            sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false', comment='Whether subscription will cancel at period end'),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True, comment='When subscription was cancelled'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('id'),
            comment='Tracks firm subscription and billing information'
        )
        # Create indexes if they don't exist
        sub_indexes = [idx['name'] for idx in inspector.get_indexes('subscriptions')]
        if 'ix_subscriptions_stripe_subscription_id' not in sub_indexes:
            op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'], unique=True)
        if 'ix_subscriptions_stripe_customer_id' not in sub_indexes:
            op.create_index('ix_subscriptions_stripe_customer_id', 'subscriptions', ['stripe_customer_id'])
    
    # Create firms table
    if 'firms' not in tables:
        op.create_table('firms',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('firm_name', sa.String(length=255), nullable=False, comment='Name of the firm/organization'),
            sa.Column('firm_admin_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True, comment='Foreign key to users (the Firm Admin)'),
            sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=True, unique=True, index=True, comment='Foreign key to subscriptions'),
            sa.Column('subscription_plan', sa.String(length=50), nullable=True, comment="Subscription plan name (e.g., 'professional', 'enterprise')"),
            sa.Column('seat_count', sa.Integer(), nullable=False, default=5, comment='Number of seats purchased (minimum 5)'),
            sa.Column('seats_used', sa.Integer(), nullable=False, default=1, comment='Number of active advisor seats in use'),
            sa.Column('billing_email', sa.String(length=255), nullable=True, comment='Email for billing notifications'),
            sa.Column('clients', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True, comment='Array of client user IDs associated with this firm'),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Whether the firm account is active'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['firm_admin_id'], ['users.id'], ondelete='RESTRICT'),
            sa.UniqueConstraint('id'),
            comment='Firm represents an organization that employs multiple advisors'
        )
    else:
        # Table exists, check if index exists before creating
        indexes = [idx['name'] for idx in inspector.get_indexes('firms')]
        if 'ix_firms_subscription_id' not in indexes:
            op.create_index('ix_firms_subscription_id', 'firms', ['subscription_id'], unique=True)


def downgrade() -> None:
    # Drop tables in reverse order
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'firms' in tables:
        op.drop_table('firms')
    
    if 'subscriptions' in tables:
        op.drop_table('subscriptions')

