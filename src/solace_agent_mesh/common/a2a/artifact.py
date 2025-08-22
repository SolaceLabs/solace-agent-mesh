"""
Helpers for creating and consuming A2A Artifact objects.
"""
import uuid


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


# --- Consumption Helpers ---


def get_artifact_id(artifact: Artifact) -> str:
    """Safely retrieves the ID from an Artifact object."""
    return artifact.artifact_id


def get_artifact_name(artifact: Artifact) -> Optional[str]:
    """Safely retrieves the name from an Artifact object."""
    return artifact.name


from a2a.types import (
    Artifact,
    DataPart,
    FilePart,
    Part,
    TextPart,
)
from typing import Any, List, Optional, Union


def get_parts_from_artifact(
    artifact: Artifact,
) -> List[Union[TextPart, DataPart, FilePart]]:
    """
    Extracts the raw, unwrapped Part objects (TextPart, DataPart, etc.) from an Artifact.

    Args:
        artifact: The `Artifact` object.

    Returns:
        A list of the unwrapped content parts.
    """
    return [part.root for part in artifact.parts]
