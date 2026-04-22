import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveService:
    def __init__(self, credentials_file: str, folder_id: str):
        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=creds)
        self._folder_id = folder_id

    def upload_bytes(self, filename: str, content: bytes, mime_type: str) -> str:
        """Upload bytes to the configured Drive folder; returns the Drive file_id."""
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
        file_meta = {"name": filename, "parents": [self._folder_id]}
        result = (
            self._service.files()
            .create(body=file_meta, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
        return result["id"]

    def download_bytes(self, file_id: str) -> bytes:
        """Download a Drive file by file_id and return its raw bytes."""
        request = self._service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def delete_file(self, file_id: str) -> None:
        """Permanently delete a Drive file by file_id."""
        self._service.files().delete(fileId=file_id, supportsAllDrives=True).execute()


def get_google_drive_service() -> GoogleDriveService:
    from app.config import settings
    from pathlib import Path
    creds_file = settings.GOOGLE_DRIVE_CREDENTIALS_FILE
    # Resolve relative paths against the backend root (two levels up from this file)
    if not Path(creds_file).is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        creds_file = str(backend_root / creds_file)
    return GoogleDriveService(
        credentials_file=creds_file,
        folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
    )
