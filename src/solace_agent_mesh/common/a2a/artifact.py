"""
Helpers for creating and consuming A2A Artifact objects.
"""

import logging
import uuid
import base64
from datetime import datetime, timezone
from typing import Any, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

from .types import ContentPart
from a2a.types import (
    Artifact,
    DataPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TextPart,
)
from .. import a2a

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService

log = logging.getLogger(__name__)

# --- Creation Helpers ---


def create_text_artifact(
    name: str,
    text: str,
    description: str = "",
    artifact_id: Optional[str] = None,
) -> Artifact:
    """
    Creates a new Artifact object containing only a single TextPart.

    Args:
        name: The human-readable name of the artifact.
        text: The text content of the artifact.
        description: An optional description of the artifact.
        artifact_id: The artifact ID. If None, a new UUID is generated.

    Returns:
        A new `Artifact` object.
    """
    text_part = TextPart(text=text)
    return Artifact(
        artifact_id=artifact_id or str(uuid.uuid4().hex),
        parts=[Part(root=text_part)],
        name=name,
        description=description,
    )


def create_data_artifact(
    name: str,
    data: dict[str, Any],
    description: str = "",
    artifact_id: Optional[str] = None,
) -> Artifact:
    """
    Creates a new Artifact object containing only a single DataPart.

    Args:
        name: The human-readable name of the artifact.
        data: The structured data content of the artifact.
        description: An optional description of the artifact.
        artifact_id: The artifact ID. If None, a new UUID is generated.

    Returns:
        A new `Artifact` object.
    """
    data_part = DataPart(data=data)
    return Artifact(
        artifact_id=artifact_id or str(uuid.uuid4().hex),
        parts=[Part(root=data_part)],
        name=name,
        description=description,
    )


def update_artifact_parts(artifact: Artifact, new_parts: List[ContentPart]) -> Artifact:
    """Returns a new Artifact with its parts replaced."""
    wrapped_parts = [Part(root=p) for p in new_parts]
    return artifact.model_copy(update={"parts": wrapped_parts})


async def prepare_file_part_for_publishing(
    part: FilePart,
    mode: str,
    artifact_service: "BaseArtifactService",
    user_id: str,
    session_id: str,
    target_agent_name: str,
    log_identifier: str,
) -> Optional[FilePart]:
    """
    Prepares a FilePart for publishing based on the artifact handling mode.

    - 'ignore': Returns None.
    - 'embed': Ensures the part contains bytes, resolving a URI if necessary.
    - 'reference': Ensures the part contains a URI, saving bytes if necessary.
    - 'passthrough': Returns the part as-is.

    Args:
        part: The input FilePart, which may contain raw bytes or a URI.
        mode: The artifact handling mode ('ignore', 'embed', 'reference', 'passthrough').
        artifact_service: The ADK artifact service instance.
        user_id: The user ID for the artifact context.
        session_id: The session ID for the artifact context.
        target_agent_name: The name of the agent the artifact will be associated with.
        log_identifier: The logging identifier for log messages.

    Returns:
        The processed FilePart, or None if ignored.
    """
    log_id = f"{log_identifier}[PrepareFilePart]"

    if mode == "ignore":
        log.debug("%s Mode is 'ignore', filtering out FilePart.", log_id)
        return None

    if mode == "passthrough":
        log.debug("%s Mode is 'passthrough', returning original FilePart.", log_id)
        return part

    if mode == "embed":
        if isinstance(part.file, FileWithUri):
            log.debug("%s Mode is 'embed', resolving URI for FilePart.", log_id)
            return await resolve_file_part_uri(part, artifact_service, log_identifier)
        return part  # It's already bytes, so it's embedded.

    if mode == "reference":
        if isinstance(part.file, FileWithBytes):
            if not artifact_service:
                log.warning(
                    "%s Mode is 'reference' but no artifact_service is configured. Ignoring FilePart '%s'.",
                    log_id,
                    part.file.name,
                )
                return None

            try:
                filename = part.file.name or f"upload-{uuid.uuid4().hex}"
                content_bytes = base64.b64decode(part.file.bytes)
                mime_type = part.file.mime_type or "application/octet-stream"

                # Create a concise and accurate metadata dictionary.
                metadata_to_save = {
                    "source": log_identifier,
                    "description": "This artifact was uploaded via the gateway",
                }

                # Call the helper with the new, simpler metadata.
                from ...agent.utils.artifact_helpers import save_artifact_with_metadata

                save_result = await save_artifact_with_metadata(
                    artifact_service=artifact_service,
                    app_name=target_agent_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    content_bytes=content_bytes,
                    mime_type=mime_type,
                    metadata_dict=metadata_to_save,
                    timestamp=datetime.now(timezone.utc),
                )

                if save_result["status"] == "success":
                    saved_version = save_result.get("data_version")
                    from ...agent.utils.artifact_helpers import format_artifact_uri

                    artifact_uri = format_artifact_uri(
                        app_name=target_agent_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=filename,
                        version=saved_version,
                    )
                    ref_part = a2a.create_file_part_from_uri(
                        uri=artifact_uri,
                        name=filename,
                        mime_type=mime_type,
                        metadata=part.metadata,
                    )
                    log.info(
                        "%s Converted embedded file '%s' to reference: %s",
                        log_id,
                        filename,
                        artifact_uri,
                    )
                    return ref_part
                else:
                    log.error(
                        "%s Failed to save artifact via helper: %s. Skipping FilePart.",
                        log_id,
                        save_result.get("message"),
                    )
                    return None

            except Exception as e:
                log.exception(
                    "%s Failed to save artifact for reference mode: %s. Skipping FilePart.",
                    log_id,
                    e,
                )
                return None
        return part  # It's already a reference (URI)

    # Default case if mode is unrecognized
    log.warning(
        "%s Unrecognized artifact_handling_mode '%s'. Ignoring FilePart.", log_id, mode
    )
    return None


async def resolve_file_part_uri(
    part: FilePart, artifact_service: "BaseArtifactService", log_identifier: str
) -> FilePart:
    """
    Resolves an artifact URI within a FilePart into embedded bytes.

    If the FilePart does not contain a resolvable `artifact://` URI, it is
    returned unchanged.

    Args:
        part: The FilePart to resolve.
        artifact_service: The ADK artifact service instance.
        log_identifier: The logging identifier for log messages.

    Returns:
        A FilePart, either with embedded bytes if resolved, or the original part.
    """
    if not (
        isinstance(part.file, FileWithUri)
        and part.file.uri
        and part.file.uri.startswith("artifact://")
    ):
        return part

    if not artifact_service:
        log.warning(
            "%s Cannot resolve artifact URI, artifact_service is not configured.",
            log_identifier,
        )
        return part

    uri = part.file.uri
    log_id_prefix = f"{log_identifier}[ResolveURI]"
    try:
        log.info("%s Found artifact URI to resolve: %s", log_id_prefix, uri)
        parsed_uri = urlparse(uri)
        app_name = parsed_uri.netloc
        path_parts = parsed_uri.path.strip("/").split("/")

        if not app_name or len(path_parts) != 3:
            raise ValueError(
                "Invalid URI structure. Expected artifact://app_name/user_id/session_id/filename"
            )

        user_id, session_id, filename = path_parts
        version_str = parse_qs(parsed_uri.query).get("version", [None])[0]
        version = int(version_str) if version_str else None

        from ...agent.utils.artifact_helpers import load_artifact_content_or_metadata

        loaded_artifact = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
            return_raw_bytes=True,
        )

        if loaded_artifact.get("status") == "success":
            content_bytes = loaded_artifact.get("raw_bytes")
            new_file_content = FileWithBytes(
                bytes=base64.b64encode(content_bytes).decode("utf-8"),
                mime_type=part.file.mime_type,
                name=part.file.name,
            )
            part.file = new_file_content
            log.info(
                "%s Successfully resolved and embedded artifact: %s",
                log_id_prefix,
                uri,
            )
        else:
            log.error(
                "%s Failed to resolve artifact URI '%s': %s",
                log_id_prefix,
                uri,
                loaded_artifact.get("message"),
            )
    except Exception as e:
        log.exception("%s Error resolving artifact URI '%s': %s", log_id_prefix, uri, e)
    return part


# --- Consumption Helpers ---


def get_artifact_id(artifact: Artifact) -> str:
    """Safely retrieves the ID from an Artifact object."""
    return artifact.artifact_id


def get_artifact_name(artifact: Artifact) -> Optional[str]:
    """Safely retrieves the name from an Artifact object."""
    return artifact.name


def get_parts_from_artifact(artifact: Artifact) -> List[ContentPart]:
    """
    Extracts the raw, unwrapped Part objects (TextPart, DataPart, etc.) from an Artifact.

    Args:
        artifact: The `Artifact` object.

    Returns:
        A list of the unwrapped content parts.
    """
    return [part.root for part in artifact.parts]


def is_text_only_artifact(artifact: Artifact) -> bool:
    """
    Checks if an artifact contains only TextParts.

    Args:
        artifact: The Artifact object to check.

    Returns:
        True if all parts are TextParts, False otherwise.
    """
    if not artifact.parts:
        return False
    
    for part in artifact.parts:
        if not isinstance(part.root, TextPart):
            return False
    
    return True


def get_text_content_from_artifact(artifact: Artifact) -> List[str]:
    """
    Extracts all text content from TextParts in an artifact.

    Args:
        artifact: The Artifact object to extract text from.

    Returns:
        A list of text strings from all TextParts. Returns empty list if no TextParts found.
    """
    text_content = []
    
    for part in artifact.parts:
        if isinstance(part.root, TextPart):
            text_content.append(part.root.text)
    
    return text_content
