"""
The Google Drive client: the only place that talks to Google.

Drive is the data room's store. Trinity creates the folders, uploads into
them, streams files back out and never keeps a copy of the bytes.

Three things shape this module:

  - authentication is OAuth against Benchmark's central account, not a
    service account. A refresh token is obtained once through the admin
    connect flow and stored encrypted in drive_integration; every call here
    exchanges it for a short-lived access token. That account is system-use
    only - no advisor, client or buyer ever holds Drive credentials, and no
    Drive URL is returned by any endpoint they can reach;
  - the google libraries are imported lazily, inside the functions that need
    them. Trinity has to boot, run its tests and serve every other feature on
    a machine where Drive was never set up, so a missing library is a
    disabled integration rather than a failed import;
  - nothing here raises a google exception outward. Everything becomes
    DriveUnavailable, which routers turn into a 503 with a sentence, so a
    Drive outage never surfaces as a stack trace or a 500.

This module has no FastAPI imports and no knowledge of engagements, per the
layer rules: it moves bytes and folders, and that is all.
"""
import logging
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Full drive scope, not drive.file. drive.file only shows the app the files it
# created itself, which would make "pick up files added directly in Drive"
# impossible - and that is a stated requirement.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

FOLDER_MIME = "application/vnd.google-apps.folder"

# Google-native documents have no bytes to download and are not what a data
# room holds; they are skipped by the sync rather than half-imported.
GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps."

# What we ask Drive for. Kept in one place so the sync and the upload path
# agree on the shape of a file record.
FILE_FIELDS = "id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents, trashed, md5Checksum"


class DriveUnavailable(RuntimeError):
    """
    Drive cannot be reached, is not configured, or refused the call.

    One exception for most failure modes on purpose: a caller has the same
    choice in nearly all of them - tell the user the data room is unavailable -
    and the distinction between "no credentials", "token revoked" and "Google
    is down" belongs in the log and the admin screen, not in control flow.
    """


class DriveRateLimited(DriveUnavailable):
    """
    Google throttled us. Transient, and emphatically not a broken connection.

    Split out because Drive answers 403 both for "your token is no longer
    valid" and for "you are going too fast". Treating the second as the first
    marks a perfectly healthy integration as disconnected and sends an admin
    off to re-authorise for nothing. Subclasses DriveUnavailable so every
    existing handler still turns it into a 503; only the callers that record
    connection health look for it specifically.
    """


class DriveTransient(DriveUnavailable):
    """
    Google failed in a way that is worth trying again - a 5xx, or a network
    blip. Like DriveRateLimited, a subclass so existing handlers still see a
    DriveUnavailable; unlike a permission failure, it says nothing about
    whether the connection is healthy.
    """


# How hard we try before giving a transient failure back to the caller. Three
# attempts over roughly a second: enough to ride out a blip, short enough that
# a user waiting on an upload is not left hanging.
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.5

# Drive returns 403 for throttling as well as for permission failures. These
# are the reasons that mean "slow down", taken from the Drive API error docs.
RATE_LIMIT_REASONS = frozenset({
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "dailyLimitExceeded",
    "sharingRateLimitExceeded",
    "quotaExceeded",
})


def drive_enabled() -> bool:
    """Whether the integration is switched on at all. Cheap, no I/O."""
    return bool(settings.GOOGLE_DRIVE_ENABLED)


def _rate_limit_reason(exc) -> Optional[str]:
    """
    The throttling reason behind a 403, or None if it was a real refusal.

    Drive puts the reason in the error body rather than the status, so it has
    to be dug out of the JSON. Anything unparseable is treated as a genuine
    permission failure: guessing "it was probably rate limiting" would hide a
    revoked token behind a message telling the admin to wait.
    """
    import json

    try:
        payload = json.loads((exc.content or b"{}").decode("utf-8"))
    except Exception:
        return None
    errors = (payload.get("error") or {}).get("errors") or []
    for entry in errors:
        reason = entry.get("reason")
        if reason in RATE_LIMIT_REASONS:
            return reason
    status_reason = (payload.get("error") or {}).get("status")
    return "quotaExceeded" if status_reason == "RESOURCE_EXHAUSTED" else None


def _require_libraries():
    """Import the google libraries, or explain why the data room is off."""
    try:
        from google.auth.transport.requests import Request  # noqa: F401
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    except ImportError as exc:  # pragma: no cover - depends on the deployment
        raise DriveUnavailable(
            "The Google Drive libraries are not installed. Run "
            "`pip install -r requirements.txt` to enable the data room."
        ) from exc
    return Credentials, build, HttpError, MediaIoBaseDownload, MediaIoBaseUpload


# ----------------------------------------------------------------------
# Token encryption
# ----------------------------------------------------------------------
def encrypt_token(raw: str) -> str:
    """
    Encrypt a refresh token for storage.

    Refuses rather than falling back to plain text: a refresh token is the
    key to every client's documents, and storing one unencrypted because a
    setting was missing is the kind of thing nobody notices until it matters.
    """
    key = settings.GOOGLE_DRIVE_TOKEN_KEY
    if not key:
        raise DriveUnavailable(
            "GOOGLE_DRIVE_TOKEN_KEY is not set, so the refresh token cannot be "
            "stored safely. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`."
        )
    from cryptography.fernet import Fernet

    return Fernet(key.encode()).encrypt(raw.encode()).decode()


def decrypt_token(stored: str) -> str:
    """Reverse of encrypt_token. A wrong or rotated key fails loudly."""
    key = settings.GOOGLE_DRIVE_TOKEN_KEY
    if not key:
        raise DriveUnavailable("GOOGLE_DRIVE_TOKEN_KEY is not set, so the stored token cannot be read.")
    from cryptography.fernet import Fernet, InvalidToken

    try:
        return Fernet(key.encode()).decrypt(stored.encode()).decode()
    except InvalidToken as exc:
        raise DriveUnavailable(
            "The stored Drive token could not be decrypted. GOOGLE_DRIVE_TOKEN_KEY "
            "has probably changed; reconnect the Drive account."
        ) from exc


# ----------------------------------------------------------------------
# OAuth flow
# ----------------------------------------------------------------------
def authorization_url(state: str) -> str:
    """
    Where an admin goes to authorise Trinity.

    access_type=offline with prompt=consent is what makes Google return a
    refresh token; without both, a second authorisation returns only an
    access token and the connection dies in an hour.
    """
    _oauth_config_or_raise()
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=DRIVE_SCOPES)
    flow.redirect_uri = settings.GOOGLE_DRIVE_REDIRECT_URI
    url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true", state=state,
    )
    return url


def exchange_code(code: str) -> Tuple[str, Optional[str]]:
    """Trade the callback code for (refresh_token, account_email)."""
    _oauth_config_or_raise()
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=DRIVE_SCOPES)
    flow.redirect_uri = settings.GOOGLE_DRIVE_REDIRECT_URI
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        raise DriveUnavailable(f"Google refused the authorisation code: {exc}") from exc

    credentials = flow.credentials
    if not credentials.refresh_token:
        raise DriveUnavailable(
            "Google returned no refresh token. Remove Trinity from the account's "
            "third-party access and authorise again so the consent screen is shown."
        )
    return credentials.refresh_token, _account_email(credentials)


def _account_email(credentials) -> Optional[str]:
    """Best-effort: which account authorised us. Never fatal."""
    try:
        from googleapiclient.discovery import build

        about = build("drive", "v3", credentials=credentials, cache_discovery=False).about()
        return (about.get(fields="user(emailAddress)").execute() or {}).get("user", {}).get("emailAddress")
    except Exception:
        logger.warning("Could not read the Drive account email; continuing without it")
        return None


def _client_config() -> Dict[str, Any]:
    return {
        "web": {
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_DRIVE_REDIRECT_URI],
        }
    }


def _oauth_config_or_raise() -> None:
    missing = [
        name for name in
        ("GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET", "GOOGLE_DRIVE_REDIRECT_URI")
        if not getattr(settings, name, None)
    ]
    if missing:
        raise DriveUnavailable(
            "Google Drive is not configured. Missing: " + ", ".join(missing)
        )


# ----------------------------------------------------------------------
# The client
# ----------------------------------------------------------------------
class DriveClient:
    """
    A thin wrapper over the Drive v3 API.

    Deliberately dumb: it knows about folders, files and change events, and
    nothing about engagements, DD items or buyers. Callers supply ids.
    """

    def __init__(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._service = None

    # -- plumbing -------------------------------------------------------
    def _svc(self):
        if self._service is not None:
            return self._service
        Credentials, build, _, _, _ = _require_libraries()
        _oauth_config_or_raise()
        credentials = Credentials(
            token=None,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_DRIVE_CLIENT_ID,
            client_secret=settings.GOOGLE_DRIVE_CLIENT_SECRET,
            scopes=DRIVE_SCOPES,
        )
        try:
            self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise DriveUnavailable(f"Could not open a Drive session: {exc}") from exc
        return self._service

    @staticmethod
    def _classify(exc, HttpError) -> DriveUnavailable:
        """Turn one Google failure into the right DriveUnavailable subclass."""
        if not isinstance(exc, HttpError):
            # A socket error, a DNS failure, a timeout. Worth another go.
            return DriveTransient(f"Drive could not be reached: {exc}")

        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 404:
            return DriveUnavailable("That file or folder no longer exists in Drive.")
        if status == 403 and _rate_limit_reason(exc):
            return DriveRateLimited(
                "Google is rate limiting Trinity. This is temporary - the "
                "connection is fine. Try again shortly."
            )
        if status in (401, 403):
            return DriveUnavailable(
                "Google refused the request. The Drive connection may have been "
                "revoked; reconnect the account in Sale Ready Admin."
            )
        if status is not None and status >= 500:
            return DriveTransient(f"Drive is having trouble ({status}).")
        return DriveUnavailable(f"Drive returned an error ({status}).")

    @staticmethod
    def _call(request, _sleep=None):
        """
        Run one API request, retrying the failures that are worth retrying.

        Throttling and 5xx get up to RETRY_ATTEMPTS tries with exponential
        backoff and jitter. Jitter matters: several uploads throttled at once
        would otherwise all come back at the same instant and throttle again.

        Auth failures, permission failures and 404s are never retried. They
        will fail identically every time, and retrying an expired token just
        makes the user wait longer for the same answer.
        """
        import random
        import time

        _, _, HttpError, _, _ = _require_libraries()
        sleep = _sleep or time.sleep

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return request.execute()
            except Exception as exc:
                failure = DriveClient._classify(exc, HttpError)
                retryable = isinstance(failure, (DriveRateLimited, DriveTransient))
                if not retryable or attempt == RETRY_ATTEMPTS:
                    raise failure from exc
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) * (1 + random.random())
                logger.info("Drive call failed (%s); retrying in %.1fs (attempt %d/%d)",
                            failure.__class__.__name__, delay, attempt, RETRY_ATTEMPTS)
                sleep(delay)

    # -- folders --------------------------------------------------------
    def find_folder(self, name: str, parent_id: str) -> Optional[Dict[str, Any]]:
        """The first non-trashed folder with this name under this parent."""
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and mimeType = '{FOLDER_MIME}' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        found = self._call(self._svc().files().list(
            q=query, fields="files(id, name, webViewLink)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ))
        files = (found or {}).get("files") or []
        return files[0] if files else None

    def create_folder(self, name: str, parent_id: str) -> Dict[str, Any]:
        return self._call(self._svc().files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
            fields="id, name, webViewLink", supportsAllDrives=True,
        ))

    def ensure_folder(self, name: str, parent_id: str) -> Dict[str, Any]:
        """
        Get this folder, creating it only if it is not already there.

        Find-then-create is not atomic, so two simultaneous uploads into a new
        folder can both create one. Drive allows that - ids are the identity,
        not names - and the caller stores whichever id it gets, so the result
        is a harmless duplicate rather than an error or a lost file.
        """
        return self.find_folder(name, parent_id) or self.create_folder(name, parent_id)

    # -- files ----------------------------------------------------------
    def upload(self, stream: BinaryIO, name: str, mime_type: Optional[str],
               parent_id: str) -> Dict[str, Any]:
        """Stream an upload straight into Drive. The bytes never touch Trinity's disk."""
        _, _, _, _, MediaIoBaseUpload = _require_libraries()
        media = MediaIoBaseUpload(
            stream, mimetype=mime_type or "application/octet-stream", resumable=False,
        )
        return self._call(self._svc().files().create(
            body={"name": name, "parents": [parent_id]},
            media_body=media, fields=FILE_FIELDS, supportsAllDrives=True,
        ))

    def download_stream(self, file_id: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        """
        Yield a file's bytes in chunks.

        A generator so a download is streamed to the caller rather than held
        in memory: Trinity is a pipe here, not a store.
        """
        import io

        _, _, _, MediaIoBaseDownload, _ = _require_libraries()
        buffer = io.BytesIO()
        request = self._svc().files().get_media(fileId=file_id, supportsAllDrives=True)
        downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)
        done = False
        while not done:
            try:
                _, done = downloader.next_chunk()
            except Exception as exc:
                raise DriveUnavailable(f"The document could not be read from Drive: {exc}") from exc
            buffer.seek(0)
            chunk = buffer.read()
            buffer.seek(0)
            buffer.truncate(0)
            if chunk:
                yield chunk

    def get_metadata(self, file_id: str) -> Dict[str, Any]:
        return self._call(self._svc().files().get(
            fileId=file_id, fields=FILE_FIELDS, supportsAllDrives=True,
        ))

    def rename(self, file_id: str, name: str) -> Dict[str, Any]:
        return self._call(self._svc().files().update(
            fileId=file_id, body={"name": name}, fields=FILE_FIELDS, supportsAllDrives=True,
        ))

    def move(self, file_id: str, new_parent_id: str, old_parent_id: str) -> Dict[str, Any]:
        return self._call(self._svc().files().update(
            fileId=file_id, addParents=new_parent_id, removeParents=old_parent_id,
            fields=FILE_FIELDS, supportsAllDrives=True,
        ))

    def trash(self, file_id: str) -> None:
        """
        Trash, never delete.

        A permanently deleted file cannot be recovered, and buyer_access_log
        rows point at these documents: a mistaken delete would destroy the
        record of what a buyer was shown. Trash is reversible from Drive.
        """
        self._call(self._svc().files().update(
            fileId=file_id, body={"trashed": True}, fields="id", supportsAllDrives=True,
        ))

    def list_children(self, parent_id: str) -> List[Dict[str, Any]]:
        """Non-trashed, non-folder children of one folder."""
        out: List[Dict[str, Any]] = []
        page = None
        while True:
            result = self._call(self._svc().files().list(
                q=f"'{parent_id}' in parents and trashed = false and mimeType != '{FOLDER_MIME}'",
                fields=f"nextPageToken, files({FILE_FIELDS})", pageToken=page, pageSize=200,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ))
            out.extend((result or {}).get("files") or [])
            page = (result or {}).get("nextPageToken")
            if not page:
                return out

    # -- change feed ----------------------------------------------------
    def start_page_token(self) -> str:
        result = self._call(self._svc().changes().getStartPageToken(supportsAllDrives=True))
        return (result or {}).get("startPageToken")

    def list_changes(self, page_token: str) -> Tuple[List[Dict[str, Any]], Optional[str], str]:
        """
        Everything that changed since page_token.

        Returns (changes, next_page_token, new_start_token). next_page_token
        is None once the feed is exhausted; new_start_token is what to store
        for the next run.
        """
        changes: List[Dict[str, Any]] = []
        token = page_token
        new_start = page_token
        while True:
            result = self._call(self._svc().changes().list(
                pageToken=token,
                fields=f"nextPageToken, newStartPageToken, changes(fileId, removed, time, file({FILE_FIELDS}))",
                pageSize=200, includeRemoved=True,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            )) or {}
            changes.extend(result.get("changes") or [])
            if result.get("newStartPageToken"):
                new_start = result["newStartPageToken"]
            token = result.get("nextPageToken")
            if not token:
                return changes, None, new_start
