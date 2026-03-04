"""
Shared artifact pre-loading helpers for tool parameters.

This module provides the common logic for loading artifacts before tool execution.
Both DynamicTool and ADKToolWrapper use these helpers to avoid code duplication.
"""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id
from solace_agent_mesh.agent.utils.artifact_helpers import load_artifact_content_or_metadata
from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade
from .artifact_types import Artifact, ArtifactTypeInfo

log = logging.getLogger(__name__)


def is_tool_context_facade_param(annotation) -> bool:
    """Check if an annotation represents a ToolContextFacade parameter."""
    if annotation is None:
        return False
    if annotation is ToolContextFacade:
        return True
    if isinstance(annotation, str) and "ToolContextFacade" in annotation:
        return True
    return False


async def load_artifact_for_param(
    param_name: str,
    filename: str,
    tool_context: ToolContext,
    log_identifier: str,
) -> Artifact:
    """
    Load artifact for a parameter.

    Args:
        param_name: Name of the parameter
        filename: Artifact filename to load (supports filename:version format)
        tool_context: The ADK ToolContext for accessing services
        log_identifier: Prefix for log messages

    Returns:
        An Artifact object containing the content and all metadata

    Raises:
        ValueError: If artifact loading fails
    """
    if not filename:
        log.debug(
            "%s Skipping artifact load for '%s': empty filename",
            log_identifier,
            param_name,
        )
        raise ValueError(f"Empty filename for parameter '{param_name}'")

    try:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)

        # Parse filename:version format (rsplit to handle colons in filenames)
        parts = filename.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            filename_base = parts[0]
            version = int(parts[1])
        else:
            filename_base = filename
            version = "latest"

        log.debug(
            "%s Loading artifact '%s' (version=%s) for param '%s'",
            log_identifier,
            filename_base,
            version,
            param_name,
        )

        result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename_base,
            version=version,
            return_raw_bytes=True,
        )

        if result.get("status") == "success":
            content = result.get("raw_bytes") or result.get("content")
            # Get metadata from result
            loaded_version = result.get("version", 0 if version == "latest" else version)
            mime_type = result.get("mime_type", "application/octet-stream")
            metadata = result.get("metadata", {})

            log.info(
                "%s Loaded artifact '%s' v%s for param '%s' (%d bytes, %s)",
                log_identifier,
                filename_base,
                loaded_version,
                param_name,
                len(content) if content else 0,
                mime_type,
            )

            return Artifact(
                content=content,
                filename=filename_base,
                version=loaded_version,
                mime_type=mime_type,
                metadata=metadata,
            )
        else:
            error_msg = result.get("message", "Unknown error loading artifact")
            raise ValueError(f"Failed to load artifact '{filename}': {error_msg}")

    except ValueError:
        raise
    except Exception as e:
        log.error(
            "%s Failed to load artifact '%s' for param '%s': %s",
            log_identifier,
            filename,
            param_name,
            e,
        )
        raise ValueError(
            f"Artifact pre-load failed for parameter '{param_name}': {e}"
        ) from e


async def resolve_artifact_params(
    artifact_params: Dict[str, ArtifactTypeInfo],
    resolved_kwargs: Dict[str, Any],
    tool_context: Any,
    tool_name: str,
    log_identifier: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve artifact parameters by loading artifacts from the artifact store.

    Iterates through artifact_params, loads each artifact (or list of artifacts),
    and replaces the filename strings in resolved_kwargs with Artifact objects.

    Args:
        artifact_params: Dict mapping param names to ArtifactTypeInfo
        resolved_kwargs: The kwargs dict to modify in-place
        tool_context: The ADK ToolContext for accessing services
        tool_name: Tool name for error responses
        log_identifier: Prefix for log messages

    Returns:
        An error dict if loading fails, or None on success.
    """
    for param_name, param_info in artifact_params.items():
        if param_name not in resolved_kwargs:
            continue

        value = resolved_kwargs[param_name]

        # Handle List[Artifact] - load each filename in the list
        if param_info.is_list:
            if not value:
                # Empty list or None - keep as-is
                continue
            if not isinstance(value, list):
                log.warning(
                    "%s Expected list for param '%s' but got %s",
                    log_identifier,
                    param_name,
                    type(value).__name__,
                )
                continue

            loaded_artifacts = []
            for idx, filename in enumerate(value):
                if filename and isinstance(filename, str):
                    try:
                        artifact = await load_artifact_for_param(
                            param_name=f"{param_name}[{idx}]",
                            filename=filename,
                            tool_context=tool_context,
                            log_identifier=log_identifier,
                        )
                        loaded_artifacts.append(artifact)
                    except ValueError as e:
                        log.error(
                            "%s Artifact pre-load failed for %s[%d], returning error: %s",
                            log_identifier,
                            param_name,
                            idx,
                            e,
                        )
                        return {
                            "status": "error",
                            "message": str(e),
                            "tool_name": tool_name,
                        }
                else:
                    # Non-string entry - skip (shouldn't happen normally)
                    log.warning(
                        "%s Skipping non-string entry at %s[%d]: %s",
                        log_identifier,
                        param_name,
                        idx,
                        type(filename).__name__,
                    )

            resolved_kwargs[param_name] = loaded_artifacts
            log.debug(
                "%s Pre-loaded %d artifacts for list param '%s'",
                log_identifier,
                len(loaded_artifacts),
                param_name,
            )

        # Handle single Artifact
        elif value and isinstance(value, str):
            try:
                artifact = await load_artifact_for_param(
                    param_name=param_name,
                    filename=value,
                    tool_context=tool_context,
                    log_identifier=log_identifier,
                )
                resolved_kwargs[param_name] = artifact
            except ValueError as e:
                # Return error immediately if artifact loading fails
                log.error(
                    "%s Artifact pre-load failed, returning error: %s",
                    log_identifier,
                    e,
                )
                return {
                    "status": "error",
                    "message": str(e),
                    "tool_name": tool_name,
                }

    return None
