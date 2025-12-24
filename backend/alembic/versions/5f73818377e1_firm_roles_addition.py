"""firm_roles_addition

Revision ID: 5f73818377e1
Revises: b2465e2f298a
Create Date: 2025-12-24 14:44:48.450818

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5f73818377e1'
down_revision = 'b2465e2f298a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values to userrole enum (if not already present)
    # PostgreSQL requires adding enum values one at a time
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_advisor'")
    
    # Update column comment
    op.alter_column('users', 'role',
               existing_type=postgresql.ENUM('ADVISOR', 'CLIENT', 'ADMIN', 'SUPER_ADMIN', 'firm_admin', 'firm_advisor', name='userrole'),
               comment='User role (advisor, client, admin, super_admin, firm_admin, firm_advisor)',
               existing_comment='User role (advisor, client, admin, super_admin)',
               existing_nullable=False)
    
    # Update task priority comment
    op.alter_column('tasks', 'priority',
               existing_type=sa.VARCHAR(length=20),
               comment='low, medium, high, critical',
               existing_comment='low, medium, high, urgent',
               existing_nullable=False,
               existing_server_default=sa.text("'medium'::character varying"))


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll revert the comments only
    
    # Revert column comment
    op.alter_column('users', 'role',
               existing_type=postgresql.ENUM('ADVISOR', 'CLIENT', 'ADMIN', 'SUPER_ADMIN', 'firm_admin', 'firm_advisor', name='userrole'),
               comment='User role (advisor, client, admin, super_admin)',
               existing_comment='User role (advisor, client, admin, super_admin, firm_admin, firm_advisor)',
               existing_nullable=False)
    
    # Revert task priority comment
    op.alter_column('tasks', 'priority',
               existing_type=sa.VARCHAR(length=20),
               comment='low, medium, high, urgent',
               existing_comment='low, medium, high, critical',
               existing_nullable=False,
               existing_server_default=sa.text("'medium'::character varying"))



