"""Azure Blob Storage client."""

import logging
from datetime import datetime, timedelta, timezone

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from .base import ObjectStorageClient, StorageObject
from .exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
)

log = logging.getLogger(__name__)


class AzureBlobStorageClient(ObjectStorageClient):
    """Azure Blob Storage client."""

    def __init__(
        self,
        container_name: str,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
    ):
        self._container_name = container_name
        self._account_name = account_name
        self._account_key = account_key

        if connection_string:
            self._service_client = BlobServiceClient.from_connection_string(connection_string)
            if not self._account_key:
                self._account_key = self._extract_key_from_connection_string(connection_string)
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self._service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        else:
            raise ValueError("Azure Blob Storage requires either connection_string or account_name + account_key")

        if not self._account_name:
            self._account_name = self._service_client.account_name
        self._container_client = self._service_client.get_container_client(container_name)

    def put_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            blob_client = self._container_client.get_blob_client(key)
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
                metadata=metadata,
            )
            return key
        except Exception as e:
            raise self._translate_error(e, key) from e

    def get_object(self, key: str) -> StorageObject:
        try:
            blob_client = self._container_client.get_blob_client(key)
            download = blob_client.download_blob()
            properties = download.properties
            return StorageObject(
                content=download.readall(),
                content_type=properties.content_settings.content_type or "application/octet-stream",
                metadata=properties.metadata or {},
            )
        except Exception as e:
            raise self._translate_error(e, key) from e

    def delete_object(self, key: str) -> None:
        try:
            blob_client = self._container_client.get_blob_client(key)
            blob_client.delete_blob()
        except Exception as e:
            translated = self._translate_error(e, key)
            if isinstance(translated, StorageNotFoundError):
                return
            raise translated from e

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        try:
            blobs = self._container_client.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                self._container_client.get_blob_client(blob.name).delete_blob()
                deleted += 1
            return deleted
        except Exception as e:
            raise self._translate_error(e) from e

    def list_objects(self, prefix: str) -> list[str]:
        try:
            return [blob.name for blob in self._container_client.list_blobs(name_starts_with=prefix)]
        except Exception as e:
            raise self._translate_error(e) from e

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        if not self._account_key:
            raise StoragePermissionError(
                "Account key is required to generate presigned URLs",
                key=key,
            )
        try:
            sas_token = generate_blob_sas(
                account_name=self._account_name,
                container_name=self._container_name,
                blob_name=key,
                account_key=self._account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            )
            return (
                f"https://{self._account_name}.blob.core.windows.net"
                f"/{self._container_name}/{key}?{sas_token}"
            )
        except Exception as e:
            raise self._translate_error(e, key) from e

    def get_public_url(self, key: str) -> str:
        return f"https://{self._account_name}.blob.core.windows.net/{self._container_name}/{key}"

    @staticmethod
    def _extract_key_from_connection_string(connection_string: str) -> str | None:
        for part in connection_string.split(";"):
            if part.strip().lower().startswith("accountkey="):
                return part.split("=", 1)[1]
        return None

    def _translate_error(self, error: Exception, key: str | None = None) -> StorageError:
        if isinstance(error, ResourceNotFoundError):
            return StorageNotFoundError(str(error), key=key, cause=error)
        if isinstance(error, HttpResponseError) and error.status_code == 403:
            return StoragePermissionError(str(error), key=key, cause=error)
        if isinstance(error, ConnectionError):
            return StorageConnectionError(str(error), key=key, cause=error)
        return StorageError(str(error), key=key, cause=error)
