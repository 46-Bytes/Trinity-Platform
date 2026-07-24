"""
File storage abstraction over local disk and Azure Blob Storage.

Callers work with a "key" — a path relative to the files root (e.g.
"uploads/diagnostic/<id>/<uuid>.pdf"), regardless of which backend is
active. Backend is picked by settings.STORAGE_BACKEND:
  - "local" (default): reads/writes backend/files/<key> on disk.
  - "azure_blob": reads/writes blobs named <key> in an Azure Storage
    container. Used in production (Container Apps replicas don't share
    or persist local disk).

Rows written before this abstraction existed may hold an absolute local
path in place of a key (e.g. Media.file_path). Both backends fall back to
reading that path directly off local disk so old dev data keeps working;
this fallback will never match on a real Azure deployment since it only
triggers for values that are themselves valid absolute paths on this host.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def write_bytes(self, key: str, content: bytes) -> None:
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        """Delete every object whose key starts with prefix (e.g. clearing
        out a user's old profile pictures before writing a new one)."""
        raise NotImplementedError

    def local_path(self, key: str) -> Optional[Path]:
        """Real filesystem path for this key, if the backend has one.

        Some callers (uploading a file to the Claude Files API) need an
        actual path to open(). Local backend can hand one back directly;
        blob backend returns None and callers fall back to a temp file.
        """
        return None


class LocalStorageService(StorageService):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if os.path.isabs(key):
            return Path(key)
        return self.base_dir / key

    def write_bytes(self, key: str, content: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete_prefix(self, prefix: str) -> None:
        dir_path = self._resolve(prefix)
        if not dir_path.is_dir():
            return
        for child in dir_path.iterdir():
            if child.is_file():
                try:
                    child.unlink()
                except OSError:
                    pass

    def local_path(self, key: str) -> Optional[Path]:
        return self._resolve(key)


class AzureBlobStorageService(StorageService):
    def __init__(self, connection_string: str, container_name: str):
        from azure.storage.blob import BlobServiceClient

        client = BlobServiceClient.from_connection_string(connection_string)
        self._container = client.get_container_client(container_name)
        try:
            self._container.create_container()
        except Exception:
            pass  # already exists

    def _legacy_local(self, key: str) -> Optional[Path]:
        if os.path.isabs(key) and os.path.exists(key):
            return Path(key)
        return None

    def write_bytes(self, key: str, content: bytes) -> None:
        self._container.upload_blob(name=key, data=content, overwrite=True)

    def read_bytes(self, key: str) -> bytes:
        legacy = self._legacy_local(key)
        if legacy is not None:
            return legacy.read_bytes()
        return self._container.download_blob(key).readall()

    def delete(self, key: str) -> None:
        legacy = self._legacy_local(key)
        if legacy is not None:
            legacy.unlink(missing_ok=True)
            return
        try:
            self._container.delete_blob(key)
        except Exception:
            pass  # already gone

    def exists(self, key: str) -> bool:
        legacy = self._legacy_local(key)
        if legacy is not None:
            return True
        return self._container.get_blob_client(key).exists()

    def delete_prefix(self, prefix: str) -> None:
        prefix = prefix.rstrip("/") + "/"
        for blob in self._container.list_blobs(name_starts_with=prefix):
            try:
                self._container.delete_blob(blob.name)
            except Exception:
                pass


@lru_cache
def get_storage_service() -> StorageService:
    if settings.STORAGE_BACKEND == "azure_blob":
        if not settings.AZURE_STORAGE_CONNECTION_STRING:
            raise RuntimeError(
                "AZURE_STORAGE_CONNECTION_STRING is required when STORAGE_BACKEND=azure_blob"
            )
        logger.info("Using Azure Blob storage backend (container=%s)", settings.AZURE_STORAGE_CONTAINER)
        return AzureBlobStorageService(
            connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
            container_name=settings.AZURE_STORAGE_CONTAINER,
        )
    base_dir = Path(__file__).resolve().parents[2] / "files"
    logger.info("Using local disk storage backend (base_dir=%s)", base_dir)
    return LocalStorageService(base_dir)
