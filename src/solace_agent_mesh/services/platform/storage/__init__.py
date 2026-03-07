"""Generic object storage abstraction supporting S3, GCS, and Azure Blob Storage."""

from .base import ObjectStorageClient, StorageObject
from .exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
)
from .factory import create_storage_client

__all__ = [
    "ObjectStorageClient",
    "StorageObject",
    "StorageError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "StorageConnectionError",
    "create_storage_client",
]
