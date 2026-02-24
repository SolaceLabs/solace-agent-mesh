"""Abstract base class for object storage backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StorageObject:
    """Wrapper returned by get_object that carries content alongside metadata."""

    content: bytes
    content_type: str = "application/octet-stream"
    metadata: dict[str, str] = field(default_factory=dict)


class ObjectStorageClient(ABC):
    """Backend-agnostic interface for blob storage operations."""

    @abstractmethod
    def put_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload content and return the key."""

    @abstractmethod
    def get_object(self, key: str) -> StorageObject:
        """Download content by key. Raises StorageNotFoundError if missing."""

    @abstractmethod
    def delete_object(self, key: str) -> None:
        """Delete a single object. No-op if the key doesn't exist."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a prefix. Returns count of deleted objects."""

    @abstractmethod
    def get_public_url(self, key: str) -> str:
        """Return the public URL for the given key."""
