"""
Google Drive integration: the connection itself, and the folder map.

Drive is the data room's store - Trinity keeps no copy of the bytes. Two
tables carry that:

- drive_integration: one row, the connection to Benchmark's central Google
  account. OAuth rather than a service account, so a refresh token has to be
  kept; it is the only secret in the database and is never logged or returned
  by any endpoint. The Drive changes page token lives here too, because it is
  meaningless without the connection that issued it.
- engagement_drive_folder: which Drive folder is which. Keyed on engagement_id
  and the DD codes, so a folder is always resolved by stored id and never by
  searching Drive for a name - names change, and a name search is ambiguous.

Nothing here is per-user. Advisors, clients and buyers never touch Drive; the
account is system-use only and every file reaches a person through Trinity.
"""
import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DriveIntegration(Base):
    """
    The single connection to the central Google account.

    One row, enforced by the partial unique index: a second connection would
    mean two accounts owning one data room. Disconnecting sets status rather
    than deleting, so the audit of who connected what survives.
    """
    __tablename__ = "drive_integration"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    account_email = Column(String(255), nullable=True, comment="The Google account that authorised Trinity")
    # Encrypted at rest by DriveCredentialStore. Never logged, never serialised.
    refresh_token = Column(Text, nullable=True, comment="Encrypted OAuth refresh token")
    root_folder_id = Column(String(255), nullable=True,
                            comment="Drive id of Trinity/Clients; everything is created beneath it")

    changes_page_token = Column(String(255), nullable=True,
                                comment="Drive changes cursor; NULL means the next sync starts fresh")

    status = Column(String(20), nullable=False, server_default='disconnected',
                    comment="'connected' or 'disconnected'")
    last_error = Column(Text, nullable=True, comment="Why the last call failed, for the admin screen")
    last_synced_at = Column(DateTime, nullable=True)

    connected_at = Column(DateTime, nullable=True)
    connected_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True,
    )

    is_deleted = Column(Boolean, nullable=False, server_default='false')
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        # Created by add_drive_data_room and declared here so autogenerate does
        # not propose dropping it. Indexing the constant true with a partial
        # predicate is what limits the table to one live row: a second
        # connection would mean two Google accounts owning one data room.
        Index('uq_drive_integration_single_live', text('(true)'), unique=True,
              postgresql_where=text('is_deleted = false')),
    )

    def __repr__(self):
        return f"<DriveIntegration {self.status} account={self.account_email}>"


class EngagementDriveFolder(Base):
    """
    One Drive folder, mapped to what it holds.

    The three-level shape is carried by which columns are set:

        category_code NULL, sub_item_code NULL -> the engagement's Data room
        category_code set,  sub_item_code NULL -> a DD category folder
        both set                               -> a DD sub-item folder

    Keyed on engagement_id, so two engagements never share a row even when
    their business names match. The folder path repeats the business name
    rather than the engagement, by decision: Trinity/Clients/{business_name}/
    Data room.
    """
    __tablename__ = "engagement_drive_folder"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    engagement_id = Column(
        UUID(as_uuid=True), ForeignKey('engagements.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    category_code = Column(String(10), nullable=True, comment="NULL for the data room root")
    sub_item_code = Column(String(10), nullable=True, comment="NULL for a category folder")

    drive_folder_id = Column(String(255), nullable=False, comment="The folder's Drive id; the only identity used")
    drive_web_link = Column(
        Text, nullable=True,
        comment="Drive UI link. Returned to advisors and owners; never to a buyer.",
    )

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        # One folder per level, declared exactly as add_drive_data_room creates
        # them. Three partial indexes rather than one UNIQUE over the three
        # columns: the level lives in a NULL, and Postgres treats NULLs as
        # distinct, so a single UNIQUE would hold only the sub-item case and
        # let an engagement acquire two roots.
        Index('uq_engagement_drive_folder_root', 'engagement_id', unique=True,
              postgresql_where=text('category_code IS NULL AND sub_item_code IS NULL')),
        Index('uq_engagement_drive_folder_category', 'engagement_id', 'category_code',
              unique=True,
              postgresql_where=text('category_code IS NOT NULL AND sub_item_code IS NULL')),
        Index('uq_engagement_drive_folder_sub_item',
              'engagement_id', 'category_code', 'sub_item_code', unique=True,
              postgresql_where=text('category_code IS NOT NULL AND sub_item_code IS NOT NULL')),
        # A sub-item cannot belong to no category. The one CheckConstraint in
        # app/models: this is table shape, not field validation, and no schema
        # can express it.
        CheckConstraint('category_code IS NOT NULL OR sub_item_code IS NULL',
                        name='ck_engagement_drive_folder_shape'),
        Index('ix_engagement_drive_folder_drive_id', 'drive_folder_id'),
    )

    def __repr__(self):
        return (f"<EngagementDriveFolder {self.engagement_id} "
                f"{self.category_code or '-'}/{self.sub_item_code or '-'}>")
