"""
Google Drive file storage service.

Mirrors local file saves to Google Drive using OAuth2 credentials.
Requires an OAuth2 credentials JSON file and a target Drive folder ID.
On first run, opens a browser for the user to authorize; the token is
then cached to ``drive_token.json`` for subsequent runs.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

from app.config import settings

logger = logging.getLogger(__name__)

# Drive API scopes
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# MIME type mapping for common extensions
MIME_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "txt": "text/plain",
    "rtf": "application/rtf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "zip": "application/zip",
}


class GoogleDriveService:
    """Handles uploading files to Google Drive via OAuth2."""

    def __init__(self):
        self._service = None
        self._enabled = bool(
            settings.GOOGLE_DRIVE_ENABLED
            and settings.GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE
            and settings.GOOGLE_DRIVE_FOLDER_ID
        )
        if not self._enabled:
            logger.info("Google Drive integration is disabled (missing config).")

    def _get_service(self):
        """Lazily build and cache the Drive API client using OAuth2."""
        if self._service is not None:
            return self._service

        creds = None
        token_path = Path(settings.GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE).parent / "drive_token.json"

        # Load cached token
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # Refresh or run auth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for next run
            token_path.write_text(creds.to_json())
            logger.info(f"OAuth token saved to {token_path}")

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _resolve_mime_type(self, filename: str, content_type: Optional[str] = None) -> str:
        """Return the best MIME type for the given filename."""
        if content_type and content_type != "application/octet-stream":
            return content_type
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return MIME_TYPES.get(ext, "application/octet-stream")

    def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """Find or create a subfolder inside *parent_id*."""
        service = self._get_service()
        query = (
            f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        results = service.files().list(
            q=query, spaces="drive", fields="files(id, name)", pageSize=1,
        ).execute()

        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=file_metadata, fields="id").execute()
        logger.info(f"Created Drive folder '{folder_name}' -> {folder['id']}")
        return folder["id"]

    def _resolve_folder(self, subfolder_path: str) -> str:
        """
        Walk a '/'-separated subfolder path under the root Drive folder,
        creating each level as needed. Returns the final folder ID.

        Example: subfolder_path="bba/project-123" will create
        root_folder -> bba -> project-123
        """
        parent_id = settings.GOOGLE_DRIVE_FOLDER_ID
        if not subfolder_path:
            return parent_id
        for part in subfolder_path.strip("/").split("/"):
            if part:
                parent_id = self._get_or_create_folder(part, parent_id)
        return parent_id

    def upload_file_from_path(
        self,
        local_path: str,
        drive_filename: Optional[str] = None,
        subfolder: str = "",
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Upload a local file to Google Drive.

        Args:
            local_path: Absolute path to the file on disk.
            drive_filename: Name to use on Drive. Defaults to the local filename.
            subfolder: Subfolder path under the root Drive folder (e.g. "diagnostic/uuid").
            content_type: MIME type override.

        Returns:
            The Google Drive file ID, or None if upload is disabled/fails.
        """
        if not self._enabled:
            return None

        try:
            path = Path(local_path)
            if not path.exists():
                logger.warning(f"Cannot upload to Drive — file not found: {local_path}")
                return None

            filename = drive_filename or path.name
            mime_type = self._resolve_mime_type(filename, content_type)
            folder_id = self._resolve_folder(subfolder)

            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
            file_metadata = {"name": filename, "parents": [folder_id]}

            service = self._get_service()
            result = service.files().create(
                body=file_metadata, media_body=media, fields="id, webViewLink",
            ).execute()

            file_id = result.get("id")
            logger.info(f"Uploaded '{filename}' to Drive -> {file_id}")
            return file_id

        except Exception as e:
            logger.error(f"Google Drive upload failed for '{local_path}': {e}", exc_info=True)
            return None

    def upload_file_from_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        subfolder: str = "",
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Upload in-memory bytes to Google Drive.

        Args:
            file_bytes: Raw file content.
            filename: Name for the file on Drive.
            subfolder: Subfolder path under the root Drive folder.
            content_type: MIME type override.

        Returns:
            The Google Drive file ID, or None if upload is disabled/fails.
        """
        if not self._enabled:
            return None

        try:
            mime_type = self._resolve_mime_type(filename, content_type)
            folder_id = self._resolve_folder(subfolder)

            media = MediaIoBaseUpload(
                io.BytesIO(file_bytes), mimetype=mime_type, resumable=True
            )
            file_metadata = {"name": filename, "parents": [folder_id]}

            service = self._get_service()
            result = service.files().create(
                body=file_metadata, media_body=media, fields="id, webViewLink",
            ).execute()

            file_id = result.get("id")
            logger.info(f"Uploaded '{filename}' (bytes) to Drive -> {file_id}")
            return file_id

        except Exception as e:
            logger.error(f"Google Drive upload failed for '{filename}': {e}", exc_info=True)
            return None

    def delete_file(self, drive_file_id: str) -> bool:
        """
        Delete a file from Google Drive.

        Args:
            drive_file_id: The Google Drive file ID.

        Returns:
            True if deleted successfully.
        """
        if not self._enabled or not drive_file_id:
            return False

        try:
            service = self._get_service()
            service.files().delete(fileId=drive_file_id).execute()
            logger.info(f"Deleted Drive file {drive_file_id}")
            return True
        except Exception as e:
            logger.error(f"Google Drive delete failed for '{drive_file_id}': {e}", exc_info=True)
            return False


# Singleton instance
google_drive_service = GoogleDriveService()
