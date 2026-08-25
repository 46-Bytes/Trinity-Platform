"""align schema with models

Revision ID: align_schema_models
Revises: drop_login_security_cols
Create Date: 2026-08-24

Closes the remaining gaps found by diffing a freshly-migrated database against
the SQLAlchemy models:

1. impersonation_sessions.original_user_id / impersonated_user_id are declared
   index=True on the model but no migration ever created those indexes. Existing
   databases have them (created out-of-band); fresh installs did not.

2. subscriptions.stripe_subscription_id / stripe_customer_id are created by
   create_firms_and_subscriptions_tables, but only on databases where that
   migration's `if 'subscriptions' not in tables` branch fired - i.e. fresh
   installs. Neither column is on the Subscription model, Stripe is not a
   dependency, and no application code references them. Dropping them makes
   fresh and existing databases agree.

All operations are guarded, so this is a no-op wherever the state already matches.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'align_schema_models'
down_revision = 'drop_login_security_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. missing impersonation_sessions indexes
    if 'impersonation_sessions' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('impersonation_sessions')]
        for col in ('original_user_id', 'impersonated_user_id'):
            name = 'ix_impersonation_sessions_%s' % col
            if name not in indexes:
                op.create_index(name, 'impersonation_sessions', [col])

    # 2. unused Stripe columns on fresh installs
    if 'subscriptions' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('subscriptions')]
        for name in ('ix_subscriptions_stripe_subscription_id',
                     'ix_subscriptions_stripe_customer_id'):
            if name in indexes:
                op.drop_index(name, table_name='subscriptions')

        uniques = [uc['name'] for uc in inspector.get_unique_constraints('subscriptions')]
        if 'subscriptions_stripe_subscription_id_key' in uniques:
            op.drop_constraint('subscriptions_stripe_subscription_id_key',
                               'subscriptions', type_='unique')

        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        for col in ('stripe_subscription_id', 'stripe_customer_id'):
            if col in columns:
                op.drop_column('subscriptions', col)


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'subscriptions' in tables:
        columns = [col['name'] for col in inspector.get_columns('subscriptions')]
        if 'stripe_subscription_id' not in columns:
            op.add_column('subscriptions', sa.Column('stripe_subscription_id', sa.String(length=255),
                                                     nullable=True, comment='Stripe subscription ID'))
            op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions',
                            ['stripe_subscription_id'], unique=True)
        if 'stripe_customer_id' not in columns:
            op.add_column('subscriptions', sa.Column('stripe_customer_id', sa.String(length=255),
                                                     nullable=True, comment='Stripe customer ID'))
            op.create_index('ix_subscriptions_stripe_customer_id', 'subscriptions',
                            ['stripe_customer_id'])

    if 'impersonation_sessions' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('impersonation_sessions')]
        for col in ('original_user_id', 'impersonated_user_id'):
            name = 'ix_impersonation_sessions_%s' % col
            if name in indexes:
                op.drop_index(name, table_name='impersonation_sessions')
