"""Common exception hierarchy for object storage backends."""


class StorageError(Exception):
    """Base exception for all storage operations."""

    def __init__(self, message: str, key: str | None = None, cause: Exception | None = None):
        self.key = key
        self.cause = cause
        super().__init__(message)


class StorageNotFoundError(StorageError):
    """Raised when a requested key does not exist."""


class StoragePermissionError(StorageError):
    """Raised when credentials are invalid or access is denied."""


class StorageConnectionError(StorageError):
    """Raised when the storage backend is unreachable."""
