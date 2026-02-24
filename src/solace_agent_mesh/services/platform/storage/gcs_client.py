"""Google Cloud Storage client."""

import logging

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import storage as gcs
from google.oauth2 import service_account

from .base import ObjectStorageClient, StorageObject
from .exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
)

log = logging.getLogger(__name__)


class GcsStorageClient(ObjectStorageClient):
    """Google Cloud Storage client."""

    def __init__(
        self,
        bucket_name: str,
        project: str | None = None,
        credentials_path: str | None = None,
    ):
        self._bucket_name = bucket_name
        kwargs: dict = {}
        if project:
            kwargs["project"] = project
        if credentials_path:
            kwargs["credentials"] = service_account.Credentials.from_service_account_file(credentials_path)

        self._gcs_client = gcs.Client(**kwargs)
        self._bucket = self._gcs_client.bucket(bucket_name)

    def put_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            blob = self._bucket.blob(key)
            if metadata:
                blob.metadata = metadata
            blob.upload_from_string(content, content_type=content_type)
            return key
        except Exception as e:
            raise self._translate_error(e, key) from e

    def get_object(self, key: str) -> StorageObject:
        try:
            blob = self._bucket.blob(key)
            content = blob.download_as_bytes()
            blob.reload()
            return StorageObject(
                content=content,
                content_type=blob.content_type or "application/octet-stream",
                metadata=blob.metadata or {},
            )
        except Exception as e:
            raise self._translate_error(e, key) from e

    def delete_object(self, key: str) -> None:
        try:
            blob = self._bucket.blob(key)
            blob.delete()
        except Exception as e:
            translated = self._translate_error(e, key)
            if isinstance(translated, StorageNotFoundError):
                return
            raise translated from e

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        try:
            blobs = list(self._bucket.list_blobs(prefix=prefix))
            if blobs:
                self._bucket.delete_blobs(blobs)
                deleted = len(blobs)
            return deleted
        except Exception as e:
            raise self._translate_error(e) from e

    def get_public_url(self, key: str) -> str:
        return f"https://storage.googleapis.com/{self._bucket_name}/{key}"

    def _translate_error(self, error: Exception, key: str | None = None) -> StorageError:
        if isinstance(error, NotFound):
            return StorageNotFoundError(str(error), key=key, cause=error)
        if isinstance(error, Forbidden):
            return StoragePermissionError(str(error), key=key, cause=error)
        if isinstance(error, ConnectionError):
            return StorageConnectionError(str(error), key=key, cause=error)
        return StorageError(str(error), key=key, cause=error)
