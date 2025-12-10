"""Response DTOs for app storage endpoints."""

from typing import Any, List

from pydantic import BaseModel, Field


class StorageValueResponse(BaseModel):
    """Response containing a storage value."""

    key: str
    value: Any
    app_id: str = Field(..., alias="appId")

    class Config:
        populate_by_name = True


class StorageKeysResponse(BaseModel):
    """Response containing list of storage keys."""

    keys: List[str]
    app_id: str = Field(..., alias="appId")

    class Config:
        populate_by_name = True


class StorageDeleteResponse(BaseModel):
    """Response after deleting a storage key."""

    success: bool
    key: str
