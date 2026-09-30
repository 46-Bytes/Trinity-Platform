"""Sale Ready gap fixes: DD-item file link and buyer company.

Items 7 (media) and 10 (engagement_buyer) of the Sale Ready gap-closing work.
Adds nullable columns only, so there's no backfill.

Revision ID: add_sale_ready_gap_fixes
Revises: add_drive_data_room
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_sale_ready_gap_fixes"
down_revision = "add_drive_data_room"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- media: item 7 (the DD item a file was uploaded from) ---------------
    op.add_column(
        "media",
        sa.Column("dd_item_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="DD item the file was uploaded from (Sale Ready)"),
    )
    op.create_foreign_key(
        "fk_media_dd_item_id", "media", "engagement_dd_item",
        ["dd_item_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_media_dd_item_id", "media", ["dd_item_id"])

    # --- engagement_buyer: item 10 (buyer company) ---------------------------
    op.add_column("engagement_buyer", sa.Column("company", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("engagement_buyer", "company")

    op.drop_index("ix_media_dd_item_id", table_name="media")
    op.drop_constraint("fk_media_dd_item_id", "media", type_="foreignkey")
    op.drop_column("media", "dd_item_id")
