"""
FastAPI router for app-scoped key-value storage.

This router provides persistent storage for SAM apps running in iframes.
Each app gets its own isolated key-value namespace, accessible via the SAM SDK.

Storage use cases:
- User preferences (theme, layout, settings)
- Draft data (form inputs, unsaved changes)
- Cache (API responses, computed results)
- Session data (current state, filters, selections)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_db_optional
from ..shared.auth_utils import get_current_user
from .dto.requests.storage_requests import SetStorageRequest
from .dto.responses.storage_responses import (
    StorageDeleteResponse,
    StorageKeysResponse,
    StorageValueResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage (replace with database in production)
# Structure: {user_id: {app_id: {key: value}}}
_storage: Dict[str, Dict[str, Dict[str, Any]]] = {}


def get_storage_path(user_id: str, app_id: str) -> tuple:
    """Get or create storage namespace for user+app."""
    if user_id not in _storage:
        _storage[user_id] = {}
    if app_id not in _storage[user_id]:
        _storage[user_id][app_id] = {}
    return user_id, app_id


@router.post("/apps/{app_id}/storage", response_model=StorageValueResponse)
async def set_storage_value(
    app_id: str,
    request: SetStorageRequest,
    user: dict = Depends(get_current_user),
):
    """
    Set a storage value for the app.

    Values are JSON-serializable objects (strings, numbers, booleans, objects, arrays).
    Storage is scoped to user+app, so different users see different data.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} setting storage key '{request.key}' in app {app_id}")

    uid, aid = get_storage_path(user_id, app_id)

    # Validate value is JSON-serializable
    try:
        json.dumps(request.value)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be JSON-serializable: {str(e)}",
        )

    # Store value
    _storage[uid][aid][request.key] = request.value

    log.info(f"Stored key '{request.key}' for app {app_id}")

    return StorageValueResponse(
        key=request.key,
        value=request.value,
        appId=app_id,
    )


@router.put("/apps/{app_id}/storage/{key}", response_model=StorageValueResponse)
async def set_storage_value_restful(
    app_id: str,
    key: str,
    request: dict,
    user: dict = Depends(get_current_user),
):
    """
    Set a storage value for the app (RESTful PUT endpoint).

    This endpoint supports the SAM SDK's PUT /apps/{app_id}/storage/{key} pattern.
    The value is passed in the request body as {"value": <json-value>}.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} setting storage key '{key}' in app {app_id} (PUT)")

    uid, aid = get_storage_path(user_id, app_id)

    # Extract value from request body
    if "value" not in request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain 'value' field",
        )

    value = request["value"]

    # Validate value is JSON-serializable
    try:
        json.dumps(value)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be JSON-serializable: {str(e)}",
        )

    # Store value
    _storage[uid][aid][key] = value

    log.info(f"Stored key '{key}' for app {app_id}")

    return StorageValueResponse(
        key=key,
        value=value,
        appId=app_id,
    )


@router.get("/apps/{app_id}/storage/{key}", response_model=StorageValueResponse)
async def get_storage_value(
    app_id: str,
    key: str,
    user: dict = Depends(get_current_user),
):
    """
    Get a storage value by key.

    Returns 404 if key doesn't exist.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} getting storage key '{key}' from app {app_id}")

    uid, aid = get_storage_path(user_id, app_id)

    if key not in _storage[uid][aid]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage key '{key}' not found",
        )

    value = _storage[uid][aid][key]

    return StorageValueResponse(
        key=key,
        value=value,
        appId=app_id,
    )


@router.delete("/apps/{app_id}/storage/{key}", response_model=StorageDeleteResponse)
async def delete_storage_value(
    app_id: str,
    key: str,
    user: dict = Depends(get_current_user),
):
    """
    Delete a storage value by key.

    Returns success even if key doesn't exist (idempotent).
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deleting storage key '{key}' from app {app_id}")

    uid, aid = get_storage_path(user_id, app_id)

    if key in _storage[uid][aid]:
        del _storage[uid][aid][key]
        log.info(f"Deleted key '{key}' from app {app_id}")
    else:
        log.info(f"Key '{key}' not found in app {app_id} (already deleted)")

    return StorageDeleteResponse(
        success=True,
        key=key,
    )


@router.get("/apps/{app_id}/storage", response_model=StorageKeysResponse)
async def list_storage_keys(
    app_id: str,
    prefix: Optional[str] = Query(None, max_length=255),
    user: dict = Depends(get_current_user),
):
    """
    List all storage keys for the app, optionally filtered by prefix.

    Example prefixes:
    - "user.": List user-related keys
    - "cache.": List cached values
    - "draft.": List draft data
    """
    user_id = user.get("id")
    log.info(f"User {user_id} listing storage keys in app {app_id} (prefix={prefix})")

    uid, aid = get_storage_path(user_id, app_id)

    keys = list(_storage[uid][aid].keys())

    # Filter by prefix if provided
    if prefix:
        keys = [k for k in keys if k.startswith(prefix)]

    log.info(f"Found {len(keys)} keys in app {app_id}")

    return StorageKeysResponse(
        keys=keys,
        appId=app_id,
    )


@router.delete("/apps/{app_id}/storage")
async def clear_storage(
    app_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Clear all storage for the app.

    This is a destructive operation - use with caution.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} clearing all storage for app {app_id}")

    uid, aid = get_storage_path(user_id, app_id)

    key_count = len(_storage[uid][aid])
    _storage[uid][aid].clear()

    log.info(f"Cleared {key_count} keys from app {app_id}")

    return {"success": True, "cleared_keys": key_count}
