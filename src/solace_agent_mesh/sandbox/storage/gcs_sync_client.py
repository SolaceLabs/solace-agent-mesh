"""Google Cloud Storage sync client."""

import logging

from .base import SyncObjectMeta, ToolSyncStorageClient

log = logging.getLogger(__name__)


class GcsSyncClient(ToolSyncStorageClient):
    """Read-only GCS storage client for tool sync."""

    def __init__(
        self,
        bucket_name: str,
        project: str | None = None,
        credentials_path: str | None = None,
    ):
        try:
            from google.cloud import storage as gcs_storage
        except ImportError as e:
            raise ImportError(
                "google-cloud-storage is required for GCS sync. "
                "Install it with: pip install google-cloud-storage"
            ) from e

        kwargs: dict = {}
        if project:
            kwargs["project"] = project
        if credentials_path:
            from google.oauth2 import service_account

            kwargs["credentials"] = service_account.Credentials.from_service_account_file(
                credentials_path
            )

        client = gcs_storage.Client(**kwargs)
        self._bucket = client.bucket(bucket_name)

    def list_objects(self, prefix: str) -> list[SyncObjectMeta]:
        result: list[SyncObjectMeta] = []
        for blob in self._bucket.list_blobs(prefix=prefix):
            etag = blob.etag or blob.md5_hash or ""
            result.append(
                SyncObjectMeta(
                    key=blob.name,
                    etag=etag,
                    size=blob.size or 0,
                )
            )
        return result

    def download_object(self, key: str) -> bytes:
        blob = self._bucket.blob(key)
        return blob.download_as_bytes()
