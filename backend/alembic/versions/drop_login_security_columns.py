"""drop login security columns

Revision ID: drop_login_security_cols
Revises: 45bdcc478ace
Create Date: 2026-08-24

Removes users.failed_login_attempts and users.locked_until, added by
f227a49caf86_add_login_security_columns for an account-lockout feature that was
never implemented. Neither column was ever present on the User model and no
backend or frontend code reads or writes them.

Both operations are guarded by an inspector check because environments differ on
whether these columns exist.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_login_security_cols'
down_revision = '45bdcc478ace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'locked_until' in columns:
        op.drop_column('users', 'locked_until')
    if 'failed_login_attempts' in columns:
        op.drop_column('users', 'failed_login_attempts')


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'failed_login_attempts' not in columns:
        op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False, comment='Number of consecutive failed login attempts'))
    if 'locked_until' not in columns:
        op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True, comment='Account locked until this time after too many failed attempts'))
