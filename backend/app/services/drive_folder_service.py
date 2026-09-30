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

The whole tree - 16 DD categories and 73 sub-items - is created up front by
provision_tree, which the Drive scheduler runs a few engagements at a time.
A folder has to be mapped before the sync can see a file dropped into it,
so creating folders only on first upload left Drive-side drops invisible.
The ensure_* helpers still create anything missing on demand.
"""
import logging
import re
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.drive import DriveIntegration, EngagementDriveFolder
from app.models.engagement import Engagement
from app.models.sale_ready import EngagementDDItem
from app.services.drive_client import (
    DriveClient, DriveNotFound, DriveUnavailable, decrypt_token, drive_enabled,
)
from app.services.engagement_status import STATUS_ARCHIVED, STATUS_COMPLETED, STATUS_ENDED
from app.services.program_registry import PROGRAM_SALE_READY

# Engagements that are over get no new folders. Reopening sets them active again,
# which puts them back in the queue. Paused engagements are still provisioned.
_NOT_PROVISIONED_STATUSES = (STATUS_ENDED, STATUS_COMPLETED, STATUS_ARCHIVED)

logger = logging.getLogger(__name__)

DATA_ROOM_FOLDER = "Data room"

# Engagements provisioned per scheduler pass. Each costs ~90 Drive calls, so
# a backlog is worked through over several passes rather than in one burst.
PROVISION_BATCH = 5

# An engagement whose provisioning fails waits before it is tried again, so it
# never holds a slot in the batch. The wait doubles per failure, up to the cap.
PROVISION_BACKOFF_MAX_SECONDS = 6 * 3600

# Drive tolerates most characters, but a path separator or a control
# character in a folder name is asking for trouble in every tool that later
# reads it. Collapse them rather than rejecting the engagement.
_UNSAFE = re.compile(r"[\\/\x00-\x1f]+")


class SharedDriveFolder(ValueError):
    """A Drive folder is, or would become, mapped to more than one engagement."""


class EngagementBusy(Exception):
    """Another request is creating this engagement's folders; try again next pass."""


# Class id for the per-engagement folder lock. Two-part advisory keys never collide
# with the scheduler's single-number key, so the global pass lock is unaffected.
ENGAGEMENT_FOLDER_LOCK_CLASS = 918_273_646


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


class DriveAccountMismatch(DriveUnavailable):
    """The connected Google account is not the one the data room must live in."""


def account_matches(account_email: Optional[str]) -> bool:
    """Whether an account may hold the data room. True when no account is pinned."""
    expected = (settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT or "").strip().lower()
    return not expected or (account_email or "").strip().lower() == expected


def require_expected_account(db: Session) -> None:
    """
    Refuse writes and syncing while Drive is connected as the wrong account.

    Reads still work, so documents already indexed stay downloadable; nothing
    new is written to, or pulled from, an account that is not the data room's.
    """
    integration = get_integration(db)
    if integration is not None and not account_matches(integration.account_email):
        raise DriveAccountMismatch(
            f"Google Drive is connected as {integration.account_email or 'an unknown account'}, "
            f"not {settings.GOOGLE_DRIVE_EXPECTED_ACCOUNT}. Uploads and syncing are paused "
            "until an admin reconnects with the right account in Sale Ready Admin."
        )


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
    def _lock_engagement(self, engagement_id: UUID, wait: bool = True) -> bool:
        """
        Serialise folder creation for one engagement across requests and workers.

        Transaction-scoped: released on commit or rollback. Re-entrant on the same
        connection. `wait=False` returns False instead of blocking when held.
        """
        fn = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
        got = self.db.execute(
            text(f"SELECT {fn}(:cls, hashtext(:eid))"),
            {"cls": ENGAGEMENT_FOLDER_LOCK_CLASS, "eid": str(engagement_id)},
        ).scalar()
        return True if wait else bool(got)

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
        # Another request may be creating it: wait, then use theirs if it now exists.
        self._lock_engagement(engagement.id)
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
        return self._ensure_category(engagement, category_code, client)[0]

    def _ensure_category(self, engagement: Engagement, category_code: str, client=None,
                         parent_is_new: bool = False) -> Tuple[str, bool]:
        """
        (folder id, whether Drive created it just now). A folder adopted by
        name may already hold sub-folders, so only a created one counts as empty.
        """
        existing = self.folder_id_for(engagement.id, category_code, None)
        if existing:
            return existing, False
        self._lock_engagement(engagement.id)
        existing = self.folder_id_for(engagement.id, category_code, None)
        if existing:
            return existing, False
        client = self._client(client)
        parent = self.ensure_data_room(engagement, client=client)
        name = safe_folder_name(
            self._category_label(engagement.id, category_code), f"Category {category_code}",
        )
        found = None if parent_is_new else client.find_folder(name, parent)
        folder = found or client.create_folder(name, parent)
        return self._record(engagement.id, category_code, None, folder).drive_folder_id, found is None

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
        return self._ensure_sub_item(engagement, category_code, sub_item_code, client)[0]

    def _ensure_sub_item(self, engagement: Engagement, category_code: str, sub_item_code: str,
                         client=None, parent_is_new: bool = False) -> Tuple[str, bool]:
        existing = self.folder_id_for(engagement.id, category_code, sub_item_code)
        if existing:
            return existing, False
        self._lock_engagement(engagement.id)
        existing = self.folder_id_for(engagement.id, category_code, sub_item_code)
        if existing:
            return existing, False
        client = self._client(client)
        parent = self.ensure_category(engagement, category_code, client=client)
        name = safe_folder_name(
            self._sub_item_label(engagement.id, category_code, sub_item_code), sub_item_code,
        )
        # A parent Drive created a moment ago is empty: no name search, no backfill.
        found = None if parent_is_new else client.find_folder(name, parent)
        row = self._record(engagement.id, category_code, sub_item_code,
                           found or client.create_folder(name, parent))
        if found:
            self._index_existing(row)
        return row.drive_folder_id, found is None

    # -- whole tree -----------------------------------------------------
    def expected_tree(self, engagement_id: UUID) -> Dict[str, List[str]]:
        """The DD folders this engagement should have: {category_code: [sub_item_code, ...]}."""
        rows = self.db.query(
            EngagementDDItem.category_code, EngagementDDItem.sub_item_code,
        ).filter(EngagementDDItem.engagement_id == engagement_id).distinct().all()
        tree: Dict[str, List[str]] = {}
        for cat, sub in sorted(rows, key=lambda r: (_code_key(r[0]), _code_key(r[1]))):
            tree.setdefault(cat, []).append(sub)
        return tree

    def provision_tree(self, engagement: Engagement, client=None) -> int:
        """
        Create and map every DD folder the engagement is missing. Returns how many were created.

        Idempotent: mapped folders are skipped, so a second run makes no Drive
        calls for them. Commits after the root and after each category, so an
        interruption keeps what exists; the root is never adopted by name, so
        losing its row would mean a duplicate tree.

        Raises EngagementBusy, without waiting, when an upload holds the
        engagement's folder lock. A commit releases the lock, so it is taken
        again before each category.
        """
        tree = self.expected_tree(engagement.id)
        if not tree:
            return 0
        if not self._lock_engagement(engagement.id, wait=False):
            raise EngagementBusy(str(engagement.id))
        client = self._client(client)
        root_is_new = self.folder_id_for(engagement.id) is None
        self.ensure_data_room(engagement, client=client)
        created = int(root_is_new)
        self.db.commit()
        for category_code, sub_items in tree.items():
            if not self._lock_engagement(engagement.id, wait=False):
                raise EngagementBusy(str(engagement.id))
            _, category_is_new = self._ensure_category(
                engagement, category_code, client, parent_is_new=root_is_new,
            )
            created += int(category_is_new)
            for sub_item_code in sub_items:
                _, sub_is_new = self._ensure_sub_item(
                    engagement, category_code, sub_item_code, client, parent_is_new=category_is_new,
                )
                created += int(sub_is_new)
            self.db.commit()
        return created

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


def _code_key(code: Optional[str]) -> Tuple:
    """Sort '3.10' after '3.9': numeric parts compared as numbers."""
    return tuple(int(p) if p.isdigit() else p for p in (code or "").split("."))


# In-process record of failed engagements: {engagement_id: (failures, retry_at)}.
# Lost on restart (the engagement is simply tried once more) and kept per API
# instance; persisting it would need a migration.
_provision_failures: Dict[UUID, Tuple[int, datetime]] = {}
_provision_failures_lock = threading.Lock()


def provision_backoff_seconds(failures: int) -> float:
    """Wait after `failures` consecutive failures: the sync interval, doubling, capped."""
    base = float(settings.GOOGLE_DRIVE_SYNC_INTERVAL_SECONDS)
    return min(base * (2 ** max(failures - 1, 0)), PROVISION_BACKOFF_MAX_SECONDS)


def _record_provision_failure(engagement_id: UUID, now: datetime) -> Tuple[int, datetime]:
    with _provision_failures_lock:
        failures = _provision_failures.get(engagement_id, (0, now))[0] + 1
        retry_at = now + timedelta(seconds=provision_backoff_seconds(failures))
        _provision_failures[engagement_id] = (failures, retry_at)
        return failures, retry_at


def _clear_provision_failure(engagement_id: UUID) -> None:
    with _provision_failures_lock:
        _provision_failures.pop(engagement_id, None)


def _is_backing_off(engagement_id: UUID, now: datetime) -> bool:
    with _provision_failures_lock:
        entry = _provision_failures.get(engagement_id)
    return entry is not None and now < entry[1]


def reset_provision_backoff() -> None:
    """Forget every recorded failure. For tests."""
    with _provision_failures_lock:
        _provision_failures.clear()


def pending_engagements(db: Session) -> List[Engagement]:
    """
    Live Sale Ready engagements whose folder tree is incomplete, oldest first.

    Incomplete means fewer mapped sub-item folders than distinct DD sub-items.
    A mapped sub-item implies its category and the root, so that one count is
    enough. Engagements with no DD items yet, or ended, completed or archived,
    are not due.
    """
    expected = db.query(
        EngagementDDItem.engagement_id.label("engagement_id"),
        func.count(func.distinct(func.concat(
            EngagementDDItem.category_code, "|", EngagementDDItem.sub_item_code,
        ))).label("n"),
    ).group_by(EngagementDDItem.engagement_id).subquery()
    mapped = db.query(
        EngagementDriveFolder.engagement_id.label("engagement_id"),
        func.count(EngagementDriveFolder.id).label("n"),
    ).filter(
        EngagementDriveFolder.sub_item_code.isnot(None),
    ).group_by(EngagementDriveFolder.engagement_id).subquery()
    return (
        db.query(Engagement)
        .join(expected, expected.c.engagement_id == Engagement.id)
        .outerjoin(mapped, mapped.c.engagement_id == Engagement.id)
        .filter(
            Engagement.tool == PROGRAM_SALE_READY,
            Engagement.is_deleted == False,  # noqa: E712
            Engagement.status.notin_(_NOT_PROVISIONED_STATUSES),
            func.coalesce(mapped.c.n, 0) < expected.c.n,
        )
        .order_by(Engagement.created_at.asc(), Engagement.id.asc())
        .all()
    )


def provision_pending(db: Session, limit: int = PROVISION_BATCH,
                      now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """
    One scheduler pass's share of folder provisioning. None when nothing is due.

    Takes the oldest pending engagements that are not backing off. A failure
    that belongs to one engagement (a folder gone from Drive, a folder mapped
    to another engagement, anything unexpected) is logged, backs that
    engagement off and the pass moves on. A connection-level failure (not
    connected, wrong account, throttled, Drive down) ends the pass and is
    raised for the scheduler to report, since every engagement would hit it.
    """
    pending = pending_engagements(db)
    if not pending:
        return None
    require_expected_account(db)
    client = get_drive_client(db)
    service = get_drive_folder_service(db)
    now = now or datetime.utcnow()
    eligible = [e for e in pending if not _is_backing_off(e.id, now)]
    done = folders = 0
    failed: List[str] = []
    busy: List[str] = []
    try:
        for engagement in eligible[:limit]:
            try:
                folders += service.provision_tree(engagement, client=client)
                done += 1
                _clear_provision_failure(engagement.id)
            except EngagementBusy:
                # An upload is creating its folders right now. Not a failure: no
                # backoff; what was committed stays and the next pass finishes it.
                db.rollback()
                busy.append(str(engagement.id))
            except (DriveNotFound, SharedDriveFolder) as exc:
                db.rollback()
                count, retry_at = _record_provision_failure(engagement.id, now)
                failed.append(str(engagement.id))
                logger.warning("Drive folders for engagement %s failed (%d in a row): %s; next try after %s",
                               engagement.id, count, exc, retry_at.isoformat())
            except DriveUnavailable:
                raise
            except Exception:
                db.rollback()
                count, retry_at = _record_provision_failure(engagement.id, now)
                failed.append(str(engagement.id))
                logger.exception("Could not provision Drive folders for engagement %s (%d in a row); "
                                 "next try after %s", engagement.id, count, retry_at.isoformat())
    finally:
        logger.info("Drive folders provisioned %d/%d pending engagement(s) this pass; %d failed, "
                    "%d busy, %d backing off; %d folder(s) created",
                    done, len(pending), len(failed), len(busy), len(pending) - len(eligible), folders)
    return {"provisioned": done, "pending": len(pending), "folders_created": folders,
            "failed": failed, "busy": busy, "backing_off": len(pending) - len(eligible)}


def get_drive_folder_service(db: Session) -> DriveFolderService:
    return DriveFolderService(db)
