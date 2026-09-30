"""
Drive -> Trinity sync.

The brief asks Trinity to "pick up files added directly in Drive". An advisor
who drops a lease into the 9.1 folder from their laptop should see it in
Trinity, and a buyer released on that folder should be able to open it.

Polling, not webhooks. Drive's push notifications need a publicly reachable
HTTPS endpoint and a channel renewed every seven days, for latency nobody
needs in a data room. `changes.list` with a stored cursor works the same in
production, staging and on a developer's machine.

Four events are handled, which is what two-way sync means here:

  added    a file appears in a mapped folder      -> index it, promote its DD items
  renamed  file.name differs                      -> follow it
  moved    file.parents differs                   -> refile, or drop out of the room
  deleted  removed or trashed                     -> soft delete, never hard

Identity is drive_file_id, never the name. That is what makes a move an
update rather than a duplicate, and it is the single most important thing in
this file.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models.drive import EngagementDriveFolder
from app.models.media import Media
from app.services.data_room_service import SOURCE_DRIVE, _parse_drive_time
from app.services.drive_client import GOOGLE_NATIVE_PREFIX, DriveUnavailable
from app.services.drive_folder_service import (
    SharedDriveFolder,
    get_drive_client,
    get_drive_folder_service,
    get_integration,
)

logger = logging.getLogger(__name__)

# How many times one change is retried within a pass before the sync gives
# up on it and holds the cursor.
CHANGE_ATTEMPTS = 2

# media column limits: file_name String(255), file_extension String(20), file_size Integer.
_NAME_MAX, _EXT_MAX, _SIZE_MAX = 255, 20, 2**31 - 1


class UnindexableChange(ValueError):
    """A change that fails the same way on every attempt, so it is recorded and skipped."""


# Failures a retry cannot fix. Anything else (a lock, Drive unreachable) holds the cursor.
_DETERMINISTIC = (UnindexableChange, SharedDriveFolder, DataError, IntegrityError)
_APPLIED, _UNINDEXABLE, _FAILED = "applied", "unindexable", "failed"


def _stored_extension(name: str) -> Optional[str]:
    """The text after the last dot, only if it looks like an extension."""
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    return ext if ext and len(ext) <= _EXT_MAX and " " not in ext else None


def _stored_name(name: str) -> str:
    """Drive allows longer names than media.file_name; shorten, keeping the extension."""
    if len(name) <= _NAME_MAX:
        return name
    ext = _stored_extension(name)
    suffix = f".{ext}" if ext else ""
    return name[:_NAME_MAX - len(suffix)] + suffix


def _stored_size(size: Optional[str]) -> Optional[int]:
    """Size in bytes, or None when it does not fit media.file_size (files over 2 GB)."""
    if not size:
        return None
    value = int(size)
    return value if value <= _SIZE_MAX else None


class SyncResult:
    """What one pass did. Returned for the log line and the admin screen."""

    def __init__(self):
        self.added = 0
        self.renamed = 0
        self.moved = 0
        self.deleted = 0
        self.skipped = 0
        # True when the cursor was deliberately not advanced, because a change
        # failed and skipping it would lose it for good.
        self.held = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "added": self.added, "renamed": self.renamed, "moved": self.moved,
            "deleted": self.deleted, "skipped": self.skipped, "held": self.held,
        }

    def __repr__(self):
        return f"<SyncResult {self.as_dict()}>"


class DriveSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.folders = get_drive_folder_service(db)

    # ------------------------------------------------------------------
    def sync(self) -> SyncResult:
        """
        One pass over everything that changed since the last cursor.

        A first run has no cursor. Before taking one it walks every mapped
        folder, because the change feed only reports what happens afterwards
        and anything already filed would otherwise never be seen.

        A change that fails for a reason a retry might fix holds the cursor
        rather than being skipped: see the comment where that decision is made.
        One that fails the same way every time is skipped and named in last_error.
        """
        integration = get_integration(self.db)
        if integration is None:
            raise DriveUnavailable("Trinity is not connected to Google Drive.")

        client = get_drive_client(self.db)
        result = SyncResult()

        if not integration.changes_page_token:
            # First run, or the first after reconnecting. The change feed only
            # reports what happens from here on, so anything already sitting in
            # a mapped folder would never be seen. Walk them once before
            # taking the cursor - without this, pointing Trinity at a folder
            # that already has documents leaves them invisible forever.
            for folder in self._mapped_sub_item_folders():
                try:
                    result.added += self.backfill_folder(folder)
                except Exception:
                    result.skipped += 1
                    logger.exception("Could not backfill Drive folder %s", folder.drive_folder_id)
            integration.changes_page_token = client.start_page_token()
            integration.last_synced_at = datetime.utcnow()
            self.db.commit()
            logger.info("Drive sync initialised at cursor %s after backfilling %d file(s)",
                        integration.changes_page_token, result.added)
            return result

        changes, _, new_token = client.list_changes(integration.changes_page_token)
        failed: List[str] = []
        unindexable: List[str] = []
        for change in changes:
            outcome = self._apply_with_retries(change, result)
            if outcome == _FAILED:
                failed.append(str(change.get("fileId")))
            elif outcome == _UNINDEXABLE:
                unindexable.append(str(change.get("fileId")))

        integration.last_synced_at = datetime.utcnow()
        if failed:
            # The cursor stays where it is. Advancing past a change that was
            # never applied loses it permanently: the feed only reports a
            # change once, so nothing would ever mention that file again and
            # Trinity's index would silently disagree with Drive.
            #
            # Only failures a later pass might fix get here (a lock, Drive
            # unreachable). Ones that fail identically every time are skipped
            # and named instead, so a single bad file cannot stall the feed.
            result.held = True
            integration.last_error = (
                f"{len(failed)} Drive change(s) could not be applied, so the sync is "
                f"paused rather than skipping them: {', '.join(failed[:5])}"
                f"{'...' if len(failed) > 5 else ''}"
            )
            self.db.commit()
            logger.error("Drive sync holding its cursor after %d failed change(s): %s",
                         len(failed), failed[:5])
            return result

        integration.changes_page_token = new_token
        # A change that fails identically every time cannot block the rest.
        # It is named here and in the log; the cursor moves on.
        integration.last_error = (
            f"{len(unindexable)} Drive file(s) could not be indexed and were skipped: "
            f"{', '.join(unindexable[:5])}{'...' if len(unindexable) > 5 else ''}"
        ) if unindexable else None
        self.db.commit()
        logger.info("Drive sync %s", result.as_dict())
        return result

    def _apply_with_retries(self, change: Dict[str, Any], result: SyncResult) -> str:
        """
        Apply one change, retrying a couple of times before giving up on it.

        Each change is committed on its own. That keeps a rollback from
        discarding the changes already applied earlier in the same pass, and
        it is safe to replay: _apply matches on drive_file_id, so re-running
        an add becomes an update and re-running a delete is a no-op.

        Most failures here are transient - a lock, a blip reaching Drive for
        metadata - and clear on the next attempt. The session is rolled back
        between tries because a failed statement poisons it, and a later
        change in the same pass would then fail for the wrong reason.

        Returns _APPLIED, _UNINDEXABLE (fails the same way every time: skip and
        record) or _FAILED (probably transient: hold the cursor).
        """
        for attempt in range(1, CHANGE_ATTEMPTS + 1):
            try:
                self._apply(change, result)
                self.db.commit()
                return _APPLIED
            except Exception as e:
                self.db.rollback()
                if attempt == CHANGE_ATTEMPTS:
                    result.skipped += 1
                    logger.exception("Drive change could not be applied after %d attempts: %s",
                                     CHANGE_ATTEMPTS, change.get("fileId"))
                    return _UNINDEXABLE if isinstance(e, _DETERMINISTIC) else _FAILED
                logger.warning("Drive change %s failed (attempt %d/%d), retrying",
                               change.get("fileId"), attempt, CHANGE_ATTEMPTS)
        return _FAILED

    # ------------------------------------------------------------------
    def _apply(self, change: Dict[str, Any], result: SyncResult) -> None:
        file_id = change.get("fileId")
        if not file_id:
            return
        existing = self.db.query(Media).filter(Media.drive_file_id == file_id).first()
        payload = change.get("file") or {}

        # Gone, or in the bin.
        if change.get("removed") or payload.get("trashed"):
            if existing and existing.deleted_at is None:
                self._soft_delete(existing)
                result.deleted += 1
            return

        # Folders are structure, not documents.
        if payload.get("mimeType") == "application/vnd.google-apps.folder":
            return
        # Google Docs/Sheets have no bytes to serve; a data room holds files.
        if (payload.get("mimeType") or "").startswith(GOOGLE_NATIVE_PREFIX):
            result.skipped += 1
            return

        folder = self._owning_folder(payload.get("parents") or [])

        if existing is None:
            if folder is not None:
                self._create(payload, folder)
                result.added += 1
            return

        if folder is None:
            # Moved out of the data room entirely. It is no longer a document
            # anyone was released, so it stops being visible.
            if existing.deleted_at is None:
                self._soft_delete(existing)
                result.moved += 1
            return

        self._update(existing, payload, folder, result)

    # ------------------------------------------------------------------
    def _mapped_sub_item_folders(self) -> List[EngagementDriveFolder]:
        """Every folder that can hold documents. Category and root folders cannot."""
        return self.db.query(EngagementDriveFolder).filter(
            EngagementDriveFolder.sub_item_code.isnot(None),
        ).all()

    def _owning_folder(self, parents: List[str]) -> Optional[EngagementDriveFolder]:
        """The mapped sub-item folder this file sits in, if any."""
        for parent in parents:
            row = self.folders.folder_by_drive_id(parent)
            if row is not None and row.sub_item_code:
                return row
        return None

    def _create(self, payload: Dict[str, Any], folder: EngagementDriveFolder) -> None:
        name = payload.get("name") or "Untitled"
        user_id = self._attribution_user_id(folder)
        if user_id is None:
            raise UnindexableChange(
                f"Engagement {folder.engagement_id} has no primary advisor to attribute the file to"
            )
        media = Media(
            # A file dropped straight into Drive has no Trinity user. It is
            # attributed to the engagement's advisor, with source='drive'
            # recording that nobody here uploaded it.
            user_id=user_id,
            engagement_id=folder.engagement_id,
            file_name=_stored_name(name),
            file_path=None,
            file_size=_stored_size(payload.get("size")),
            file_type=(payload.get("mimeType") or "")[:100] or None,
            file_extension=_stored_extension(name),
            drive_file_id=payload["id"],
            drive_web_link=payload.get("webViewLink"),
            drive_modified_time=_parse_drive_time(payload.get("modifiedTime")),
            dd_category_code=folder.category_code,
            dd_sub_item_code=folder.sub_item_code,
            source=SOURCE_DRIVE,
        )
        self.db.add(media)
        self._promote(folder)

    def _update(self, media: Media, payload: Dict[str, Any],
                folder: EngagementDriveFolder, result: SyncResult) -> None:
        drive_time = _parse_drive_time(payload.get("modifiedTime"))
        # Trinity wrote to Drive and then updated the row, so its own change
        # comes back as an echo. Ignoring anything not newer than what we
        # already recorded makes that echo a no-op instead of a rewrite.
        if drive_time and media.drive_modified_time and drive_time <= media.drive_modified_time:
            return

        name = payload.get("name")
        if name and _stored_name(name) != media.file_name:
            media.file_name = _stored_name(name)
            media.file_extension = _stored_extension(name)
            result.renamed += 1

        moved_engagement = folder.engagement_id != media.engagement_id
        if moved_engagement:
            # Moved into another engagement's folder: the file now belongs to that engagement.
            media.engagement_id = folder.engagement_id
        if moved_engagement or (folder.category_code, folder.sub_item_code) != (
            media.dd_category_code, media.dd_sub_item_code
        ):
            media.dd_category_code = folder.category_code
            media.dd_sub_item_code = folder.sub_item_code
            self._promote(folder)
            result.moved += 1

        # Undeleted in Drive: restore rather than leave a ghost.
        if media.deleted_at is not None:
            media.deleted_at = None
            media.is_active = True

        media.drive_modified_time = drive_time
        media.file_size = _stored_size(payload.get("size")) if payload.get("size") else media.file_size
        media.drive_web_link = payload.get("webViewLink") or media.drive_web_link

    def _soft_delete(self, media: Media) -> None:
        media.deleted_at = datetime.utcnow()
        media.is_active = False

    def _promote(self, folder: EngagementDriveFolder) -> None:
        """A file arriving moves its DD items on, whichever side put it there."""
        from app.services.data_room_service import get_data_room_service

        get_data_room_service(self.db).promote_dd_items(
            folder.engagement_id, folder.category_code, folder.sub_item_code, None,
        )

    def _attribution_user_id(self, folder: EngagementDriveFolder):
        from app.models.engagement import Engagement

        engagement = self.db.query(Engagement).filter(
            Engagement.id == folder.engagement_id,
        ).first()
        return engagement.primary_advisor_id if engagement else None

    # ------------------------------------------------------------------
    def backfill_folder(self, folder: EngagementDriveFolder) -> int:
        """
        Index whatever is already in one folder.

        Used when a folder is first mapped, and as the recovery path for an
        upload that reached Drive but whose row was never committed: such a
        file is indistinguishable from one added by hand, and is adopted the
        same way.
        """
        client = get_drive_client(self.db)
        found = 0
        for payload in client.list_children(folder.drive_folder_id):
            if (payload.get("mimeType") or "").startswith(GOOGLE_NATIVE_PREFIX):
                continue
            exists = self.db.query(Media.id).filter(Media.drive_file_id == payload["id"]).first()
            if exists:
                continue
            try:
                self._create(payload, folder)
            except UnindexableChange:
                # Raised before anything is added, so the rest of the folder still indexes.
                logger.exception("Skipped Drive file %s while backfilling", payload.get("id"))
                continue
            found += 1
        # Deliberately no commit: this runs inside an upload's transaction as
        # well as the sync's, and committing here would split the upload in
        # two. The caller owns the transaction.
        self.db.flush()
        return found


def get_drive_sync_service(db: Session) -> DriveSyncService:
    return DriveSyncService(db)
