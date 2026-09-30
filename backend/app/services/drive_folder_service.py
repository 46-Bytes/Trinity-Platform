"""
The data room's folder map.

One decision shapes this file: a folder is always resolved by its stored
Drive id, never by asking Drive for a name. Names change - a client renames
their business, someone tidies a folder - and a name search is both slow and
ambiguous. The id is the identity.

The structure is fixed by the client:

    Trinity / Clients / {business_name} / Data room / {category} / {sub-item}

The {business_name} folder is created for each engagement and never adopted by
name, so two engagements with the same business name get two separate folders
(Drive allows the same name twice; the stored id tells them apart). Below it,
category and sub-item folders are looked up by name only inside that
engagement's own data room, and a Drive id is never mapped to two engagements.

Folders below the data room are created lazily. An engagement has 16 DD
categories and around 130 sub-items; creating all of them up front would be
~146 Drive calls before a single file exists, most of them for folders that
will stay empty.
"""
import logging
import re
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.drive import DriveIntegration, EngagementDriveFolder
from app.models.engagement import Engagement
from app.models.sale_ready import EngagementDDItem
from app.services.drive_client import DriveClient, DriveUnavailable, decrypt_token, drive_enabled

logger = logging.getLogger(__name__)

DATA_ROOM_FOLDER = "Data room"

# Drive tolerates most characters, but a path separator or a control
# character in a folder name is asking for trouble in every tool that later
# reads it. Collapse them rather than rejecting the engagement.
_UNSAFE = re.compile(r"[\\/\x00-\x1f]+")


class SharedDriveFolder(ValueError):
    """A Drive folder is, or would become, mapped to more than one engagement."""


def safe_folder_name(raw: Optional[str], fallback: str) -> str:
    """A folder name that will not surprise anyone, or a fallback if empty."""
    cleaned = _UNSAFE.sub(" ", (raw or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or fallback


def get_integration(db: Session) -> Optional[DriveIntegration]:
    """The single live connection row, or None when Drive was never connected."""
    return db.query(DriveIntegration).filter(
        DriveIntegration.is_deleted == False,  # noqa: E712
    ).first()


def get_drive_client(db: Session) -> DriveClient:
    """
    A client authenticated as the central account.

    Raises rather than returning None so no caller can accidentally treat a
    missing connection as an empty data room.
    """
    if not drive_enabled():
        raise DriveUnavailable(
            "The Google Drive data room is switched off (GOOGLE_DRIVE_ENABLED is false)."
        )
    integration = get_integration(db)
    if not integration or integration.status != "connected" or not integration.refresh_token:
        raise DriveUnavailable(
            "Trinity is not connected to Google Drive. Connect the Benchmark "
            "account in Sale Ready Admin."
        )
    return DriveClient(decrypt_token(integration.refresh_token))


class DriveFolderService:
    """Maps an engagement and its DD codes onto Drive folder ids."""

    def __init__(self, db: Session):
        self.db = db

    # -- lookups --------------------------------------------------------
    def _row(self, engagement_id: UUID, category_code: Optional[str],
             sub_item_code: Optional[str]) -> Optional[EngagementDriveFolder]:
        return self.db.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement_id,
            EngagementDriveFolder.category_code.is_(None) if category_code is None
            else EngagementDriveFolder.category_code == category_code,
            EngagementDriveFolder.sub_item_code.is_(None) if sub_item_code is None
            else EngagementDriveFolder.sub_item_code == sub_item_code,
        ).first()

    def folder_id_for(self, engagement_id: UUID, category_code: Optional[str] = None,
                      sub_item_code: Optional[str] = None) -> Optional[str]:
        """The stored Drive id, without calling Drive."""
        row = self._row(engagement_id, category_code, sub_item_code)
        return row.drive_folder_id if row else None

    def folder_by_drive_id(self, drive_folder_id: str) -> Optional[EngagementDriveFolder]:
        """
        Which engagement and DD codes a Drive folder belongs to. Used by the sync.

        Raises if two engagements map the same folder, rather than picking one
        and filing a document against the wrong engagement.
        """
        rows = self.db.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.drive_folder_id == drive_folder_id,
        ).all()
        if len({r.engagement_id for r in rows}) > 1:
            raise SharedDriveFolder(
                f"Drive folder {drive_folder_id} is mapped to more than one engagement"
            )
        return rows[0] if rows else None

    def mapped_folders(self, engagement_id: UUID) -> Dict[Tuple[Optional[str], Optional[str]], str]:
        rows = self.db.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement_id,
        ).all()
        return {(r.category_code, r.sub_item_code): r.drive_folder_id for r in rows}

    def mapped_web_links(
        self, engagement_id: UUID,
    ) -> Dict[Tuple[Optional[str], Optional[str]], Optional[str]]:
        """
        Drive links for the folders that exist, keyed the same way.

        For the advisor and the owner, who may open a folder in Drive when it
        suits them. Never handed to a buyer: their folder schema has no field
        for it, and their router cannot reach the endpoint that returns this.
        Folders not yet created in Drive are simply absent.
        """
        rows = self.db.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.engagement_id == engagement_id,
        ).all()
        return {(r.category_code, r.sub_item_code): r.drive_web_link for r in rows}

    # -- creation -------------------------------------------------------
    def _record(self, engagement_id: UUID, category_code: Optional[str],
                sub_item_code: Optional[str], folder: Dict) -> EngagementDriveFolder:
        # A folder belongs to one engagement. Never map another engagement's folder.
        owner = self.db.query(EngagementDriveFolder.engagement_id).filter(
            EngagementDriveFolder.drive_folder_id == folder["id"],
            EngagementDriveFolder.engagement_id != engagement_id,
        ).first()
        if owner:
            raise SharedDriveFolder(
                f"Drive folder {folder['id']} already belongs to engagement {owner[0]}"
            )
        row = self._row(engagement_id, category_code, sub_item_code)
        if row:
            row.drive_folder_id = folder["id"]
            row.drive_web_link = folder.get("webViewLink")
            return row
        row = EngagementDriveFolder(
            engagement_id=engagement_id,
            category_code=category_code,
            sub_item_code=sub_item_code,
            drive_folder_id=folder["id"],
            drive_web_link=folder.get("webViewLink"),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _client(self, client=None) -> DriveClient:
        """
        The caller's client, or a fresh one.

        Threaded through ensure_* because a first upload walks three levels,
        and each get_drive_client is a query, a token decrypt and a service
        build for no gain. Behaviour is identical either way.
        """
        return client if client is not None else get_drive_client(self.db)

    def ensure_data_room(self, engagement: Engagement, client=None) -> str:
        """
        The engagement's Data room folder id, creating the path if needed.

        Trinity/Clients is configuration - Trinity does not create it. The two
        levels below it are ours: {business_name} and Data room. Both are always
        created, never found by name: another engagement may have a folder with
        the same business name, and adopting it would share its data room.
        """
        existing = self.folder_id_for(engagement.id)
        if existing:
            return existing

        integration = get_integration(self.db)
        root = (integration.root_folder_id if integration else None)
        if not root:
            raise DriveUnavailable(
                "The Drive root folder is not configured. Set the id of "
                "Trinity/Clients on the Drive connection before uploading."
            )

        client = self._client(client)
        business = safe_folder_name(
            engagement.business_name or engagement.engagement_name, str(engagement.id),
        )
        client_folder = client.create_folder(business, root)
        data_room = client.create_folder(DATA_ROOM_FOLDER, client_folder["id"])
        row = self._record(engagement.id, None, None, data_room)
        logger.info("Data room ready for engagement %s at %s", engagement.id, data_room["id"])
        return row.drive_folder_id

    def ensure_category(self, engagement: Engagement, category_code: str, client=None) -> str:
        existing = self.folder_id_for(engagement.id, category_code, None)
        if existing:
            return existing
        client = self._client(client)
        parent = self.ensure_data_room(engagement, client=client)
        name = safe_folder_name(
            self._category_label(engagement.id, category_code), f"Category {category_code}",
        )
        folder = client.ensure_folder(name, parent)
        return self._record(engagement.id, category_code, None, folder).drive_folder_id

    def ensure_sub_item(self, engagement: Engagement, category_code: str,
                        sub_item_code: str, client=None) -> str:
        """
        The folder one DD sub-item's documents live in. The release boundary.

        A folder mapped for the first time is indexed immediately. ensure_folder
        adopts a folder of the same name if one is already in Drive, and that
        folder may well have documents in it - put there by an advisor working
        in Drive, or left behind by an upload that reached Drive but whose row
        never committed. The change feed only reports what happens after the
        cursor is taken, so without this pass those files would stay invisible.
        """
        existing = self.folder_id_for(engagement.id, category_code, sub_item_code)
        if existing:
            return existing
        client = self._client(client)
        parent = self.ensure_category(engagement, category_code, client=client)
        name = safe_folder_name(
            self._sub_item_label(engagement.id, category_code, sub_item_code), sub_item_code,
        )
        folder = client.ensure_folder(name, parent)
        row = self._record(engagement.id, category_code, sub_item_code, folder)
        self._index_existing(row)
        return row.drive_folder_id

    def _index_existing(self, row: EngagementDriveFolder) -> None:
        """
        Import whatever is already in a newly mapped folder.

        Imported late to avoid a circular import: the sync service reaches
        back into this one to resolve which folder a file belongs to. Failure
        is logged, never raised - an upload must not fail because a file that
        was already there could not be indexed.
        """
        from app.services.drive_sync_service import get_drive_sync_service

        try:
            found = get_drive_sync_service(self.db).backfill_folder(row)
            if found:
                logger.info("Indexed %d existing file(s) in newly mapped folder %s",
                            found, row.drive_folder_id)
        except Exception:
            logger.exception("Could not index existing files in folder %s", row.drive_folder_id)

    # -- naming ---------------------------------------------------------
    def _category_label(self, engagement_id: UUID, category_code: str) -> str:
        row = self.db.query(EngagementDDItem.category).filter(
            EngagementDDItem.engagement_id == engagement_id,
            EngagementDDItem.category_code == category_code,
        ).first()
        return f"{category_code}. {row[0]}" if row and row[0] else f"Category {category_code}"

    def _sub_item_label(self, engagement_id: UUID, category_code: str, sub_item_code: str) -> str:
        row = self.db.query(EngagementDDItem.sub_item).filter(
            EngagementDDItem.engagement_id == engagement_id,
            EngagementDDItem.category_code == category_code,
            EngagementDDItem.sub_item_code == sub_item_code,
        ).first()
        return f"{sub_item_code} {row[0]}".strip() if row and row[0] else sub_item_code

    # -- maintenance ----------------------------------------------------
    def rename_client_folder(self, engagement: Engagement) -> None:
        """
        Follow a business-name change in Drive.

        Renames the {business_name} folder, which is the data room's parent.
        Ids are unaffected, so nothing else in the map has to move.
        """
        data_room_id = self.folder_id_for(engagement.id)
        if not data_room_id:
            return
        client = get_drive_client(self.db)
        metadata = client.get_metadata(data_room_id)
        parents = metadata.get("parents") or []
        if not parents:
            return
        client.rename(
            parents[0],
            safe_folder_name(engagement.business_name or engagement.engagement_name, str(engagement.id)),
        )


def get_drive_folder_service(db: Session) -> DriveFolderService:
    return DriveFolderService(db)
