"""
Common utility functions for working with ADK artifacts.
"""

import logging
from typing import Optional
from google.adk.artifacts import BaseArtifactService

log = logging.getLogger(__name__)


async def get_latest_artifact_version(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
) -> Optional[int]:
    """Resolves the latest version number for a given artifact."""
    try:
        versions = await artifact_service.list_artifact_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        if versions:
            return max(versions)
    except Exception as e:
        log.error(f"Error listing versions for artifact '{filename}': {e}")
    return None
