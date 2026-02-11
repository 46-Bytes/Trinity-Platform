"""add read_by to notes

Revision ID: add_read_by_to_notes
Revises: 79dc61b1e153
Create Date: 2026-02-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID


# revision identifiers, used by Alembic.
revision = "add_read_by_to_notes"
down_revision = "79dc61b1e153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add read_by array column to notes table
    op.add_column(
        "notes",
        sa.Column(
            "read_by",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
            comment="Array of user IDs who have read this note",
        ),
    )

    # Backfill existing notes so that authors are marked as having read their own notes
    op.execute("UPDATE notes SET read_by = ARRAY[author_id]")


def downgrade() -> None:
    # Remove column
    op.drop_column("notes", "read_by")


