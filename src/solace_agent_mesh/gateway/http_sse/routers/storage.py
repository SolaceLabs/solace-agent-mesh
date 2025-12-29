"""
FastAPI router for app-scoped key-value storage.

This router provides persistent storage for SAM apps running in iframes.
Each app gets its own isolated key-value namespace, accessible via the SAM SDK.

Storage is persisted to the database and survives server restarts.

Storage use cases:
- User preferences (theme, layout, settings)
- Draft data (form inputs, unsaved changes)
- Cache (API responses, computed results)
- Session data (current state, filters, selections)
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..dependencies import get_db_optional
from ..shared.auth_utils import get_current_user
from ..repository.app_storage_repository import AppStorageRepository
from .dto.requests.storage_requests import SetStorageRequest
from .dto.responses.storage_responses import (
    StorageDeleteResponse,
    StorageKeysResponse,
    StorageValueResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()

# Fallback in-memory storage when database is not available
# Structure: {user_id: {app_id: {key: value}}}
_memory_storage: Dict[str, Dict[str, Dict[str, Any]]] = {}

# Repository for database operations
_storage_repo = AppStorageRepository()


def _get_memory_storage(user_id: str, app_id: str) -> Dict[str, Any]:
    """Get or create in-memory storage namespace for user+app."""
    if user_id not in _memory_storage:
        _memory_storage[user_id] = {}
    if app_id not in _memory_storage[user_id]:
        _memory_storage[user_id][app_id] = {}
    return _memory_storage[user_id][app_id]


@router.post("/apps/{app_id}/storage", response_model=StorageValueResponse)
async def set_storage_value(
    app_id: str,
    request: SetStorageRequest,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Set a storage value for the app.

    Values are JSON-serializable objects (strings, numbers, booleans, objects, arrays).
    Storage is scoped to user+app, so different users see different data.
    """
    user_id = user.get("id")
    log.info(f"[Storage] POST set_storage_value: user={user_id} app={app_id} key={request.key}")

    # Validate value is JSON-serializable
    try:
        json.dumps(request.value)
    except (TypeError, ValueError) as e:
        log.warning(f"[Storage] Invalid value for key={request.key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be JSON-serializable: {str(e)}",
        )

    if db:
        # Use database storage
        log.debug(f"[Storage] Using database storage for key={request.key}")
        _storage_repo.set(db, user_id, app_id, request.key, request.value)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage for key={request.key}")
        storage = _get_memory_storage(user_id, app_id)
        storage[request.key] = request.value

    log.info(f"[Storage] Successfully stored key={request.key} for app={app_id}")

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
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Set a storage value for the app (RESTful PUT endpoint).

    This endpoint supports the SAM SDK's PUT /apps/{app_id}/storage/{key} pattern.
    The value is passed in the request body as {"value": <json-value>}.
    """
    user_id = user.get("id")
    log.info(f"[Storage] PUT set_storage_value: user={user_id} app={app_id} key={key}")

    # Extract value from request body
    if "value" not in request:
        log.warning(f"[Storage] Missing 'value' field in request for key={key}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must contain 'value' field",
        )

    value = request["value"]

    # Validate value is JSON-serializable
    try:
        json.dumps(value)
    except (TypeError, ValueError) as e:
        log.warning(f"[Storage] Invalid value for key={key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be JSON-serializable: {str(e)}",
        )

    if db:
        # Use database storage
        log.debug(f"[Storage] Using database storage for key={key}")
        _storage_repo.set(db, user_id, app_id, key, value)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage for key={key}")
        storage = _get_memory_storage(user_id, app_id)
        storage[key] = value

    log.info(f"[Storage] Successfully stored key={key} for app={app_id}")

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
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Get a storage value by key.

    Returns 404 if key doesn't exist.
    """
    user_id = user.get("id")
    log.info(f"[Storage] GET get_storage_value: user={user_id} app={app_id} key={key}")

    value = None

    if db:
        # Use database storage
        log.debug(f"[Storage] Querying database for key={key}")
        value = _storage_repo.get(db, user_id, app_id, key)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage for key={key}")
        storage = _get_memory_storage(user_id, app_id)
        value = storage.get(key)

    if value is None:
        log.info(f"[Storage] Key not found: user={user_id} app={app_id} key={key}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage key '{key}' not found",
        )

    log.info(f"[Storage] Found key={key} for app={app_id}")

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
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Delete a storage value by key.

    Returns success even if key doesn't exist (idempotent).
    """
    user_id = user.get("id")
    log.info(f"[Storage] DELETE delete_storage_value: user={user_id} app={app_id} key={key}")

    if db:
        # Use database storage
        log.debug(f"[Storage] Deleting from database key={key}")
        _storage_repo.delete(db, user_id, app_id, key)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage for key={key}")
        storage = _get_memory_storage(user_id, app_id)
        if key in storage:
            del storage[key]

    log.info(f"[Storage] Deleted key={key} from app={app_id}")

    return StorageDeleteResponse(
        success=True,
        key=key,
    )


@router.get("/apps/{app_id}/storage", response_model=StorageKeysResponse)
async def list_storage_keys(
    app_id: str,
    prefix: Optional[str] = Query(None, max_length=255),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    List all storage keys for the app, optionally filtered by prefix.

    Example prefixes:
    - "user.": List user-related keys
    - "cache.": List cached values
    - "draft.": List draft data
    """
    user_id = user.get("id")
    log.info(f"[Storage] GET list_storage_keys: user={user_id} app={app_id} prefix={prefix}")

    keys = []

    if db:
        # Use database storage
        log.debug(f"[Storage] Listing keys from database")
        keys = _storage_repo.list_keys(db, user_id, app_id, prefix)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage")
        storage = _get_memory_storage(user_id, app_id)
        keys = list(storage.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]

    log.info(f"[Storage] Found {len(keys)} keys in app={app_id}")

    return StorageKeysResponse(
        keys=keys,
        appId=app_id,
    )


@router.delete("/apps/{app_id}/storage")
async def clear_storage(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """
    Clear all storage for the app.

    This is a destructive operation - use with caution.
    """
    user_id = user.get("id")
    log.info(f"[Storage] DELETE clear_storage: user={user_id} app={app_id}")

    key_count = 0

    if db:
        # Use database storage
        log.debug(f"[Storage] Clearing all keys from database")
        key_count = _storage_repo.clear(db, user_id, app_id)
    else:
        # Fallback to in-memory storage
        log.warning(f"[Storage] No database available, using in-memory storage")
        storage = _get_memory_storage(user_id, app_id)
        key_count = len(storage)
        storage.clear()

    log.info(f"[Storage] Cleared {key_count} keys from app={app_id}")

    return {"success": True, "cleared_keys": key_count}
