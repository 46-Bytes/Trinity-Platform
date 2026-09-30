"""
The data room: files filed against DD sub-items, stored in Drive.

Trinity keeps no copy of the bytes. An upload is streamed straight into
Drive and the Media row that comes out of it is an index entry - file_path
is NULL, drive_file_id is the locator. A download is streamed back the same
way. That is the whole point of the feature: no server storage cost, and
Google's durability rather than ours.

Deliberately separate from FileService, which writes to local disk and is
still right for everything else in Trinity. Sharing it would have meant a
flag threaded through every call and a real risk of a data room file being
persisted by accident.

Two rules from the brief are enforced here rather than left to callers:

  - uploading a file to a DD item moves that item to In progress, unless it
    is already answered. An advisor still has to check it and mark it Yes;
  - a delete is a soft delete on both sides - trashed in Drive, deleted_at
    in Trinity - because buyer_access_log rows point at these documents and
    a hard delete would destroy the record of what a buyer was shown.
"""
import logging
from datetime import datetime
from typing import Any, BinaryIO, Dict, Iterator, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.media import Media
from app.models.sale_ready import EngagementDDItem, EngagementDocumentRegisterEntry
from app.models.user import User
from app.services import sale_ready_rules as rules
from app.services.drive_client import GOOGLE_NATIVE_PREFIX, DriveUnavailable
from app.services.drive_folder_service import (
    get_drive_client, get_drive_folder_service, require_expected_account,
)

logger = logging.getLogger(__name__)

SOURCE_TRINITY = "trinity"
SOURCE_DRIVE = "drive"

# Mirrors FileService, deliberately duplicated rather than imported: the data
# room's limits are a Sale Ready decision and should be changeable without
# touching what diagnostics and avatars accept.
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'rtf',
    'xls', 'xlsx', 'csv',
    'jpg', 'jpeg', 'png', 'gif', 'webp',
    'zip',
}

# DD statuses an upload may overwrite. A 'yes' or 'not_applicable' has been
# decided by an advisor and a file arriving does not undo that.
_PROMOTABLE = (None, rules.DD_STATUS_NO)


class DataRoomError(ValueError):
    """The request is valid but cannot be applied to this file or folder."""


class _LimitedStream:
    """
    A read-through wrapper that refuses to hand over more than `limit` bytes.

    The declared size is checked before anything is read, but it comes from
    UploadFile.size, which the multipart parser fills in and which is not part
    of any contract we control. If it were ever absent the limit would simply
    not apply and an unbounded file would stream into Drive. Counting as the
    bytes actually go past is the check that cannot be skipped.

    Raising mid-read aborts the request body before Google has a complete
    upload, so no partial file is left behind.
    """

    def __init__(self, stream: BinaryIO, limit: int, file_name: str):
        self._stream = stream
        self._limit = limit
        self._file_name = file_name
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self.bytes_read += len(chunk)
        if self.bytes_read > self._limit:
            raise DataRoomError(
                f"{self._file_name} is larger than the "
                f"{self._limit // (1024 * 1024)}MB limit."
            )
        return chunk

    def __getattr__(self, name):
        # seek, tell, close and anything else the upload machinery reaches for.
        return getattr(self._stream, name)


def _extension(file_name: str) -> str:
    return (file_name or "").rsplit(".", 1)[-1].lower() if "." in (file_name or "") else ""


def _parse_drive_time(value: Optional[str]) -> Optional[datetime]:
    """Drive's RFC 3339 timestamps, as naive UTC to match every other column."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


class DataRoomService:
    def __init__(self, db: Session):
        self.db = db
        self.folders = get_drive_folder_service(db)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def files_in_folder(self, engagement_id: UUID, category_code: str,
                        sub_item_code: str) -> List[Media]:
        return self.db.query(Media).filter(
            Media.engagement_id == engagement_id,
            Media.dd_category_code == category_code,
            Media.dd_sub_item_code == sub_item_code,
            Media.is_active == True,  # noqa: E712
            Media.deleted_at.is_(None),
        ).order_by(Media.created_at.asc()).all()

    def files_for_engagement(self, engagement_id: UUID) -> List[Media]:
        """Every live data room file, for the register and the folder counts."""
        return self.db.query(Media).filter(
            Media.engagement_id == engagement_id,
            Media.dd_sub_item_code.isnot(None),
            Media.is_active == True,  # noqa: E712
            Media.deleted_at.is_(None),
        ).order_by(Media.dd_category_code.asc(), Media.dd_sub_item_code.asc(),
                   Media.created_at.asc()).all()

    def get_file(self, engagement_id: UUID, media_id: UUID) -> Optional[Media]:
        return self.db.query(Media).filter(
            Media.id == media_id,
            Media.engagement_id == engagement_id,
            Media.dd_sub_item_code.isnot(None),
            Media.is_active == True,  # noqa: E712
            Media.deleted_at.is_(None),
        ).first()

    def download_stream(self, media: Media) -> Iterator[bytes]:
        """The file's bytes, straight from Drive. Never a link, never a local read."""
        if not media.drive_file_id:
            raise DriveUnavailable("This document is not stored in the data room.")
        return get_drive_client(self.db).download_stream(media.drive_file_id)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def validate(self, file_name: str, size: Optional[int]) -> None:
        ext = _extension(file_name)
        if ext not in ALLOWED_EXTENSIONS:
            raise DataRoomError(
                f"File type .{ext or '?'} is not allowed. Allowed types: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        if size is not None and size > MAX_FILE_SIZE:
            raise DataRoomError(
                f"{file_name} is larger than the {MAX_FILE_SIZE // (1024 * 1024)}MB limit."
            )

    def upload(self, engagement: Engagement, category_code: str, sub_item_code: str,
               stream: BinaryIO, file_name: str, content_type: Optional[str],
               user: User, size: Optional[int] = None) -> Media:
        """
        Put a file in a DD sub-item's folder.

        Drive is written first and the row committed after, so a crash between
        them leaves an orphan in Drive rather than a Media row pointing at
        nothing. The sync adopts orphans on its next pass, because an orphan
        is indistinguishable from a file someone dropped into Drive by hand.
        """
        self.validate(file_name, size)
        require_expected_account(self.db)
        self._require_dd_item(engagement.id, category_code, sub_item_code)

        # One client for the whole operation: ensure_sub_item may create three
        # folders, and each get_drive_client is a query, a decrypt and a build.
        client = get_drive_client(self.db)
        folder_id = self.folders.ensure_sub_item(
            engagement, category_code, sub_item_code, client=client,
        )
        guarded = _LimitedStream(stream, MAX_FILE_SIZE, file_name)
        uploaded = client.upload(guarded, file_name, content_type, folder_id)

        media = Media(
            user_id=user.id,
            engagement_id=engagement.id,
            file_name=uploaded.get("name") or file_name,
            file_path=None,  # the bytes live in Drive
            file_size=int(uploaded["size"]) if uploaded.get("size") else (size or guarded.bytes_read),
            file_type=uploaded.get("mimeType") or content_type,
            file_extension=_extension(file_name),
            drive_file_id=uploaded["id"],
            drive_web_link=uploaded.get("webViewLink"),
            drive_modified_time=_parse_drive_time(uploaded.get("modifiedTime")),
            dd_category_code=category_code,
            dd_sub_item_code=sub_item_code,
            source=SOURCE_TRINITY,
        )
        self.db.add(media)
        self.promote_dd_items(engagement.id, category_code, sub_item_code, user)
        self.db.commit()
        self.db.refresh(media)
        logger.info("Data room upload %s -> engagement %s %s/%s",
                    media.id, engagement.id, category_code, sub_item_code)
        return media

    def _require_dd_item(self, engagement_id: UUID, category_code: str, sub_item_code: str) -> None:
        exists = self.db.query(EngagementDDItem.id).filter(
            EngagementDDItem.engagement_id == engagement_id,
            EngagementDDItem.category_code == category_code,
            EngagementDDItem.sub_item_code == sub_item_code,
        ).first()
        if not exists:
            raise DataRoomError(
                f"{category_code}/{sub_item_code} is not a due diligence folder on this engagement."
            )

    # ------------------------------------------------------------------
    # DD status
    # ------------------------------------------------------------------
    def promote_dd_items(self, engagement_id: UUID, category_code: str, sub_item_code: str,
                         user: Optional[User]) -> int:
        """
        Move this folder's DD items to In progress, per the brief.

        Only from "no status" or "No". A Yes or Not applicable was decided by
        an advisor and a file arriving does not reopen it. Applies however the
        file arrived - uploaded here or dropped straight into Drive - because
        the brief describes the item, not the channel.
        """
        items = self.db.query(EngagementDDItem).filter(
            EngagementDDItem.engagement_id == engagement_id,
            EngagementDDItem.category_code == category_code,
            EngagementDDItem.sub_item_code == sub_item_code,
        ).all()
        changed = 0
        for item in items:
            if item.status in _PROMOTABLE:
                item.status = rules.DD_STATUS_IN_PROGRESS
                item.status_changed_at = datetime.utcnow()
                if user is not None:
                    item.status_changed_by_user_id = user.id
                changed += 1
        return changed

    # ------------------------------------------------------------------
    # Rename and delete
    # ------------------------------------------------------------------
    def rename(self, media: Media, new_name: str) -> Media:
        name = (new_name or "").strip()
        if not name:
            raise DataRoomError("A file name is required.")
        self.validate(name, None)
        require_expected_account(self.db)
        updated = get_drive_client(self.db).rename(media.drive_file_id, name)
        media.file_name = updated.get("name") or name
        media.file_extension = _extension(media.file_name)
        media.drive_modified_time = _parse_drive_time(updated.get("modifiedTime"))
        self.db.commit()
        self.db.refresh(media)
        return media

    def delete(self, media: Media) -> None:
        """Trash in Drive, soft delete here. The access log keeps its subject."""
        require_expected_account(self.db)
        if media.drive_file_id:
            get_drive_client(self.db).trash(media.drive_file_id)
        media.deleted_at = datetime.utcnow()
        media.is_active = False
        self.db.commit()
        logger.info("Data room file %s trashed", media.id)


    # ------------------------------------------------------------------
    # Document register
    # ------------------------------------------------------------------
    def register_for_stage(self, engagement_id: UUID, stage_code: str) -> List[Dict[str, Any]]:
        """
        A stage's register: every file in that stage's DD folders, with the
        advisor's notes attached where there are any.

        Generated, not stored - the brief is explicit that the register is a
        view of the files. A file with no notes still appears, with the typed
        fields empty; the row in engagement_document_register_entry is
        created only when something is typed.
        """
        sub_items = self.db.query(
            EngagementDDItem.category_code, EngagementDDItem.sub_item_code, EngagementDDItem.sub_item,
        ).filter(
            EngagementDDItem.engagement_id == engagement_id,
            EngagementDDItem.stage_code == stage_code,
        ).distinct().all()
        if not sub_items:
            return []
        labels = {(r.category_code, r.sub_item_code): r.sub_item for r in sub_items}

        files = [
            f for f in self.files_for_engagement(engagement_id)
            if (f.dd_category_code, f.dd_sub_item_code) in labels
        ]
        if not files:
            return []

        notes = {
            row.media_id: row
            for row in self.db.query(EngagementDocumentRegisterEntry).filter(
                EngagementDocumentRegisterEntry.engagement_id == engagement_id,
                EngagementDocumentRegisterEntry.media_id.in_([f.id for f in files]),
            ).all()
        }
        return [
            {
                "media_id": f.id,
                "file_name": f.file_name,
                "sub_item_code": f.dd_sub_item_code,
                "sub_item": labels.get((f.dd_category_code, f.dd_sub_item_code)),
                "added_at": f.created_at,
                "document_id": getattr(notes.get(f.id), "document_id", None),
                "renewal_date": getattr(notes.get(f.id), "renewal_date", None),
                "renewal_cost": (
                    float(notes[f.id].renewal_cost)
                    if f.id in notes and notes[f.id].renewal_cost is not None else None
                ),
                "notes": getattr(notes.get(f.id), "notes", None),
                # Advisor convenience, on an advisor-only endpoint. The buyer
                # document schema carries no link and this never reaches it.
                "drive_web_link": f.drive_web_link,
            }
            for f in files
        ]

    def update_register_entry(self, engagement: Engagement, stage_code: str, media_id: UUID,
                              fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save what the advisor typed against one file.

        The row is created on first use, so an untouched register writes
        nothing. document_name, creation_date and file_link are deliberately
        left NULL: the brief takes all three from the file.
        """
        media = self.get_file(engagement.id, media_id)
        if media is None:
            raise DataRoomError("That document is not in this engagement's data room.")

        row = self.db.query(EngagementDocumentRegisterEntry).filter(
            EngagementDocumentRegisterEntry.media_id == media_id,
        ).first()
        if row is None:
            row = EngagementDocumentRegisterEntry(
                engagement_id=engagement.id, stage_code=stage_code, media_id=media_id,
            )
            self.db.add(row)
        else:
            row.stage_code = stage_code

        for key in ("document_id", "renewal_date", "renewal_cost", "notes"):
            if key in fields:
                setattr(row, key, fields[key])
        self.db.commit()
        self.db.refresh(row)

        return {
            "media_id": media.id,
            "file_name": media.file_name,
            "sub_item_code": media.dd_sub_item_code,
            "sub_item": None,
            "added_at": media.created_at,
            "document_id": row.document_id,
            "renewal_date": row.renewal_date,
            "renewal_cost": float(row.renewal_cost) if row.renewal_cost is not None else None,
            "notes": row.notes,
            "drive_web_link": media.drive_web_link,
        }


def get_data_room_service(db: Session) -> DataRoomService:
    return DataRoomService(db)
