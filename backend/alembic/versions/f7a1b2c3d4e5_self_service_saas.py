"""self-service (SaaS) tier: business owner signup, billing and team members

Feature 7. Adds:
  - users.account_type ('advisory' | 'self_service') - a self-service business
    owner keeps UserRole.CLIENT, this is what tells the two apart
  - engagements.primary_advisor_id becomes nullable - a self-service engagement
    has no advisor (Feature 9 fills it in later on upsell)
  - subscriptions.user_id / program / provider - owner-scoped subscriptions
  - owner_team_members, signup_intents

Written idempotently (inspector guards) to match the style of
create_firms_and_subscriptions_tables.py, because several environments have
drifted from the migration history.

Revision ID: f7a1b2c3d4e5
Revises: 45bdcc478ace
Create Date: 2026-07-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f7a1b2c3d4e5'
down_revision = '45bdcc478ace'
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {c['name'] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. users.account_type
    # ------------------------------------------------------------------
    if not _has_column('users', 'account_type'):
        op.add_column(
            'users',
            sa.Column(
                'account_type',
                sa.String(length=20),
                nullable=False,
                server_default='advisory',
                comment="How the account was provisioned: 'advisory' (by an advisor/admin) or 'self_service' (direct SaaS signup)",
            ),
        )

    # users.role is VARCHAR(50), not a PG enum - converted by
    # 662a7acdc7ea_first_name_last_name.py - so 'team_member' needs no DDL.
    # Belt and braces for environments whose DB predates that conversion and
    # still has the userrole type bound to the column: add the value if the
    # type exists. ALTER TYPE ... ADD VALUE cannot run inside a transaction on
    # PG < 12, hence the explicit COMMIT.
    op.execute("COMMIT")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'userrole' AND e.enumlabel = 'team_member'
                ) THEN
                    ALTER TYPE userrole ADD VALUE 'team_member';
                END IF;
            END IF;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # 2. engagements.primary_advisor_id -> nullable
    # ------------------------------------------------------------------
    if _has_column('engagements', 'primary_advisor_id'):
        op.alter_column(
            'engagements',
            'primary_advisor_id',
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
            comment='Foreign key to users (main advisor). NULL for self-service engagements.',
        )

    # ------------------------------------------------------------------
    # 3. subscriptions: owner-scoped columns
    # ------------------------------------------------------------------
    if not _has_column('subscriptions', 'user_id'):
        op.add_column(
            'subscriptions',
            sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True,
                      comment='Foreign key to users (the self-service business owner). NULL for firm subscriptions.'),
        )
        op.create_foreign_key(
            'fk_subscriptions_user_id', 'subscriptions', 'users', ['user_id'], ['id'], ondelete='CASCADE',
        )
        op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'], unique=False)

    if not _has_column('subscriptions', 'program'):
        op.add_column(
            'subscriptions',
            sa.Column('program', sa.String(length=50), nullable=True,
                      comment='Program bought: value_builder or sale_ready. NULL for firm subscriptions.'),
        )

    if not _has_column('subscriptions', 'provider'):
        op.add_column(
            'subscriptions',
            sa.Column('provider', sa.String(length=20), nullable=False, server_default='manual',
                      comment='Billing provider that owns this subscription: manual or stripe'),
        )

    # ------------------------------------------------------------------
    # 4. owner_team_members
    # ------------------------------------------------------------------
    if not _has_table('owner_team_members'):
        op.create_table(
            'owner_team_members',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('owner_user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('member_user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('access_level', sa.String(length=20), nullable=False, server_default='viewer',
                      comment='Access level: collaborator or viewer'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='invited',
                      comment='Membership status: invited, active, revoked'),
            sa.Column('invited_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['member_user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('id'),
            sa.UniqueConstraint('owner_user_id', 'member_user_id', name='uq_owner_team_member'),
        )
        op.create_index('ix_owner_team_members_owner_user_id', 'owner_team_members', ['owner_user_id'], unique=False)
        op.create_index('ix_owner_team_members_member_user_id', 'owner_team_members', ['member_user_id'], unique=False)
        op.create_index('ix_owner_team_members_status', 'owner_team_members', ['status'], unique=False)

    # ------------------------------------------------------------------
    # 5. signup_intents
    # ------------------------------------------------------------------
    if not _has_table('signup_intents'):
        op.create_table(
            'signup_intents',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=True),
            sa.Column('business_name', sa.String(length=255), nullable=True),
            sa.Column('program', sa.String(length=50), nullable=False,
                      comment='Selected program: value_builder or sale_ready'),
            sa.Column('plan_name', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending',
                      comment='Intent status: pending, consumed, expired'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('id'),
        )
        op.create_index('ix_signup_intents_email', 'signup_intents', ['email'], unique=False)
        op.create_index('ix_signup_intents_status', 'signup_intents', ['status'], unique=False)


def downgrade() -> None:
    if _has_table('signup_intents'):
        op.drop_index('ix_signup_intents_status', table_name='signup_intents')
        op.drop_index('ix_signup_intents_email', table_name='signup_intents')
        op.drop_table('signup_intents')

    if _has_table('owner_team_members'):
        op.drop_index('ix_owner_team_members_status', table_name='owner_team_members')
        op.drop_index('ix_owner_team_members_member_user_id', table_name='owner_team_members')
        op.drop_index('ix_owner_team_members_owner_user_id', table_name='owner_team_members')
        op.drop_table('owner_team_members')

    if _has_column('subscriptions', 'provider'):
        op.drop_column('subscriptions', 'provider')
    if _has_column('subscriptions', 'program'):
        op.drop_column('subscriptions', 'program')
    if _has_column('subscriptions', 'user_id'):
        op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
        op.drop_constraint('fk_subscriptions_user_id', 'subscriptions', type_='foreignkey')
        op.drop_column('subscriptions', 'user_id')

    # Restoring NOT NULL would fail if any self-service engagement exists, so
    # clear those rows' engagements first is NOT done here - instead we only
    # restore the constraint when it is safe to do so.
    if _has_column('engagements', 'primary_advisor_id'):
        orphaned = op.get_bind().execute(
            sa.text('SELECT COUNT(*) FROM engagements WHERE primary_advisor_id IS NULL')
        ).scalar()
        if not orphaned:
            op.alter_column(
                'engagements',
                'primary_advisor_id',
                existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=False,
                comment='Foreign key to users (main advisor)',
            )

    if _has_column('users', 'account_type'):
        op.drop_column('users', 'account_type')
