"""Azure Blob Storage sync client."""

import logging

from .base import SyncObjectMeta, ToolSyncStorageClient

log = logging.getLogger(__name__)


class AzureSyncClient(ToolSyncStorageClient):
    """Read-only Azure Blob storage client for tool sync."""

    def __init__(
        self,
        container_name: str,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
    ):
        try:
            from azure.storage.blob import ContainerClient
        except ImportError as e:
            raise ImportError(
                "azure-storage-blob is required for Azure sync. "
                "Install it with: pip install azure-storage-blob"
            ) from e

        if connection_string:
            self._container = ContainerClient.from_connection_string(
                connection_string, container_name=container_name
            )
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self._container = ContainerClient(
                account_url,
                container_name=container_name,
                credential=account_key,
            )
        else:
            raise ValueError(
                "Azure storage requires either connection_string or both account_name and account_key"
            )

    def list_objects(self, prefix: str) -> list[SyncObjectMeta]:
        result: list[SyncObjectMeta] = []
        for blob in self._container.list_blobs(name_starts_with=prefix):
            etag = (blob.etag or "").strip('"')
            result.append(
                SyncObjectMeta(
                    key=blob.name,
                    etag=etag,
                    size=blob.size or 0,
                )
            )
        return result

    def download_object(self, key: str) -> bytes:
        return self._container.download_blob(key).readall()
