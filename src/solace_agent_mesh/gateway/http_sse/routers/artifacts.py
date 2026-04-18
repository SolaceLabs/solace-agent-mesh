"""
FastAPI router for managing session-specific artifacts via REST endpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
    Request as FastAPIRequest,
)
from pydantic import BaseModel, Field
from fastapi.responses import Response, StreamingResponse

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


import io
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlparse

from ....common.a2a.types import ArtifactInfo
from ....common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_recursively_in_string,
)
from ....common.utils.embeds.types import ResolutionMode
from ....common.utils.mime_helpers import is_text_based_mime_type, resolve_mime_type
from ....common.utils.templates import resolve_template_blocks_in_string
from ..dependencies import (
    get_project_service_optional,
    ValidatedUserConfig,
    get_sac_component,
    get_session_validator,
    get_shared_artifact_service,
    get_user_id,
    get_session_manager,
    get_session_business_service_optional,
    get_db,
    get_db_optional,
)
from ..services.project_service import ProjectService


from ..session_manager import SessionManager
from ..services.session_service import SessionService
from sqlalchemy.orm import Session
from ....shared.api.pagination import PaginationParams

from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    get_artifact_info_list_fast,
    load_artifact_content_or_metadata,
    process_artifact_upload,
)

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)

LOAD_FILE_CHUNK_SIZE = 1024 * 1024  # 1MB chunks

class ArtifactUploadResponse(BaseModel):
    """Response model for artifact upload with camelCase fields."""

    uri: str
    session_id: str = Field(..., alias="sessionId")
    filename: str
    size: int
    mime_type: str = Field(..., alias="mimeType")
    metadata: dict[str, Any]
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


router = APIRouter()


# ── Scheduled session ID naming convention ──────────────────────────
#
# Per-execution sessions:  "scheduled_{execution_id}"   — used as the chat session
# Stable storage sessions: "scheduled_task_{task_id}"   — used as the ADK context_id
#                                                         where agents store artifacts
#
# _is_execution_session distinguishes the two by checking for the "scheduled_"
# prefix while excluding the "scheduled_task_" prefix.
# ─────────────────────────────────────────────────────────────────────


def _is_execution_session(session_id: str | None) -> bool:
    """Return True if session_id is a per-execution scheduled session (not task-level)."""
    return bool(
        session_id
        and session_id.startswith("scheduled_")
        and not session_id.startswith("scheduled_task_")
    )


def _get_execution_from_db(session_id: str, caller: str):
    """Look up the scheduled execution record for an execution session.

    Returns the execution ORM object, or ``None`` if the session is not an
    execution session or the lookup fails.
    """
    if not _is_execution_session(session_id):
        return None

    try:
        from ..repository.scheduled_task_repository import ScheduledTaskRepository
        from ..dependencies import SessionLocal

        if SessionLocal is None:
            return None

        repo = ScheduledTaskRepository()
        with SessionLocal() as db:
            return repo.find_execution_by_session_id(db, session_id)
    except Exception as e:
        log.warning("[%s] Failed to look up execution for %s: %s", caller, session_id, e)
        return None


def _resolve_execution_context(session_id: str) -> tuple[str | None, dict[str, int | None] | None]:
    """Resolve both the stable storage session and artifact version info in a single DB lookup.

    For per-execution scheduled sessions (``scheduled_{execution_id}``), this
    fetches the execution record once and derives:
    1. The stable storage session (``scheduled_task_{task_id}``) where artifacts live.
    2. The artifact name → pinned version mapping from the execution's manifest.

    Returns:
        (stable_session_id, artifact_info) — either or both may be ``None``
        if the session is not an execution session or the lookup fails.
    """
    execution = _get_execution_from_db(session_id, "_resolve_execution_context")
    if not execution:
        return None, None

    stable_id = f"scheduled_task_{execution.scheduled_task_id}"
    log.debug("[_resolve_execution_context] Mapped %s -> %s", session_id, stable_id)

    artifact_info: dict[str, int | None] | None = None
    if execution.artifacts:
        info: dict[str, int | None] = {}
        for art in execution.artifacts:
            if isinstance(art, dict):
                name = art.get("name") or art.get("filename")
                if name:
                    info[name] = art.get("version")
        artifact_info = info if info else None

    return stable_id, artifact_info


def _user_owns_execution_session(session_id: str, user_id: str) -> bool:
    """Return True if ``user_id`` owns the scheduled task behind ``session_id``.

    Used to gate artifact access for per-execution scheduled sessions so a
    user who obtains another user's execution/session id cannot fetch their
    artifacts.
    """
    execution = _get_execution_from_db(session_id, "_user_owns_execution_session")
    if not execution:
        return False

    try:
        from ..repository.scheduled_task_repository import ScheduledTaskRepository
        from ..dependencies import SessionLocal

        if SessionLocal is None:
            return False

        repo = ScheduledTaskRepository()
        with SessionLocal() as db:
            task = repo.find_by_id(db, execution.scheduled_task_id)
    except Exception as e:
        log.warning("[_user_owns_execution_session] lookup failed for %s: %s", session_id, e)
        return False

    if not task:
        return False
    return task.created_by == user_id


def _resolve_storage_context(
    session_id: str,
    project_id: str | None,
    user_id: str,
    validate_session: Callable[[str, str], bool],
    project_service: ProjectService | None,
    log_prefix: str,
) -> tuple[str, str, str, dict[str, int | None] | None]:
    """
    Resolve storage context from session or project parameters.

    Returns:
        tuple: (storage_user_id, storage_session_id, context_type, execution_artifact_info)
               execution_artifact_info is non-None only for per-execution scheduled sessions.

    Raises:
        HTTPException: If no valid context found
    """
    # Priority 1: Session context
    if session_id and session_id.strip() and session_id not in ["null", "undefined"]:
        if not validate_session(session_id, user_id):
            log.warning("%s Session validation failed", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied.",
            )

        # For scheduled execution sessions, resolve to the stable task-level
        # session where artifacts are actually stored by the agent.
        # A single DB lookup returns both the storage session and artifact info.
        stable_session, artifact_info = _resolve_execution_context(session_id)
        if stable_session:
            # Ownership check: ensure the requesting user owns the scheduled
            # task that produced these artifacts. Return 404 (not 403) to avoid
            # confirming existence to unauthorized users.
            if not _user_owns_execution_session(session_id, user_id):
                log.warning(
                    "%s User %s not authorized for scheduled session %s",
                    log_prefix, user_id, session_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or access denied.",
                )
            log.info(
                "%s Resolved scheduled storage session: %s -> %s",
                log_prefix, session_id, stable_session,
            )
            return user_id, stable_session, "session", artifact_info

        return user_id, session_id, "session", None

    # Priority 2: Project context (only if persistence is enabled)
    elif project_id and project_id.strip() and project_id not in ["null", "undefined"]:
        if project_service is None:
            log.warning("%s Project context requested but persistence not enabled", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Project context requires database configuration.",
            )

        from ....gateway.http_sse.dependencies import SessionLocal

        if SessionLocal is None:
            log.warning("%s Project context requested but database not configured", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Project context requires database configuration.",
            )

        db = SessionLocal()
        try:
            project = project_service.get_project(db, project_id, user_id)
            if not project:
                log.warning("%s Project not found or access denied", log_prefix)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or access denied.",
                )
            return project.user_id, f"project-{project_id}", "project", None
        except HTTPException:
            raise
        except Exception as e:
            log.error("%s Error resolving project context: %s", log_prefix, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resolve project context"
            )
        finally:
            db.close()

    # No valid context
    log.warning("%s No valid context found", log_prefix)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No valid context provided.",
    )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=ArtifactUploadResponse,
    summary="Upload Artifact (Body-Based Session Management)",
    description="Uploads file with sessionId and filename in request body. Creates session if sessionId is null/empty.",
)
async def upload_artifact_with_session(
    request: FastAPIRequest,
    upload_file: UploadFile = File(..., description="The file content to upload"),
    sessionId: str | None = Form(
        None,
        description="Session ID (null/empty to create new session)",
        alias="sessionId",
    ),
    filename: str = Form(..., description="The name of the artifact to create/update"),
    metadata_json: str | None = Form(
        None, description="JSON string of artifact metadata (e.g., description, source)"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:create"])),
    session_manager: SessionManager = Depends(get_session_manager),
    session_service: SessionService | None = Depends(
        get_session_business_service_optional
    ),
    db: Session | None = Depends(get_db_optional),
):
    """
    Uploads a file to create a new version of the specified artifact.

    Key features:
    - Session ID and filename provided in request body (not URL)
    - Automatically creates new session if session_id is null/empty
    - Consistent with chat API patterns
    """
    log_prefix = f"[POST /artifacts/upload] User {user_id}: "

    # Handle session creation logic (matching chat API pattern)
    effective_session_id = None
    is_new_session = False  # Track if we created a new session

    # Use session ID from request body (matching sessionId pattern in session APIs)
    if sessionId and sessionId.strip():
        effective_session_id = sessionId.strip()
        log.info("%sUsing existing session: %s", log_prefix, effective_session_id)
    else:
        # Create new session when no sessionId provided (like chat does for new conversations)
        effective_session_id = session_manager.create_new_session_id(request)
        is_new_session = True  # Mark that we created this session
        log.info(
            "%sCreated new session for file upload: %s",
            log_prefix,
            effective_session_id,
        )

        # Persist session in database if persistence is available (matching chat pattern)
        if session_service and db:
            try:
                session_service.create_session(
                    db=db,
                    user_id=user_id,
                    session_id=effective_session_id,
                    agent_id=None,  # Will be determined when first message is sent
                    name=None,  # Will be set when first message is sent
                )
                db.commit()
                log.info(
                    "%sSession created and committed to database: %s",
                    log_prefix,
                    effective_session_id,
                )
            except Exception as session_error:
                db.rollback()
                log.warning(
                    "%sSession persistence failed, continuing with in-memory session: %s",
                    log_prefix,
                    session_error,
                )
        else:
            log.debug(
                "%sNo persistence available - using in-memory session: %s",
                log_prefix,
                effective_session_id,
            )

    # Validate inputs
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    if not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload is required.",
        )

    # Validate artifact service availability
    if not artifact_service:
        log.error("%sArtifact service is not configured.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    # Validate session (now that we have an effective_session_id)
    # Skip validation if we just created the session to avoid race conditions
    if not is_new_session and not validate_session(effective_session_id, user_id):
        log.warning(
            "%sSession validation failed for session: %s",
            log_prefix,
            effective_session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid session or insufficient permissions.",
        )

    log.info(
        "%sUploading file '%s' to session '%s'",
        log_prefix,
        filename.strip(),
        effective_session_id,
    )

    try:
        # ===== VALIDATE FILE SIZE BEFORE READING =====
        max_upload_size = component.get_config("gateway_max_upload_size_bytes")
        
        # Check Content-Length header first (if available)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                file_size = int(content_length)
                
                if file_size > max_upload_size:
                    error_msg = (
                        f"File upload rejected: size {file_size:,} bytes "
                        f"exceeds maximum {max_upload_size:,} bytes "
                        f"({file_size / (1024*1024):.2f} MB > {max_upload_size / (1024*1024):.2f} MB)"
                    )
                    log.warning("%s %s", log_prefix, error_msg)
                    
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=error_msg  # Use string instead of dict
                    )
            except ValueError:
                log.warning("%s Invalid Content-Length header: %s", log_prefix, content_length)
        
        # Validate file size by streaming through WITHOUT accumulating chunks in memory
        chunk_size = LOAD_FILE_CHUNK_SIZE
        total_bytes_read = 0

        try:
            # Step 1: Validate size by reading chunks (discard data, just count bytes)
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break  # End of file

                total_bytes_read += len(chunk)

                # Validate size during reading (fail fast)
                if total_bytes_read > max_upload_size:
                    error_msg = (
                        f"File '{upload_file.filename}' rejected: size exceeds maximum {max_upload_size:,} bytes "
                        f"(read {total_bytes_read:,} bytes so far, "
                        f"{total_bytes_read / (1024*1024):.2f} MB > {max_upload_size / (1024*1024):.2f} MB)"
                    )
                    log.warning("%s %s", log_prefix, error_msg)

                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=error_msg
                    )

            # Step 2: Size is valid - reset to beginning
            await upload_file.seek(0)

            # Step 3: Read all content at once
            content_bytes = await upload_file.read()

            log.debug(
                "%s File validated (%d bytes) and loaded into memory",
                log_prefix,
                total_bytes_read
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions (size limit exceeded)
            raise
        except Exception as read_error:
            log.exception("%s Error reading uploaded file: %s", log_prefix, read_error)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read uploaded file"
            )

        mime_type = resolve_mime_type(filename, upload_file.content_type)
        filename_clean = filename.strip()

        log.debug(
            "%sProcessing file: %s (%d bytes, %s)",
            log_prefix,
            filename_clean,
            len(content_bytes),
            mime_type,
        )

        # Use the common upload helper
        upload_result = await process_artifact_upload(
            artifact_service=artifact_service,
            component=component,
            user_id=user_id,
            session_id=effective_session_id,
            filename=filename_clean,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_json=metadata_json,
            log_prefix=log_prefix,
        )

        if upload_result["status"] != "success":
            error_msg = upload_result.get("message", "Failed to upload artifact")
            error_type = upload_result.get("error", "unknown")

            if error_type in ["invalid_filename", "empty_file"]:
                status_code = status.HTTP_400_BAD_REQUEST
            elif error_type == "file_too_large":
                status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            log.error("%s%s", log_prefix, error_msg)
            raise HTTPException(status_code=status_code, detail=error_msg)

        artifact_uri = upload_result["artifact_uri"]
        saved_version = upload_result["version"]

        log.info(
            "%sArtifact stored successfully: %s (%d bytes), version: %s",
            log_prefix,
            artifact_uri,
            len(content_bytes),
            saved_version,
        )

        # Get metadata from upload result (it was already parsed and validated)
        metadata_dict = {}
        if metadata_json and metadata_json.strip():
            try:
                metadata_dict = json.loads(metadata_json.strip())
                if not isinstance(metadata_dict, dict):
                    metadata_dict = {}
            except json.JSONDecodeError:
                metadata_dict = {}

        # Invalidate the cached artifact list so the next page view reflects this upload
        _artifact_list_cache.invalidate(user_id)

        # Return standardized response using Pydantic model (ensures camelCase conversion)
        return ArtifactUploadResponse(
            uri=artifact_uri,
            session_id=effective_session_id,  # Will be returned as "sessionId" due to alias
            filename=filename_clean,
            size=len(content_bytes),
            mime_type=mime_type,  # Will be returned as "mimeType" due to alias
            metadata=metadata_dict,
            created_at=datetime.now(
                timezone.utc
            ).isoformat(),  # Will be returned as "createdAt" due to alias
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        log.exception("%sUnexpected error storing artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store artifact due to an internal error.",
        )
    finally:
        # Ensure file is properly closed
        try:
            await upload_file.close()
        except Exception as close_error:
            log.warning("%sError closing upload file: %s", log_prefix, close_error)


# ============================================================================
# BULK ARTIFACTS ENDPOINT
# This endpoint MUST be defined BEFORE any /{session_id} routes to avoid
# FastAPI matching "/all" as a session_id parameter.
# ============================================================================

class ArtifactWithContext(BaseModel):
    """Artifact info with session/project context for bulk listing."""
    
    # Core artifact fields from ArtifactInfo
    filename: str
    size: int
    mime_type: Optional[str] = Field(None, alias="mimeType")
    last_modified: Optional[str] = Field(None, alias="lastModified")  # ISO date string
    uri: Optional[str] = None
    
    # Context fields
    session_id: str = Field(..., alias="sessionId")
    session_name: Optional[str] = Field(None, alias="sessionName")
    project_id: Optional[str] = Field(None, alias="projectId")
    project_name: Optional[str] = Field(None, alias="projectName")
    
    # Source field for origin badges (upload, generated, project)
    source: Optional[str] = None
    
    # Tags for categorization (e.g., ["__working"] to mark as internal)
    tags: Optional[list[str]] = None
    
    model_config = {"populate_by_name": True}


class BulkArtifactsResponse(BaseModel):
    """Response model for bulk artifacts listing."""

    artifacts: list[ArtifactWithContext]
    total_count: int = Field(..., alias="totalCount")
    total_count_estimated: bool = Field(False, alias="totalCountEstimated")
    has_more: bool = Field(False, alias="hasMore")
    next_page: Optional[int] = Field(None, alias="nextPage")

    model_config = {"populate_by_name": True}


# Semaphore to limit concurrent artifact fetches (prevent overwhelming the artifact service)
_ARTIFACT_FETCH_SEMAPHORE = asyncio.Semaphore(10)

# Default TTL for the per-user artifact list cache (seconds)
_ARTIFACT_CACHE_TTL_SECONDS = 30
_ARTIFACT_CACHE_MAX_USERS = 200


class _ArtifactListCache:
    """Short-lived per-user cache for the full deduplicated/sorted artifact list.

    Prevents re-fetching every source on each "Load More" page request. The
    cache is keyed by ``user_id`` and entries expire after *ttl* seconds.

    Bounded to *max_size* entries with LRU eviction to prevent unbounded
    memory growth in multi-tenant deployments.  Per-user asyncio locks
    prevent concurrent requests from duplicating fetch work (TOCTOU).
    """

    def __init__(
        self,
        ttl: int = _ARTIFACT_CACHE_TTL_SECONDS,
        max_size: int = _ARTIFACT_CACHE_MAX_USERS,
    ):
        self._ttl = ttl
        self._max_size = max_size
        # Each entry: (timestamp, artifacts, sources_processed, total_sources)
        self._store: dict[str, tuple[float, list[ArtifactWithContext], int, int]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get(
        self, user_id: str
    ) -> tuple[list[ArtifactWithContext], int, int] | None:
        """Return cached ``(artifacts, sources_processed, total_sources)`` or *None*."""
        entry = self._store.get(user_id)
        if entry is None:
            return None
        ts, artifacts, sources_processed, total_sources = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[user_id]
            return None
        return artifacts, sources_processed, total_sources

    def put(
        self,
        user_id: str,
        artifacts: list[ArtifactWithContext],
        sources_processed: int = 0,
        total_sources: int = 0,
    ) -> None:
        # Evict oldest entries when at capacity
        while len(self._store) >= self._max_size and user_id not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
            self._locks.pop(oldest_key, None)
        self._store[user_id] = (time.monotonic(), artifacts, sources_processed, total_sources)

    def invalidate(self, user_id: str) -> None:
        self._store.pop(user_id, None)

    def lock_for(self, user_id: str) -> asyncio.Lock:
        """Return a per-user lock, creating one if needed.

        Also prunes orphaned locks (user has no cache entry and lock is not
        held) to prevent unbounded growth in multi-tenant deployments.
        """
        # Prune orphaned locks periodically (cheap: only iterates lock dict)
        orphaned = [
            uid for uid, lk in self._locks.items()
            if uid != user_id and uid not in self._store and not lk.locked()
        ]
        for uid in orphaned:
            del self._locks[uid]

        lock = self._locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[user_id] = lock
        return lock

    def clear(self) -> None:
        """Remove all entries (useful for testing)."""
        self._store.clear()
        self._locks.clear()


_artifact_list_cache = _ArtifactListCache()


async def _fetch_all_source_artifacts(
    source_entries: list[dict],
    fetch_fn,
    log_prefix: str,
    batch_size: int = 20,
    target_count: int = 0,
) -> tuple[list[ArtifactWithContext], int]:
    """Fetch artifacts from sources in batches to limit concurrency.

    Args:
        source_entries: List of source dicts with session/project info.
        fetch_fn: Async function to fetch artifacts for a single source.
        log_prefix: Logging prefix.
        batch_size: Number of sources to fetch in parallel per batch.
        target_count: If > 0, stop fetching once this many artifacts are
            collected (early termination). If 0, fetch all sources.

    Returns:
        Tuple of (artifacts_list, sources_processed_count).
    """
    all_artifacts: list[ArtifactWithContext] = []
    sources_processed = 0
    for i in range(0, len(source_entries), batch_size):
        # Early termination: stop if we already have enough artifacts
        if target_count > 0 and len(all_artifacts) >= target_count:
            break

        batch = source_entries[i : i + batch_size]
        fetch_tasks = [
            asyncio.create_task(fetch_fn(
                session_id=entry["session_id"],
                session_name=entry["session_name"],
                project_id=entry["project_id"],
                project_name=entry["project_name"],
                fetch_user_id=entry["fetch_user_id"],
            ))
            for entry in batch
        ]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                failed_entry = batch[idx]
                log.warning(
                    "%s Task failed for source session_id=%s project_id=%s: %s",
                    log_prefix,
                    failed_entry.get("session_id"),
                    failed_entry.get("project_id"),
                    result,
                    exc_info=result,
                )
                continue
            all_artifacts.extend(result)
        sources_processed = i + len(batch)
    return all_artifacts, sources_processed


def _deduplicate_artifacts(
    artifacts: list[ArtifactWithContext],
) -> list[ArtifactWithContext]:
    """Deduplicate artifacts, preferring project-scoped entries over session copies."""
    seen_project_artifacts: dict[tuple[str, str], ArtifactWithContext] = {}
    non_project_artifacts: list[ArtifactWithContext] = []

    for artifact in artifacts:
        if artifact.project_id:
            key = (artifact.project_id, artifact.filename)
            existing = seen_project_artifacts.get(key)
            if existing is None:
                seen_project_artifacts[key] = artifact
            elif artifact.session_id.startswith("project-") and not existing.session_id.startswith("project-"):
                seen_project_artifacts[key] = artifact
        else:
            non_project_artifacts.append(artifact)

    return list(seen_project_artifacts.values()) + non_project_artifacts


@router.get(
    "/all",
    response_model=BulkArtifactsResponse,
    summary="List All User Artifacts",
    description="Retrieves artifacts across all sessions and projects for the current user with pagination.",
)
async def list_all_artifacts(
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    session_service: SessionService | None = Depends(get_session_business_service_optional),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    db: Session | None = Depends(get_db_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
    page: int = Query(default=1, ge=1, alias="pageNumber", description="Page number (1-based)"),
    # Default must match ARTIFACTS_PAGE_SIZE in frontend hooks.ts
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize", description="Number of artifacts per page"),
    search: Optional[str] = Query(default=None, description="Search query to filter artifacts by filename, mime type, session name, or project name"),
):
    """
    Lists artifacts across all sessions and projects for the current user.
    
    Uses progressive fetching: processes sessions in small batches and stops
    once enough artifacts are collected for the requested page. This prevents
    overwhelming the artifact service with hundreds of concurrent S3 requests.
    
    When a search query is provided, early termination is disabled to ensure
    complete search results across all sessions. The cache helps avoid
    re-fetching on subsequent page requests.
    
    Pagination is session-based: each page fetches artifacts from a batch of
    sessions until the page is filled. The `nextPage` field indicates if more
    artifacts are available.
    """
    search_query = search.strip().lower() if isinstance(search, str) and search.strip() else None
    log_prefix = f"[ArtifactRouter:ListAll] User={user_id} -"
    log.info(
        "%s Request received (page=%d, page_size=%d, search=%s).",
        log_prefix, page, page_size, repr(search_query),
    )
    
    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )
    
    app_name = component.get_config("name", "A2A_WebUI_App")
    
    # Helper function to determine artifact source
    def _determine_source(filename: str, session_id: str) -> str:
        """Determine the source type of an artifact based on filename and session."""
        if session_id.startswith("project-"):
            return "project"
        return "upload"
    
    # Helper function to fetch artifacts for a session with semaphore
    async def _fetch_session_artifacts(
        session_id: str,
        session_name: Optional[str],
        project_id: Optional[str],
        project_name: Optional[str],
        fetch_user_id: str,
    ) -> list[ArtifactWithContext]:
        """Fetch artifacts for a single session, respecting the semaphore."""
        async with _ARTIFACT_FETCH_SEMAPHORE:
            try:
                artifacts = await get_artifact_info_list_fast(
                    artifact_service=artifact_service,
                    app_name=app_name,
                    user_id=fetch_user_id,
                    session_id=session_id,
                )
                
                result = []
                for artifact in artifacts:
                    if artifact.filename.endswith('.converted.txt') or artifact.filename == 'project_bm25_index.zip':
                        continue
                    
                    result.append(ArtifactWithContext(
                        filename=artifact.filename,
                        size=artifact.size,
                        mime_type=artifact.mime_type,
                        last_modified=artifact.last_modified,
                        uri=artifact.uri,
                        session_id=session_id,
                        session_name=session_name,
                        project_id=project_id,
                        project_name=project_name,
                        source=_determine_source(artifact.filename, session_id),
                        tags=artifact.tags,
                    ))
                return result
            except Exception as e:
                log.warning("%s Error fetching artifacts for session %s: %s", log_prefix, session_id, e)
                return []
    
    try:
        # ----------------------------------------------------------------
        # Step 0: Check per-user cache (avoids re-fetching all sources on
        #         every "Load More" page request within the TTL window).
        #         A per-user lock prevents concurrent requests from both
        #         missing the cache and duplicating the expensive fetch.
        # ----------------------------------------------------------------
        _was_partial_fetch = False  # Track if we did early termination
        total_sources = 0
        deduplicated_artifacts = None
        need_fetch = True

        # Skip cache for search queries — a cached partial result from a
        # non-search request would miss artifacts from unprocessed sources.
        if not search_query:
            cache_hit = _artifact_list_cache.get(user_id)
            if cache_hit is not None:
                cached_artifacts, cached_sources_processed, total_sources = cache_hit
                is_partial = cached_sources_processed < total_sources
                # Use cache only if the fetch was complete OR the cached set
                # covers the requested page.  Otherwise discard it and re-fetch
                # with a larger target so later pages aren't dead-ended.
                end_idx_needed = page * page_size
                if not is_partial or len(cached_artifacts) >= end_idx_needed:
                    deduplicated_artifacts = cached_artifacts
                    _was_partial_fetch = is_partial
                    need_fetch = False

        if need_fetch:
            async with _artifact_list_cache.lock_for(user_id):
                # Re-check after acquiring lock (another request may have populated it)
                if not search_query:
                    cache_hit = _artifact_list_cache.get(user_id)
                    if cache_hit is not None:
                        cached_artifacts, cached_sources_processed, total_sources = cache_hit
                        is_partial = cached_sources_processed < total_sources
                        end_idx_needed = page * page_size
                        if not is_partial or len(cached_artifacts) >= end_idx_needed:
                            deduplicated_artifacts = cached_artifacts
                            _was_partial_fetch = is_partial
                if deduplicated_artifacts is None:
                    # ----------------------------------------------------------------
                    # Step 1: Collect all session/project IDs (lightweight DB queries)
                    # ----------------------------------------------------------------
                    all_source_entries: list[dict] = []  # [{session_id, session_name, project_id, project_name, fetch_user_id}]

                    # Collect project entries first (they take priority in dedup)
                    if project_service and db:
                        try:
                            projects = project_service.get_user_projects(db, user_id)
                            for project in projects:
                                all_source_entries.append({
                                    "session_id": f"project-{project.id}",
                                    "session_name": None,
                                    "project_id": project.id,
                                    "project_name": project.name,
                                    "fetch_user_id": project.user_id,
                                })
                        except Exception as e:
                            log.warning("%s Error fetching projects: %s", log_prefix, e)

                    # Collect session entries
                    if session_service and db:
                        try:
                            session_page = 1
                            while True:
                                pagination = PaginationParams(page_number=session_page, page_size=100)
                                sessions_response = session_service.get_user_sessions(db, user_id, pagination)
                                for session in sessions_response.data:
                                    all_source_entries.append({
                                        "session_id": session.id,
                                        "session_name": session.name,
                                        "project_id": session.project_id,
                                        "project_name": session.project_name,
                                        "fetch_user_id": user_id,
                                    })
                                if sessions_response.meta.pagination.next_page is None:
                                    break
                                session_page += 1
                                if session_page > 100:
                                    log.warning("%s Reached safety limit of 100 pages for sessions", log_prefix)
                                    break
                        except Exception as e:
                            log.warning("%s Error fetching sessions: %s", log_prefix, e)

                    total_sources = len(all_source_entries)
                    log.info("%s Found %d total sources (sessions + projects)", log_prefix, total_sources)

                    # ----------------------------------------------------------------
                    # Step 2: Progressive fetch with early termination.
                    #         Fetch artifacts in batches and STOP once we have
                    #         enough to fill the requested page (with buffer for
                    #         dedup). This prevents fetching hundreds of sessions
                    #         from S3 when only 50 artifacts are needed.
                    #
                    #         When a search query is active, we MUST fetch all
                    #         sources to ensure complete search results (the
                    #         matching artifact could be in any session).
                    # ----------------------------------------------------------------
                    if search_query:
                        # Search requires scanning all sources
                        fetch_target = 0  # 0 = no early termination
                    else:
                        fetch_target = page * page_size + page_size  # buffer for dedup
                    all_artifacts, sources_processed = await _fetch_all_source_artifacts(
                        all_source_entries,
                        _fetch_session_artifacts,
                        log_prefix,
                        target_count=fetch_target,
                    )

                    log.info(
                        "%s Fetched %d artifacts from %d/%d sources (target=%d)",
                        log_prefix, len(all_artifacts), sources_processed,
                        total_sources, fetch_target,
                    )

                    # ----------------------------------------------------------------
                    # Step 3: Deduplicate
                    # ----------------------------------------------------------------
                    deduplicated_artifacts = _deduplicate_artifacts(all_artifacts)

                    # Sort by last_modified (newest first)
                    deduplicated_artifacts.sort(key=lambda a: a.last_modified or "", reverse=True)

                    _was_partial_fetch = sources_processed < total_sources
                    # Cache results so subsequent page requests within the
                    # TTL window avoid re-fetching.  Don't cache search
                    # results — they are always complete fetches and would
                    # overwrite a useful partial/complete non-search cache.
                    if not search_query:
                        _artifact_list_cache.put(
                            user_id, deduplicated_artifacts, sources_processed, total_sources,
                        )
                else:
                    log.info("%s Using cached artifact list (%d items)", log_prefix, len(deduplicated_artifacts))
        else:
            log.info("%s Using cached artifact list (%d items)", log_prefix, len(deduplicated_artifacts))

        # ----------------------------------------------------------------
        # Step 3.5: Apply server-side search filter (if provided)
        # ----------------------------------------------------------------
        if search_query:
            deduplicated_artifacts = [
                a for a in deduplicated_artifacts
                if search_query in (a.filename or "").lower()
                or search_query in (a.mime_type or "").lower()
                or search_query in (a.session_name or "").lower()
                or search_query in (a.project_name or "").lower()
            ]
            pre_filter = _artifact_list_cache.get(user_id)
            pre_filter_count = len(pre_filter[0]) if pre_filter else len(deduplicated_artifacts)
            log.info(
                "%s Search filter '%s' reduced artifacts from %d to %d",
                log_prefix, search_query, pre_filter_count,
                len(deduplicated_artifacts),
            )

        # ----------------------------------------------------------------
        # Step 4: Apply pagination slice
        # ----------------------------------------------------------------
        total_count = len(deduplicated_artifacts)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_artifacts = deduplicated_artifacts[start_idx:end_idx]

        # Determine if more artifacts are available:
        # - more_in_fetched: there are items beyond the current slice in what we fetched
        # - _was_partial_fetch: we used early termination and didn't process all
        #   sources, so there may be more artifacts in unprocessed sessions
        more_in_fetched = end_idx < total_count
        has_more = len(page_artifacts) > 0 and (more_in_fetched or _was_partial_fetch)
        next_page = page + 1 if has_more else None

        log.info(
            "%s Returning %d artifacts (page=%d, page_size=%d, total_deduped=%d, "
            "has_more=%s, partial_fetch=%s)",
            log_prefix, len(page_artifacts), page, page_size, total_count,
            has_more, _was_partial_fetch,
        )

        return BulkArtifactsResponse(
            artifacts=page_artifacts,
            total_count=total_count,
            total_count_estimated=_was_partial_fetch,
            has_more=has_more,
            next_page=next_page,
        )
        
    except Exception as e:
        log.exception("%s Error retrieving all artifacts: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve artifacts: {str(e)}",
        )


# ============================================================================
# SESSION-SPECIFIC ARTIFACT ENDPOINTS
# These endpoints use /{session_id} path parameters and must come AFTER /all
# ============================================================================

@router.get(
    "/{session_id}/{filename}/versions",
    response_model=list[int],
    summary="List Artifact Versions",
    description="Retrieves a list of available version numbers for a specific artifact.",
)
async def list_artifact_versions(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists the available integer versions for a given artifact filename
    associated with the specified context (session or project).
    """

    log_prefix = f"[ArtifactRouter:ListVersions:{filename}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context
    storage_user_id, storage_session_id, context_type, _ = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service not available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    if not hasattr(artifact_service, "list_versions"):
        log.warning(
            "%s Configured artifact service (%s) does not support listing versions.",
            log_prefix,
            type(artifact_service).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Version listing not supported by the configured '{type(artifact_service).__name__}' artifact service.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
        )
        log.info("%s Found versions: %s", log_prefix, versions)
        return versions
    except FileNotFoundError:
        log.warning("%s Artifact not found.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        )
    except Exception as e:
        log.exception("%s Error listing artifact versions: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list artifact versions: {str(e)}",
        )


@router.get(
    "/{session_id}",
    response_model=list[ArtifactInfo],
    summary="List Artifact Information",
    description="Retrieves detailed information for artifacts available for the specified user session.",
)
@router.get(
    "/",
    response_model=list[ArtifactInfo],
    summary="List Artifact Information",
    description="Retrieves detailed information for artifacts available for the current user session.",
)
async def list_artifacts(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to list artifacts for (or 'null' for project context)"
    ),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists detailed information (filename, size, type, modified date, uri)
    for all artifacts associated with the specified context (session or project).
    """

    log_prefix = f"[ArtifactRouter:ListInfo] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context (projects vs sessions). This allows for project artiacts
    # to be listed before a session is created.
    try:
        storage_user_id, storage_session_id, context_type, execution_artifact_info = _resolve_storage_context(
            session_id, project_id, user_id, validate_session, project_service, log_prefix
        )
    except HTTPException:
        log.info("%s No valid context found, returning empty list", log_prefix)
        return []

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s",
                log_prefix, context_type, storage_user_id, storage_session_id)

        artifact_info_list = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
        )

        # Filter out generated files (converted text files and BM25 index)
        # Users should only see original files in the UI, not internal conversion artifacts
        original_artifacts_only = [
            artifact for artifact in artifact_info_list
            if not artifact.filename.endswith('.converted.txt')
            and artifact.filename != 'project_bm25_index.zip'
        ]

        # For scheduled execution sessions, further filter to only show
        # artifacts produced by this specific execution (not all artifacts
        # accumulated across all executions of the same scheduled task).
        # The artifact info was already fetched in _resolve_storage_context.
        if execution_artifact_info is not None:
            before_count = len(original_artifacts_only)
            original_artifacts_only = [
                a for a in original_artifacts_only
                if a.filename in execution_artifact_info
            ]
            log.info(
                "%s Filtered scheduled execution artifacts: %d -> %d (execution produced: %s)",
                log_prefix, before_count, len(original_artifacts_only),
                list(execution_artifact_info.keys()),
            )

        log.info(
            "%s Returning %d artifact details (filtered from %d total, excluded %d generated files).",
            log_prefix,
            len(original_artifacts_only),
            len(artifact_info_list),
            len(artifact_info_list) - len(original_artifacts_only),
        )
        return original_artifacts_only

    except Exception as e:
        log.exception("%s Error retrieving artifact details: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve artifact details: {str(e)}",
        )


@router.get(
    "/{session_id}/{filename}",
    summary="Get Latest Artifact Content",
    description="Retrieves the content of the latest version of a specific artifact.",
)
async def get_latest_artifact(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    max_bytes: Optional[int] = Query(
        None,
        ge=1,
        le=1048576,
        description=(
            "If provided, truncate the response body to at most this many bytes. "
            "Useful for generating tile previews without downloading the full artifact. "
            "When truncation is applied, embed resolution is skipped and the response "
            "includes an X-Truncated: true header."
        ),
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of the latest version of the specified artifact
    associated with the specified context (session or project).

    When ``max_bytes`` is supplied the response is truncated to that size.
    This is intended for lightweight tile previews on the artifacts page so
    the frontend does not need to download multi-megabyte files just to show
    an 8-line snippet.  Embed / template resolution is skipped in this mode.
    """
    log_prefix = (
        f"[ArtifactRouter:GetLatest:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    # Resolve storage context (single DB lookup also returns artifact version info)
    storage_user_id, storage_session_id, context_type, execution_artifact_info = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s",
                log_prefix, context_type, storage_user_id, storage_session_id)

        # For scheduled execution sessions, pin to the version produced by
        # this specific execution so the user sees the correct artifact state.
        # The artifact info was already fetched in _resolve_storage_context.
        pinned_version = None
        if execution_artifact_info and filename in execution_artifact_info:
            pinned_version = execution_artifact_info[filename]
            if pinned_version is not None:
                log.info(
                    "%s Using pinned version %d for scheduled execution artifact %s",
                    log_prefix, pinned_version, filename,
                )

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
            version=pinned_version,
        )

        if artifact_part is None or artifact_part.inline_data is None:
            log.warning("%s Artifact not found or has no data.", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' not found or is empty.",
            )

        data_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type or "application/octet-stream"
        original_size = len(data_bytes)
        truncated = False
        log.info(
            "%s Artifact loaded successfully (%d bytes, %s).",
            log_prefix,
            original_size,
            mime_type,
        )

        # When max_bytes is requested, truncate early and skip embed resolution.
        # This is used by the artifacts page to generate lightweight tile previews
        # without downloading multi-megabyte files.
        if max_bytes is not None and original_size > max_bytes:
            data_bytes = data_bytes[:max_bytes]
            # Ensure we don't split a multi-byte UTF-8 character (e.g. emoji/CJK)
            if is_text_based_mime_type(mime_type):
                data_bytes = data_bytes.decode("utf-8", "ignore").encode("utf-8")
            truncated = True
            log.info(
                "%s Truncating artifact from %d to %d bytes for preview.",
                log_prefix,
                original_size,
                max_bytes,
            )

        if not truncated and is_text_based_mime_type(mime_type) and component.enable_embed_resolution:
            log.info(
                "%s Artifact is text-based. Attempting recursive embed resolution.",
                log_prefix,
            )
            try:
                original_content_string = data_bytes.decode("utf-8")

                context_for_resolver = {
                    "artifact_service": artifact_service,
                    "session_context": {
                        "app_name": component.gateway_id,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                }
                config_for_resolver = {
                    "gateway_max_artifact_resolve_size_bytes": component.gateway_max_artifact_resolve_size_bytes,
                    "gateway_recursive_embed_depth": component.gateway_recursive_embed_depth,
                }

                resolved_content_string = await resolve_embeds_recursively_in_string(
                    text=original_content_string,
                    context=context_for_resolver,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES,
                    resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                # Also resolve any template blocks in the artifact
                resolved_content_string = await resolve_template_blocks_in_string(
                    text=resolved_content_string,
                    artifact_service=artifact_service,
                    session_context=context_for_resolver["session_context"],
                    log_identifier=f"{log_prefix}[TemplateResolve]",
                )
                log.info(
                    "%s Template block resolution complete. Final size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                data_bytes = resolved_content_string.encode("utf-8")
            except UnicodeDecodeError as ude:
                log.warning(
                    "%s Failed to decode artifact for recursive resolution: %s. Serving original content.",
                    log_prefix,
                    ude,
                )
            except Exception as resolve_err:
                log.exception(
                    "%s Error during recursive embed resolution: %s. Serving original content.",
                    log_prefix,
                    resolve_err,
                )
        else:
            log.info(
                "%s Artifact is not text-based or embed resolution is disabled. Serving original content.",
                log_prefix,
            )

        filename_encoded = quote(filename)
        response_headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
        }
        if truncated:
            response_headers["X-Truncated"] = "true"
            response_headers["X-Original-Size"] = str(original_size)
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers=response_headers,
        )

    except FileNotFoundError:
        log.warning("%s Artifact not found by service.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        )
    except Exception as e:
        log.exception("%s Error loading artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load artifact",
        )


@router.get(
    "/{session_id}/{filename}/versions/{version}",
    summary="Get Specific Artifact Version Content",
    description="Retrieves the content of a specific version of an artifact.",
)
async def get_specific_artifact_version(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    version: int | str = Path(
        ...,
        title="Version",
        description="The specific version number to retrieve, or 'latest'",
    ),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of a specific version of the specified artifact
    associated with the specified context (session or project).
    """
    log_prefix = f"[ArtifactRouter:GetVersion:{filename} v{version}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context
    storage_user_id, storage_session_id, context_type, _ = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
            version=version,
            load_metadata_only=False,
            return_raw_bytes=True,
            log_identifier_prefix="[ArtifactRouter:GetVersion]",
        )

        if load_result.get("status") != "success":
            error_message = load_result.get(
                "message", f"Failed to load artifact '{filename}' version '{version}'."
            )
            log.warning("%s %s", log_prefix, error_message)
            if (
                "not found" in error_message.lower()
                or "no versions available" in error_message.lower()
            ):
                status_code = status.HTTP_404_NOT_FOUND
            elif "invalid version" in error_message.lower():
                status_code = status.HTTP_400_BAD_REQUEST
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(status_code=status_code, detail=error_message)

        data_bytes = load_result.get("raw_bytes")
        mime_type = load_result.get("mime_type", "application/octet-stream")
        resolved_version_from_helper = load_result.get("version")
        if data_bytes is None:
            log.error(
                "%s Helper (with return_raw_bytes=True) returned success but no raw_bytes for '%s' v%s (resolved to %s).",
                log_prefix,
                filename,
                version,
                resolved_version_from_helper,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error retrieving artifact content.",
            )

        log.info(
            "%s Artifact '%s' version %s (resolved to %s) loaded successfully (%d bytes, %s). Streaming content.",
            log_prefix,
            filename,
            version,
            resolved_version_from_helper,
            len(data_bytes),
            mime_type,
        )

        if is_text_based_mime_type(mime_type) and component.enable_embed_resolution:
            log.info(
                "%s Artifact is text-based. Attempting recursive embed resolution.",
                log_prefix,
            )
            try:
                original_content_string = data_bytes.decode("utf-8")

                context_for_resolver = {
                    "artifact_service": artifact_service,
                    "session_context": {
                        "app_name": component.gateway_id,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                }
                config_for_resolver = {
                    "gateway_max_artifact_resolve_size_bytes": component.gateway_max_artifact_resolve_size_bytes,
                    "gateway_recursive_embed_depth": component.gateway_recursive_embed_depth,
                }

                resolved_content_string = await resolve_embeds_recursively_in_string(
                    text=original_content_string,
                    context=context_for_resolver,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES,
                    resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                # Also resolve any template blocks in the artifact
                resolved_content_string = await resolve_template_blocks_in_string(
                    text=resolved_content_string,
                    artifact_service=artifact_service,
                    session_context=context_for_resolver["session_context"],
                    log_identifier=f"{log_prefix}[TemplateResolve]",
                )
                log.info(
                    "%s Template block resolution complete. Final size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                data_bytes = resolved_content_string.encode("utf-8")
            except UnicodeDecodeError as ude:
                log.warning(
                    "%s Failed to decode artifact for recursive resolution: %s. Serving original content.",
                    log_prefix,
                    ude,
                )
            except Exception as resolve_err:
                log.exception(
                    "%s Error during recursive embed resolution: %s. Serving original content.",
                    log_prefix,
                    resolve_err,
                )
        else:
            log.info(
                "%s Artifact is not text-based or embed resolution is disabled. Serving original content.",
                log_prefix,
            )

        filename_encoded = quote(filename)
        # Artifact versions are immutable (version number is fixed), so we can
        # cache aggressively. Use private cache (user-specific content) with a
        # 1-hour max-age. The ETag is derived from the filename + resolved version
        # (both immutable) — no need to hash the content bytes.
        # This allows the browser to validate with If-None-Match and get a 304
        # instead of re-downloading the full content on subsequent visits.
        etag = f'"{hashlib.md5(f"{filename}-v{resolved_version_from_helper}".encode()).hexdigest()}"'
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}",
                "Cache-Control": "private, max-age=3600",
                "ETag": etag,
            },
        )

    except HTTPException:
        raise
    except FileNotFoundError:
        log.warning("%s Artifact version not found by service.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' version {version} not found.",
        )
    except ValueError as ve:
        log.warning("%s Invalid request (e.g., version format): %s", log_prefix, ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(ve)}",
        )
    except Exception as e:
        log.exception("%s Error loading artifact version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load artifact version: {str(e)}",
        )


@router.get(
    "/scheduled/{session_id}/{filename}",
    summary="Get Scheduled Task Artifact",
    description="Retrieves artifact content from a scheduled task execution session.",
)
async def get_scheduled_task_artifact(
    session_id: str = Path(..., title="Session ID", description="The scheduler session ID"),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    download: bool = Query(False, description="Force download (true) or inline view (false)"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
    db: Session = Depends(get_db),
):
    """
    Retrieves artifact content from a scheduled task execution.
    Verifies that the requesting user owns the scheduled task that produced this artifact.
    """
    log_prefix = f"[ArtifactRouter:Scheduled:{filename}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    if not session_id.startswith("scheduled_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scheduler session ID format.",
        )

    # Prevent path traversal attacks via crafted filenames (including URL-encoded sequences)
    import os
    from urllib.parse import unquote
    decoded_filename = unquote(filename)
    if os.path.basename(decoded_filename) != decoded_filename or not decoded_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artifact filename.",
        )

    # Verify the requesting user owns the task that produced this artifact
    # and that it belongs to this gateway's namespace.
    # Return 404 (not 403) to avoid confirming existence to unauthorized users.
    from ..repository.scheduled_task_repository import ScheduledTaskRepository
    repo = ScheduledTaskRepository()
    execution = repo.find_execution_by_session_id(db, session_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found.",
        )
    task = repo.find_by_id(db, execution.scheduled_task_id)
    if not task or task.created_by != user_id or task.namespace != component.get_namespace():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        # Artifacts are stored under the stable task-level context_id
        # (scheduled_task_{task_id}), not the per-execution chat session
        # (scheduled_{execution_id}).  Resolve the correct storage session.
        storage_session_id = f"scheduled_task_{execution.scheduled_task_id}"

        # Pin to the version produced by this execution (if available)
        pinned_version = None
        if execution.artifacts:
            for art in execution.artifacts:
                if isinstance(art, dict):
                    art_name = art.get("name") or art.get("filename")
                    if art_name == filename and art.get("version") is not None:
                        pinned_version = art["version"]
                        break

        log.info(
            "%s Resolved storage session: %s (from chat session %s, pinned_version=%s)",
            log_prefix, storage_session_id, session_id, pinned_version,
        )

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=storage_session_id,
            filename=filename,
            version=pinned_version,
        )

        if artifact_part is None or artifact_part.inline_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' not found or is empty.",
            )

        data_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type or "application/octet-stream"

        filename_encoded = quote(filename)
        disposition = "attachment" if download else "inline"

        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{filename_encoded}"
            },
        )

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        )
    except Exception as e:
        log.exception("%s Error loading artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load artifact",
        )


@router.get(
    "/by-uri",
    response_class=StreamingResponse,
    summary="Get Artifact by URI",
    description="Resolves a formal artifact:// URI and streams its content. This endpoint is secure and validates that the requesting user is authorized to access the specified artifact.",
)
async def get_artifact_by_uri(
    uri: str,
    requesting_user_id: str = Depends(get_user_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Resolves an artifact:// URI and streams its content.
    This allows fetching artifacts from any context, not just the current user's session,
    after performing an authorization check.
    """
    log_id_prefix = "[ArtifactRouter:by-uri]"
    log.info(
        "%s Received request for URI: %s from user: %s",
        log_id_prefix,
        uri,
        requesting_user_id,
    )
    artifact_service = component.get_shared_artifact_service()
    if not artifact_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact service not available.",
        )

    try:
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme != "artifact":
            raise ValueError("Invalid URI scheme, must be 'artifact'.")

        app_name = parsed_uri.netloc
        path_parts = parsed_uri.path.strip("/").split("/")
        if not app_name or len(path_parts) != 3:
            raise ValueError(
                "Invalid URI path structure. Expected artifact://app_name/user_id/session_id/filename"
            )

        owner_user_id, session_id, filename = path_parts

        query_params = parse_qs(parsed_uri.query)
        version_list = query_params.get("version")
        if not version_list or not version_list[0]:
            raise ValueError("Version query parameter is required.")
        version = version_list[0]

        log.info(
            "%s Parsed URI: app=%s, owner=%s, session=%s, file=%s, version=%s",
            log_id_prefix,
            app_name,
            owner_user_id,
            session_id,
            filename,
            version,
        )

        is_authorized = False
        
        if owner_user_id == requesting_user_id:
            # User owns the artifact
            is_authorized = True
        elif session_id.startswith("project-"):
            # Project artifact - check if user has shared access to the project
            project_id = session_id.replace("project-", "", 1)
            from ..dependencies import SessionLocal
            from ..services.project_service import ProjectService
            if SessionLocal:
                db = SessionLocal()
                try:
                    project_service = ProjectService(component=component)
                    # _has_view_access checks both ownership and shared access
                    is_authorized = project_service._has_view_access(db, project_id, requesting_user_id)
                finally:
                    db.close()
        
        if not is_authorized:
            log.warning(
                "%s Authorization denied: User '%s' attempted to access artifact owned by '%s' (session=%s)",
                log_id_prefix,
                requesting_user_id,
                owner_user_id,
                session_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to access this artifact.",
            )

        log.info(
            "%s User '%s' authorized to access artifact URI.",
            log_id_prefix,
            requesting_user_id,
        )

        loaded_artifact = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=owner_user_id,
            session_id=session_id,
            filename=filename,
            version=int(version),
            return_raw_bytes=True,
            log_identifier_prefix=log_id_prefix,
            component=component,
        )

        if loaded_artifact.get("status") != "success":
            raise HTTPException(status_code=404, detail=loaded_artifact.get("message"))

        content_bytes = loaded_artifact.get("raw_bytes")
        mime_type = loaded_artifact.get("mime_type", "application/octet-stream")

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions (authorization denied, not found, etc.)
        raise
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid artifact URI: {e}")
    except Exception as e:
        log.exception("%s Error fetching artifact by URI: %s", log_id_prefix, e)
        raise HTTPException(
            status_code=500, detail="Internal server error fetching artifact by URI"
        )


@router.delete(
    "/{session_id}/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Artifact",
    description="Deletes an artifact and all its versions.",
)
async def delete_artifact(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to delete artifacts from"
    ),
    filename: str = Path(
        ..., title="Filename", description="The name of the artifact to delete"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:delete"])),
):
    """
    Deletes the specified artifact (including all its versions)
    associated with the current user and session ID.
    """
    log_prefix = (
        f"[ArtifactRouter:Delete:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    # Validate session exists and belongs to user
    if not validate_session(session_id, user_id):
        log.warning("%s Session validation failed or access denied.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied.",
        )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        await artifact_service.delete_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

        log.info("%s Artifact deletion request processed successfully.", log_prefix)
        # Invalidate the cached artifact list so the next page view reflects this deletion
        _artifact_list_cache.invalidate(user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        log.exception("%s Error deleting artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete artifact: {str(e)}",
        )


