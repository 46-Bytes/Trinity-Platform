"""add the Google Drive data room: connection, folder map and file index

Revision ID: add_drive_data_room
Revises: add_buyer_access
Create Date: 2026-09-29

Drive becomes the data room's store and Trinity keeps no copy of the bytes.
Three things change:

- drive_integration: one row holding the OAuth connection to Benchmark's
  central Google account, the root folder id, and the Drive changes cursor.
  OAuth rather than a service account, so a refresh token has to be stored;
  it is encrypted by the application before it reaches this column. A partial
  unique index allows exactly one live row - a second connection would mean
  two accounts owning one data room.
- engagement_drive_folder: which Drive folder is which, keyed on engagement_id
  plus the DD category and sub-item. NULLs carry the level: both NULL is the
  engagement's Data room, category only is a category folder, both set is a
  sub-item folder. Folders are always resolved by stored id, never by asking
  Drive for a name.

  Because the level lives in a NULL, one UNIQUE over the three columns would
  not enforce it: Postgres treats NULLs as distinct, so the root and category
  rows could each be inserted twice over and only the sub-item level would
  actually be held. That matters because folder creation is find-then-create
  and the Files tab uploads in parallel - an engagement's first multi-file
  upload fires concurrent requests that each call ensure_data_room, which
  creates rather than adopts, so a race would leave two "{business}/Data room"
  trees and two rows claiming to be the root. Three partial unique indexes,
  one per level, are used instead. Partial indexes rather than UNIQUE NULLS
  NOT DISTINCT, which would be neater but needs Postgres 15+; these work on
  any version and match how uq_drive_integration_single_live below and the
  buyer indexes are already written. A CHECK closes the fourth combination:
  a sub-item with no category is a shape no code path can read.
- media gains the data room index. All the new columns are NULL on every file
  that is not a data room document, which is every file outside Sale Ready.

media.file_path is relaxed to nullable. A data room file has no local path -
that is the point - so the column can no longer be required. Every existing
row keeps its value and nothing is rewritten.

engagement_document_register_entry already exists, created by
add_sale_ready_program_tables. Two adjustments only: document_name is relaxed
to nullable, because the brief takes the name from the file rather than from
the advisor, and media_id gains a unique constraint so one file has at most
one set of register notes. The table has never held a row, so neither is a
data migration.

Purely additive otherwise. No data is written, moved or deleted, and nothing
outside Sale Ready changes behaviour: a NULL drive_file_id is exactly what
every pre-existing media row already has.

Downgrade drops the two new tables and the media columns, and restores both
NOT NULLs. It will fail if any media row has a NULL file_path by then - that
is deliberate. Those rows are data room files whose bytes live only in Drive,
and silently deleting Trinity's only index of them would orphan the whole
data room. Clear them first if a downgrade is really intended.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_drive_data_room'
down_revision = 'add_buyer_access'
branch_labels = None
depends_on = None

# Kept identical on both columns and in app/models. The buyer boundary is the
# real one: advisors and owners reach these links through endpoints a buyer
# cannot call, and the buyer schemas have no field that could carry one.
WEB_LINK_COMMENT = "Drive UI link. Returned to advisors and owners; never to a buyer."


def upgrade() -> None:
    # ---- drive_integration ------------------------------------------------
    op.create_table(
        'drive_integration',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('account_email', sa.String(255), nullable=True,
                  comment="The Google account that authorised Trinity"),
        sa.Column('refresh_token', sa.Text(), nullable=True,
                  comment="Encrypted OAuth refresh token; never logged or returned"),
        sa.Column('root_folder_id', sa.String(255), nullable=True,
                  comment="Drive id of Trinity/Clients"),
        sa.Column('changes_page_token', sa.String(255), nullable=True,
                  comment="Drive changes cursor; NULL means start fresh"),
        sa.Column('status', sa.String(20), nullable=False, server_default='disconnected'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('connected_at', sa.DateTime(), nullable=True),
        sa.Column('connected_by_user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['connected_by_user_id'], ['users.id'], ondelete='SET NULL',
                                name='fk_drive_integration_connected_by'),
    )
    # Exactly one live connection.
    op.create_index(
        'uq_drive_integration_single_live', 'drive_integration',
        [sa.text('(true)')], unique=True,
        postgresql_where=sa.text('is_deleted = false'),
    )

    # ---- engagement_drive_folder ------------------------------------------
    op.create_table(
        'engagement_drive_folder',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), nullable=False),
        sa.Column('category_code', sa.String(10), nullable=True,
                  comment="NULL for the engagement's data room root"),
        sa.Column('sub_item_code', sa.String(10), nullable=True,
                  comment="NULL for a category folder"),
        sa.Column('drive_folder_id', sa.String(255), nullable=False),
        sa.Column('drive_web_link', sa.Text(), nullable=True, comment=WEB_LINK_COMMENT),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE',
                                name='fk_engagement_drive_folder_engagement'),
        # A sub-item cannot belong to no category.
        sa.CheckConstraint('category_code IS NOT NULL OR sub_item_code IS NULL',
                           name='ck_engagement_drive_folder_shape'),
    )
    op.create_index('ix_engagement_drive_folder_engagement_id', 'engagement_drive_folder',
                    ['engagement_id'])
    op.create_index('ix_engagement_drive_folder_drive_id', 'engagement_drive_folder',
                    ['drive_folder_id'])

    # One folder per level. See the module docstring for why these are three
    # partial indexes rather than one UNIQUE over the three columns.
    op.create_index(
        'uq_engagement_drive_folder_root', 'engagement_drive_folder',
        ['engagement_id'], unique=True,
        postgresql_where=sa.text('category_code IS NULL AND sub_item_code IS NULL'),
    )
    op.create_index(
        'uq_engagement_drive_folder_category', 'engagement_drive_folder',
        ['engagement_id', 'category_code'], unique=True,
        postgresql_where=sa.text('category_code IS NOT NULL AND sub_item_code IS NULL'),
    )
    op.create_index(
        'uq_engagement_drive_folder_sub_item', 'engagement_drive_folder',
        ['engagement_id', 'category_code', 'sub_item_code'], unique=True,
        postgresql_where=sa.text('category_code IS NOT NULL AND sub_item_code IS NOT NULL'),
    )

    # ---- media: the data room index ---------------------------------------
    op.add_column('media', sa.Column('drive_file_id', sa.String(255), nullable=True,
                                     comment="Drive file id; the locator when file_path is NULL"))
    op.add_column('media', sa.Column('drive_web_link', sa.Text(), nullable=True,
                                     comment=WEB_LINK_COMMENT))
    op.add_column('media', sa.Column('drive_modified_time', sa.DateTime(), nullable=True,
                                     comment="Drive modifiedTime at last sync; decides conflicts"))
    op.add_column('media', sa.Column('dd_category_code', sa.String(10), nullable=True))
    op.add_column('media', sa.Column('dd_sub_item_code', sa.String(10), nullable=True))
    op.add_column('media', sa.Column('source', sa.String(20), nullable=True,
                                     comment="'trinity' or 'drive'"))
    op.create_index('uq_media_drive_file_id', 'media', ['drive_file_id'], unique=True)
    # Listing one data room folder.
    op.create_index('ix_media_engagement_dd_folder', 'media',
                    ['engagement_id', 'dd_category_code', 'dd_sub_item_code'])

    # A data room file has no local path.
    op.alter_column('media', 'file_path', existing_type=sa.Text(), nullable=True)

    # ---- document register ------------------------------------------------
    # The name comes from the file, so the advisor never types one.
    op.alter_column('engagement_document_register_entry', 'document_name',
                    existing_type=sa.String(255), nullable=True)
    op.create_unique_constraint('uq_engagement_doc_register_media',
                                'engagement_document_register_entry', ['media_id'])


def downgrade() -> None:
    op.drop_constraint('uq_engagement_doc_register_media',
                       'engagement_document_register_entry', type_='unique')
    op.alter_column('engagement_document_register_entry', 'document_name',
                    existing_type=sa.String(255), nullable=False)

    # Fails loudly if data room files exist; see the module docstring.
    op.alter_column('media', 'file_path', existing_type=sa.Text(), nullable=False)
    op.drop_index('ix_media_engagement_dd_folder', table_name='media')
    op.drop_index('uq_media_drive_file_id', table_name='media')
    for column in ('source', 'dd_sub_item_code', 'dd_category_code',
                   'drive_modified_time', 'drive_web_link', 'drive_file_id'):
        op.drop_column('media', column)

    op.drop_index('uq_engagement_drive_folder_sub_item', table_name='engagement_drive_folder')
    op.drop_index('uq_engagement_drive_folder_category', table_name='engagement_drive_folder')
    op.drop_index('uq_engagement_drive_folder_root', table_name='engagement_drive_folder')
    op.drop_index('ix_engagement_drive_folder_drive_id', table_name='engagement_drive_folder')
    op.drop_index('ix_engagement_drive_folder_engagement_id', table_name='engagement_drive_folder')
    op.drop_table('engagement_drive_folder')

    op.drop_index('uq_drive_integration_single_live', table_name='drive_integration')
    op.drop_table('drive_integration')
