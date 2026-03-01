"""Factory for creating sync storage clients based on configuration."""

import os
import logging

from .base import ToolSyncStorageClient

log = logging.getLogger(__name__)


def create_sync_client(
    storage_type: str | None = None,
    bucket_name: str | None = None,
) -> ToolSyncStorageClient:
    """Create a ToolSyncStorageClient based on environment or explicit config.

    Uses the same env vars as the enterprise ObjectStorageClient factory so
    Helm sets them once for both platform service and STR pods.

    Args:
        storage_type: Override backend type. Reads OBJECT_STORAGE_TYPE if None. Defaults to "s3".
        bucket_name: Override bucket/container name. Falls back to backend-specific env vars.

    Raises:
        ValueError: If required configuration is missing or storage_type is unsupported.
        ImportError: If the optional dependency for the requested backend is not installed.
    """
    backend = (storage_type or os.getenv("OBJECT_STORAGE_TYPE", "s3")).lower()

    if backend == "s3":
        return _create_s3_client(bucket_name)
    if backend == "gcs":
        return _create_gcs_client(bucket_name)
    if backend == "azure":
        return _create_azure_client(bucket_name)

    raise ValueError(f"Unsupported storage type: {backend!r}. Supported: s3, gcs, azure")


def _create_s3_client(bucket_name: str | None) -> ToolSyncStorageClient:
    from .s3_sync_client import S3SyncClient

    resolved_bucket = bucket_name or os.getenv("OBJECT_STORAGE_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME")
    if not resolved_bucket:
        raise ValueError("Bucket name required: set OBJECT_STORAGE_BUCKET_NAME, S3_BUCKET_NAME, or pass bucket_name")

    return S3SyncClient(
        bucket_name=resolved_bucket,
        region=os.getenv("S3_REGION", "us-east-1"),
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
    )


def _create_gcs_client(bucket_name: str | None) -> ToolSyncStorageClient:
    from .gcs_sync_client import GcsSyncClient

    resolved_bucket = bucket_name or os.getenv("OBJECT_STORAGE_BUCKET_NAME") or os.getenv("GCS_BUCKET_NAME")
    if not resolved_bucket:
        raise ValueError("Bucket name required: set OBJECT_STORAGE_BUCKET_NAME, GCS_BUCKET_NAME, or pass bucket_name")

    return GcsSyncClient(
        bucket_name=resolved_bucket,
        project=os.getenv("GCS_PROJECT"),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )


def _create_azure_client(bucket_name: str | None) -> ToolSyncStorageClient:
    from .azure_sync_client import AzureSyncClient

    resolved_container = bucket_name or os.getenv("OBJECT_STORAGE_BUCKET_NAME") or os.getenv("AZURE_CONTAINER_NAME")
    if not resolved_container:
        raise ValueError(
            "Container name required: set OBJECT_STORAGE_BUCKET_NAME, AZURE_CONTAINER_NAME, or pass bucket_name"
        )

    return AzureSyncClient(
        container_name=resolved_container,
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
        account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
    )
