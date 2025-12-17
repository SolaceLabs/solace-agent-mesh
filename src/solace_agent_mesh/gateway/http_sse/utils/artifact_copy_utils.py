"""
Utility functions for copying project artifacts to sessions.
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy.orm import Session as DbSession

from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent
    from ....gateway.http_sse.services.project_service import ProjectService

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    class BaseArtifactService:
        pass


log = logging.getLogger(__name__)


async def has_pending_project_context(
    user_id: str,
    session_id: str,
    artifact_service: BaseArtifactService,
    app_name: str,
    db: DbSession,
) -> bool:
    """
    Check if session has any artifacts with pending project context.

    This is used to determine if we should inject full project context
    on the next user message after a session has been moved to a project.

    Args:
        user_id: User ID
        session_id: Session ID
        artifact_service: Artifact service instance
        app_name: Application name for artifact storage
        db: Database session

    Returns:
        True if any artifacts have project_context_pending=True metadata
    """
    try:
        session_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        # Check each artifact's metadata to see if it has pending project context
        for artifact_info in session_artifacts:
            loaded_metadata = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=artifact_info.filename,
                load_metadata_only=True,
                version="latest",
            )

            if loaded_metadata.get("status") == "success":
                metadata = loaded_metadata.get("metadata", {})
                if metadata.get("project_context_pending"):
                    return True

        return False
    except Exception as e:
        log.warning("Failed to check for pending project context: %s", e)
        return False


async def clear_pending_project_context(
    user_id: str,
    session_id: str,
    artifact_service: BaseArtifactService,
    app_name: str,
    db: DbSession,
    log_prefix: str = "",
) -> None:
    """
    Clear the project_context_pending flag from all artifacts in a session.

    This should be called after project context has been injected to the agent.

    Args:
        user_id: User ID
        session_id: Session ID
        artifact_service: Artifact service instance
        app_name: Application name for artifact storage
        db: Database session
        log_prefix: Optional prefix for log messages
    """
    try:
        session_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        for artifact_info in session_artifacts:
            loaded_metadata = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=artifact_info.filename,
                load_metadata_only=True,
                version="latest",
            )

            if loaded_metadata.get("status") == "success":
                metadata = loaded_metadata.get("metadata", {})

                # Only update if the artifact has the pending flag
                if metadata.get("project_context_pending"):
                    log.debug(
                        "%sClearing project_context_pending flag for artifact %s",
                        log_prefix,
                        artifact_info.filename,
                    )

                    # Remove the pending flag
                    metadata.pop("project_context_pending", None)

                    loaded_artifact = await load_artifact_content_or_metadata(
                        artifact_service=artifact_service,
                        app_name=app_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=artifact_info.filename,
                        return_raw_bytes=True,
                        version="latest",
                    )

                    if loaded_artifact.get("status") == "success":
                        await save_artifact_with_metadata(
                            artifact_service=artifact_service,
                            app_name=app_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=artifact_info.filename,
                            content_bytes=loaded_artifact.get("raw_bytes"),
                            mime_type=loaded_artifact.get("mime_type"),
                            metadata_dict=metadata,
                            timestamp=datetime.now(timezone.utc),
                        )
    except Exception as e:
        log.warning("%sFailed to clear pending project context flags: %s", log_prefix, e)


async def copy_project_artifacts_to_session(
    project_id: str,
    user_id: str,
    session_id: str,
    project_service: "ProjectService",
    component: "WebUIBackendComponent",
    db: "DbSession",
    log_prefix: str = "",
    include_bm25_index: bool = True,
) -> tuple[int, list[str]]:
    """
    Copy all artifacts from a project to a session.

    This function handles:
    - Loading artifacts from the project storage
    - Checking which artifacts already exist in the session
    - Copying new artifacts to the session
    - Copying BM25 index directory (if include_bm25_index=True)
    - Setting the 'source' metadata field to 'project'

    Args:
        project_id: ID of the project containing artifacts
        user_id: ID of the user (for session artifact storage)
        session_id: ID of the session to copy artifacts to
        project_service: ProjectService instance for accessing projects
        component: WebUIBackendComponent for accessing artifact service
        db: Database session to use for queries
        log_prefix: Optional prefix for log messages
        include_bm25_index: If True, also copies the bm25_index directory

    Returns:
        Tuple of (artifacts_copied_count, list_of_new_artifact_names)

    Raises:
        Exception: If project or artifact service is not available
    """
    if not project_id:
        log.debug("%sNo project_id provided, skipping artifact copy", log_prefix)
        return 0, []

    if db is None:
        log.warning("%sArtifact copy skipped: database session not provided", log_prefix)
        return 0, []

    try:
        project = project_service.get_project(db, project_id, user_id)
        if not project:
            log.warning("%sProject %s not found for user %s", log_prefix, project_id, user_id)
            return 0, []

        artifact_service = component.get_shared_artifact_service()
        if not artifact_service:
            log.warning("%sArtifact service not available", log_prefix)
            return 0, []

        source_user_id = project.user_id
        project_artifacts_session_id = f"project-{project.id}"

        log.info(
            "%sChecking for artifacts in project %s (storage session: %s)",
            log_prefix,
            project.id,
            project_artifacts_session_id,
        )

        # Get list of artifacts in the project
        project_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=project_service.app_name,
            user_id=source_user_id,
            session_id=project_artifacts_session_id,
        )

        if not project_artifacts:
            log.info("%sNo artifacts found in project %s", log_prefix, project.id)
            return 0, []

        log.info(
            "%sFound %d artifacts in project %s to process",
            log_prefix,
            len(project_artifacts),
            project.id,
        )

        try:
            session_artifacts = await get_artifact_info_list(
                artifact_service=artifact_service,
                app_name=project_service.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            session_artifact_names = {art.filename for art in session_artifacts}
            log.debug(
                "%sSession %s currently has %d artifacts",
                log_prefix,
                session_id,
                len(session_artifact_names),
            )
        except Exception as e:
            log.warning(
                "%sFailed to get session artifacts, will copy all project artifacts: %s",
                log_prefix,
                e,
            )
            session_artifact_names = set()

        artifacts_copied = 0
        new_artifact_names = []

        for artifact_info in project_artifacts:
            # Skip if artifact already exists in session
            if artifact_info.filename in session_artifact_names:
                log.debug(
                    "%sSkipping artifact %s - already exists in session",
                    log_prefix,
                    artifact_info.filename,
                )
                continue

            new_artifact_names.append(artifact_info.filename)

            log.info(
                "%sCopying artifact %s to session %s",
                log_prefix,
                artifact_info.filename,
                session_id,
            )

            try:
                # Load artifact content from project storage
                loaded_artifact = await load_artifact_content_or_metadata(
                    artifact_service=artifact_service,
                    app_name=project_service.app_name,
                    user_id=source_user_id,
                    session_id=project_artifacts_session_id,
                    filename=artifact_info.filename,
                    return_raw_bytes=True,
                    version="latest",
                )

                # Load the full metadata separately
                loaded_metadata = await load_artifact_content_or_metadata(
                    artifact_service=artifact_service,
                    app_name=project_service.app_name,
                    user_id=source_user_id,
                    session_id=project_artifacts_session_id,
                    filename=artifact_info.filename,
                    load_metadata_only=True,
                    version="latest",
                )

                # Save a copy to the current chat session
                if loaded_artifact.get("status") == "success":
                    full_metadata = (
                        loaded_metadata.get("metadata", {})
                        if loaded_metadata.get("status") == "success"
                        else {}
                    )

                    # This flag will be checked on the next user message to inject full context
                    full_metadata["project_context_pending"] = True

                    await save_artifact_with_metadata(
                        artifact_service=artifact_service,
                        app_name=project_service.app_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=artifact_info.filename,
                        content_bytes=loaded_artifact.get("raw_bytes"),
                        mime_type=loaded_artifact.get("mime_type"),
                        metadata_dict=full_metadata,
                        timestamp=datetime.now(timezone.utc),
                    )
                    artifacts_copied += 1
                    log.info(
                        "%sSuccessfully copied artifact %s to session",
                        log_prefix,
                        artifact_info.filename,
                    )
                else:
                    log.warning(
                        "%sFailed to load artifact %s: %s",
                        log_prefix,
                        artifact_info.filename,
                        loaded_artifact.get("status"),
                    )
            except Exception as e:
                log.error(
                    "%sError copying artifact %s to session: %s",
                    log_prefix,
                    artifact_info.filename,
                    e,
                )
                
        if artifacts_copied > 0:
            log.info(
                "%sCopied %d new artifacts to session %s",
                log_prefix,
                artifacts_copied,
                session_id,
            )
        else:
            log.debug("%sNo new artifacts to copy to session %s", log_prefix, session_id)

        return artifacts_copied, new_artifact_names

    except Exception as e:
        log.warning("%sFailed to copy project artifacts to session: %s", log_prefix, e)
        return 0, []


async def copy_bm25_index_to_session(
    project_id: str,
    user_id: str,
    session_id: str,
    project_service: "ProjectService",
    component: "WebUIBackendComponent",
    db: "DbSession",
    log_prefix: str = "",
):
    """
    Copy the BM25 index directory from a project to a session.
    
    This function:
    - Locates the project's bm25_index directory using artifact canonical_uri
    - Copies the entire directory tree to the session storage
    - Uses filesystem operations (only works with filesystem-based storage)
    
    Args:
        project_id: ID of the project containing the BM25 index
        user_id: ID of the user (for session artifact storage)
        session_id: ID of the session to copy the index to
        project_service: ProjectService instance for accessing projects
        component: WebUIBackendComponent for accessing artifact service
        db: Database session to use for queries
        log_prefix: Optional prefix for log messages
    
    Returns:
        True if BM25 index was copied successfully, False otherwise
    """
    log.info("here !")
    if not project_id:
        log.debug("%sNo project_id provided, skipping BM25 index copy", log_prefix)
        return False
    
    try:
        project = project_service.get_project(db, project_id, user_id)
        if not project:
            log.warning("%sProject %s not found for user %s", log_prefix, project_id, user_id)
            return False
        
        artifact_service = component.get_shared_artifact_service()
        if not artifact_service:
            log.warning("%sArtifact service not available", log_prefix)
            return False
        
        source_user_id = project.user_id
        project_session_id = f"project-{project.id}"
        
        # Get project artifacts to extract the project root path
        project_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=project_service.app_name,
            user_id=source_user_id,
            session_id=project_session_id,
        )

        log.info("here !!")
        
        if not project_artifacts:
            log.debug("%sNo artifacts in project, cannot determine project root path", log_prefix)
            return False
        
        # Get canonical_uri from first artifact to extract project root
        first_artifact = project_artifacts[0]
        source_artifact_version = await artifact_service.get_artifact_version(
            app_name=project_service.app_name,
            user_id=source_user_id,
            session_id=project_session_id,
            filename=first_artifact.filename,
            version=first_artifact.version if first_artifact.version else 0,
        )
        
        if not source_artifact_version or not source_artifact_version.canonical_uri:
            log.warning("%sCannot get canonical_uri for project artifacts", log_prefix)
            return False
        
        # Extract project root from canonical_uri
        parsed_uri = urlparse(source_artifact_version.canonical_uri)
        source_artifact_path = Path(parsed_uri.path)
        source_project_root = source_artifact_path.parent.parent
        source_bm25_dir = source_project_root / "bm25_index"
        
        # Check if source BM25 index exists
        if not source_bm25_dir.exists():
            log.debug("%sNo BM25 index directory found at %s", log_prefix, source_bm25_dir)
            return False
        
        if not source_bm25_dir.is_dir():
            log.warning("%sBM25 index path is not a directory: %s", log_prefix, source_bm25_dir)
            return False
        
        # Get session artifacts to determine session root path
        session_artifacts = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=project_service.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        
        if not session_artifacts:
            log.warning(
                "%sNo artifacts in target session yet, cannot determine session root path. "
                "Copy artifacts first before copying BM25 index.",
                log_prefix,
            )
            return False
        
        log.info("here !!")
        
        # Get canonical_uri of first session artifact
        target_artifact_version = await artifact_service.get_artifact_version(
            app_name=project_service.app_name,
            user_id=user_id,
            session_id=session_id,
            filename=session_artifacts[0].filename,
            version=session_artifacts[0].version if session_artifacts[0].version else 0,
        )
        
        if not target_artifact_version or not target_artifact_version.canonical_uri:
            log.warning("%sCannot get canonical_uri for session artifacts", log_prefix)
            return False
        
        # Extract session root from canonical_uri
        target_parsed_uri = urlparse(target_artifact_version.canonical_uri)
        target_artifact_path = Path(target_parsed_uri.path)
        target_session_root = target_artifact_path.parent.parent
        target_bm25_dir = target_session_root / "bm25_index"
        
        # If target already exists, remove it first to ensure we get the latest index
        if target_bm25_dir.exists():
            log.info(
                "%sBM25 index directory already exists in session, removing old version: %s",
                log_prefix,
                target_bm25_dir,
            )
            shutil.rmtree(target_bm25_dir)
        
        log.info("here !!!!")

        # Create parent directory if needed
        target_bm25_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the entire directory tree
        log.info(
            "%sCopying BM25 index directory:\n  From: %s\n  To: %s",
            log_prefix,
            source_bm25_dir,
            target_bm25_dir,
        )
        
        shutil.copytree(source_bm25_dir, target_bm25_dir)
        
        log.info("%sSuccessfully copied BM25 index directory to session", log_prefix)
        # return source_bm25_dir, target_bm25_dir

        return True
        
    except Exception as e:
        log.error("%sError copying BM25 index directory: %s", log_prefix, e)
        return None
