"""add buyer access: engagement binding, released folders and the access log

Revision ID: add_buyer_access
Revises: add_sale_ready_guide_content
Create Date: 2026-09-23

A buyer is an external party invited to look at one engagement's released data
room and nothing else. Three tables carry that:

- engagement_buyer: which buyer may see which engagement. Revoking sets status
  and leaves the row, because the brief calls revocation a soft delete and the
  access log has to stay attributable afterwards; re-granting flips the same
  row back. A partial unique index on user_id, covering only live rows, is what
  enforces "one engagement per buyer account" - a revoked binding drops out, so
  the same person can be invited elsewhere once their access has ended.
- engagement_released_folder: the folders an advisor has made visible to
  buyers, keyed by due diligence category and sub-item. Nothing is released by
  default; a folder with no row here is invisible to every buyer. Withdrawing
  sets is_deleted so a folder released, withdrawn and released again keeps one
  row and one history.
- buyer_access_log: every list, open and download. Append-only - rows are never
  updated or deleted, including when the binding is revoked.

Purely additive: three new tables, nothing existing is altered and no data is
written or migrated.

users.role is deliberately untouched. It is varchar(50), not the userrole
Postgres enum (which that column stopped using long ago), so the new 'buyer'
value needs no DDL - only the Python enum and its type decorator, which are
already in this branch.

Downgrade drops all three tables. Every buyer binding, every release decision
and the whole access log are lost with them; the buyer user accounts themselves
survive, as do their Auth0 accounts, so a downgrade leaves people who can log
in but reach nothing - which is the correct end state for a feature that has
been removed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_buyer_access'
down_revision = 'add_sale_ready_guide_content'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- engagement_buyer ------------------------------------------------
    op.create_table(
        'engagement_buyer',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active',
                  comment="'active' or 'revoked'; revoking never deletes the row"),
        sa.Column('invited_by_user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('nda_signed_date', sa.Date(), nullable=True,
                  comment="When the NDA was signed outside Trinity; record only"),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                name='fk_engagement_buyer_engagement'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_engagement_buyer_user'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL',
                                name='fk_engagement_buyer_invited_by'),
        sa.UniqueConstraint('engagement_id', 'user_id',
                            name='uq_engagement_buyer_engagement_user'),
    )
    # One live engagement per buyer account. Revoked and deleted rows fall out
    # of the index, so a buyer can be invited elsewhere once access has ended.
    op.create_index(
        'uq_engagement_buyer_one_live_per_user', 'engagement_buyer', ['user_id'], unique=True,
        postgresql_where=sa.text("status = 'active' AND is_deleted = false"),
    )
    op.create_index('ix_engagement_buyer_engagement', 'engagement_buyer',
                    ['engagement_id', 'status'])

    # ---- engagement_released_folder --------------------------------------
    op.create_table(
        'engagement_released_folder',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
        sa.Column('category_code', sa.String(10), nullable=False,
                  comment="DD category number, e.g. '3'"),
        sa.Column('sub_item_code', sa.String(10), nullable=False,
                  comment="DD sub-item number, e.g. '3.1'; one data room folder"),
        sa.Column('released_by_user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                name='fk_engagement_released_folder_engagement'),
        sa.ForeignKeyConstraint(['released_by_user_id'], ['users.id'], ondelete='SET NULL',
                                name='fk_engagement_released_folder_released_by'),
        sa.UniqueConstraint('engagement_id', 'category_code', 'sub_item_code',
                            name='uq_engagement_released_folder_folder'),
    )

    # ---- buyer_access_log ------------------------------------------------
    op.create_table(
        'buyer_access_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('media_id', UUID(as_uuid=True), nullable=True,
                  comment="The document, when the action was about one"),
        sa.Column('action', sa.String(30), nullable=False, comment="'list', 'view' or 'download'"),
        sa.Column('detail', sa.Text(), nullable=True,
                  comment="What was listed or opened, for actions with no media row"),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                name='fk_buyer_access_log_engagement'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE',
                                name='fk_buyer_access_log_user'),
        # The document may be removed later; the record that it was opened stays.
        sa.ForeignKeyConstraint(['media_id'], ['media.id'], ondelete='SET NULL',
                                name='fk_buyer_access_log_media'),
    )
    op.create_index('ix_buyer_access_log_engagement_time', 'buyer_access_log',
                    ['engagement_id', 'created_at'])
    op.create_index('ix_buyer_access_log_user_time', 'buyer_access_log',
                    ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_buyer_access_log_user_time', table_name='buyer_access_log')
    op.drop_index('ix_buyer_access_log_engagement_time', table_name='buyer_access_log')
    op.drop_table('buyer_access_log')

    op.drop_table('engagement_released_folder')

    op.drop_index('ix_engagement_buyer_engagement', table_name='engagement_buyer')
    op.drop_index('uq_engagement_buyer_one_live_per_user', table_name='engagement_buyer')
    op.drop_table('engagement_buyer')
