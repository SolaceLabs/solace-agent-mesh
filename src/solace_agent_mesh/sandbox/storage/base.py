"""Read-only storage abstraction for tool sync."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SyncObjectMeta:
    """Metadata for a remote object used for change detection."""

    key: str
    etag: str
    size: int


class ToolSyncStorageClient(ABC):
    """Minimal read-only interface for syncing tool files from object storage."""

    @abstractmethod
    def list_objects(self, prefix: str) -> list[SyncObjectMeta]:
        """List all objects under *prefix*, returning metadata for each."""

    @abstractmethod
    def download_object(self, key: str) -> bytes:
        """Download a single object and return its content as bytes."""
