"""Request DTOs for app storage endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SetStorageRequest(BaseModel):
    """Request to set a storage value."""

    key: str = Field(..., min_length=1, max_length=255)
    value: Any = Field(...)


class DeleteStorageRequest(BaseModel):
    """Request to delete a storage key."""

    key: str = Field(..., min_length=1, max_length=255)


class ListStorageKeysRequest(BaseModel):
    """Request to list storage keys with optional prefix."""

    prefix: Optional[str] = Field(None, max_length=255)
