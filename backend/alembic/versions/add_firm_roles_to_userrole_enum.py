"""Add firm_admin and firm_advisor to userrole enum

Revision ID: a1b2c3d4e5f6
Revises: 6d6185e73276
Create Date: 2025-12-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '6d6185e73276'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values to userrole enum
    # PostgreSQL requires adding enum values one at a time
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_admin'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'firm_advisor'")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave a comment that manual intervention may be needed
    # In production, you might want to:
    # 1. Create a new enum with only the old values
    # 2. Update all columns to use the new enum
    # 3. Drop the old enum
    # 4. Rename the new enum
    pass

