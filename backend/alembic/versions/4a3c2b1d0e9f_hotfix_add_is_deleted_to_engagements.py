"""Hotfix: add is_deleted column to engagements

Revision ID: 4a3c2b1d0e9f
Revises: add_plan_notes_to_bba
Create Date: 2026-02-11

This migration exists because some databases were stamped to head without
actually applying the earlier is_deleted migration for engagements.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4a3c2b1d0e9f"
down_revision = "add_plan_notes_to_bba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres-safe idempotent add (avoids failure if column already exists)
    op.execute(
        """
        ALTER TABLE engagements
        ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        """
    )


def downgrade() -> None:
    # Postgres-safe idempotent drop
    op.execute(
        """
        ALTER TABLE engagements
        DROP COLUMN IF EXISTS is_deleted
        """
    )



