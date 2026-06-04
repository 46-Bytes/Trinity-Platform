"""partial unique index on email for active users

Revision ID: partial_unique_email_active_users
Revises: add_is_deleted_to_child_models
Create Date: 2026-06-03

Replaces the global unique index on users.email with a partial unique index
that only enforces uniqueness among non-deleted users. This allows the same
email to be re-registered after a user has been soft-deleted.
"""
from alembic import op

revision = 'partial_email_idx'
down_revision = 'add_is_deleted_to_child_models'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_users_email', table_name='users')
    op.execute(
        "CREATE UNIQUE INDEX ix_users_email_active ON users (email) WHERE is_deleted = FALSE"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_users_email_active")
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
