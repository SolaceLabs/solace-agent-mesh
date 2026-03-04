"""Factory for creating object storage clients based on configuration."""

import logging
import os

from .base import ObjectStorageClient

log = logging.getLogger(__name__)


def create_storage_client(
    bucket_name: str,
    storage_type: str | None = None,
) -> ObjectStorageClient:
    """Create an ObjectStorageClient for the given bucket.

    Backend type and credentials are read from environment variables.
    The caller is responsible for supplying the bucket/container name,
    which keeps the factory decoupled from any specific use case.

    Args:
        bucket_name: Bucket (S3/GCS) or container (Azure) name. Required.
        storage_type: Override backend type. Reads OBJECT_STORAGE_TYPE env var if None. Defaults to "s3".

    Returns:
        Configured ObjectStorageClient instance.

    Raises:
        ValueError: If storage_type is unsupported.
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


def _create_s3_client(bucket_name: str) -> ObjectStorageClient:
    from .s3_client import S3StorageClient

    return S3StorageClient(
        bucket_name=bucket_name,
        region=os.getenv("S3_REGION", "us-east-1"),
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _create_gcs_client(bucket_name: str) -> ObjectStorageClient:
    from .gcs_client import GcsStorageClient

    return GcsStorageClient(
        bucket_name=bucket_name,
        project=os.getenv("GCS_PROJECT"),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )


def _create_azure_client(bucket_name: str) -> ObjectStorageClient:
    from .azure_client import AzureBlobStorageClient

    return AzureBlobStorageClient(
        container_name=bucket_name,
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
        account_key=os.getenv("AZURE_STORAGE_ACCOUNT_KEY"),
    )
