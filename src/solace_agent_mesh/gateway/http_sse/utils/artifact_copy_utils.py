"""
Utility functions for copying project artifacts to sessions.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

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


async def copy_project_artifacts_to_session(
    project_id: str,
    user_id: str,
    session_id: str,
    project_service: "ProjectService",
    component: "WebUIBackendComponent",
    db: "DbSession",
    log_prefix: str = "",
    indexing_enabled: bool = False,
) -> tuple[int, list[str]]:
    """
    Copy artifacts from a project to a session.

    Behavior depends on the indexing_enabled feature flag:
    - When indexing_enabled=False (default): Copies only original user files
      (backward compatible behavior)
    - When indexing_enabled=True: Copies all artifacts including converted text
      files and BM25 index (complete context for search)

    This function handles:
    - Loading artifacts from the project storage
    - Filtering based on indexing feature flag
    - Checking which artifacts already exist in the session
    - Copying new artifacts to the session
    - Preserving all metadata (conversion info, citations, etc.)
    - Setting the 'project_context_pending' flag for context injection

    Args:
        project_id: ID of the project containing artifacts
        user_id: ID of the user (for session artifact storage)
        session_id: ID of the session to copy artifacts to
        project_service: ProjectService instance for accessing projects
        component: WebUIBackendComponent for accessing artifact service
        db: Database session to use for queries
        log_prefix: Optional prefix for log messages
        indexing_enabled: Whether BM25 indexing is enabled. When False, only
            original files are copied. When True, converted text files and
            BM25 index are also copied. Defaults to False for backward compatibility.

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

        # Filter artifacts based on indexing feature flag
        if not indexing_enabled:
            # When indexing is disabled, only copy original user files
            # Skip converted text files and BM25 index
            original_only_artifacts = [
                artifact for artifact in project_artifacts
                if not artifact.filename.endswith('.converted.txt')
                and artifact.filename != 'project_bm25_index.zip'
            ]
            log.info(
                "%sIndexing disabled: filtering to %d original artifacts (excluded %d generated files)",
                log_prefix,
                len(original_only_artifacts),
                len(project_artifacts) - len(original_only_artifacts),
            )
            project_artifacts = original_only_artifacts

        # Categorize artifacts for logging and visibility
        original_artifacts = []
        converted_artifacts = []
        index_artifacts = []

        for artifact in project_artifacts:
            if artifact.filename.endswith('.converted.txt'):
                converted_artifacts.append(artifact)
            elif artifact.filename == 'project_bm25_index.zip':
                index_artifacts.append(artifact)
            else:
                original_artifacts.append(artifact)

        log.info(
            "%sProject %s artifact breakdown (indexing_enabled=%s): %d original, %d converted, %d index",
            log_prefix,
            project.id,
            indexing_enabled,
            len(original_artifacts),
            len(converted_artifacts),
            len(index_artifacts),
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

            # Identify artifact type for logging
            artifact_type = "original"
            if artifact_info.filename.endswith('.converted.txt'):
                artifact_type = "converted"
            elif artifact_info.filename == 'project_bm25_index.zip':
                artifact_type = "index"

            log.info(
                "%sCopying %s artifact %s to session %s",
                log_prefix,
                artifact_type,
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
                        "%sSuccessfully copied %s artifact %s (v%s) to session",
                        log_prefix,
                        artifact_type,
                        artifact_info.filename,
                        loaded_artifact.get("version", "unknown"),
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
            # Count by type for summary
            copied_original = sum(
                1 for name in new_artifact_names
                if not name.endswith('.converted.txt')
                and name != 'project_bm25_index.zip'
            )
            copied_converted = sum(
                1 for name in new_artifact_names
                if name.endswith('.converted.txt')
            )
            copied_index = 1 if 'project_bm25_index.zip' in new_artifact_names else 0

            log.info(
                "%sCopied %d artifacts to session %s: %d original, %d converted, %d index",
                log_prefix,
                artifacts_copied,
                session_id,
                copied_original,
                copied_converted,
                copied_index,
            )
        else:
            log.debug("%sNo new artifacts to copy to session %s", log_prefix, session_id)

        return artifacts_copied, new_artifact_names

    except Exception as e:
        log.warning("%sFailed to copy project artifacts to session: %s", log_prefix, e)
        return 0, []
