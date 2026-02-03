"""
Custom type aliases for the A2A helper layer.
"""

from typing import Union, Optional, Dict, Any
from a2a.types import TextPart, DataPart, FilePart, AgentSkill
from pydantic import BaseModel, Field, ConfigDict, field_validator

# A type alias for the raw content parts of a message or artifact.
# This is the type that application logic should work with, insulating it
# from the SDK's generic `Part` wrapper.
ContentPart = Union[TextPart, DataPart, FilePart]


class ToolsExtensionParams(BaseModel):
    """
    The parameters for the custom 'tools' AgentCard extension.
    """

    tools: list[AgentSkill]


class SchemasExtensionParams(BaseModel):
    """
    The parameters for the custom 'schemas' AgentCard extension.
    """

    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class ArtifactInfo(BaseModel):
    """
    Represents information about an artifact, typically for listing or display.
    Mirrors the frontend ArtifactInfo type and the model used in artifact_helpers.py.
    """

    filename: str
    mime_type: Optional[str] = None
    size: int
    last_modified: Optional[str] = None
    description: Optional[str] = None
    schema_definition: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    uri: Optional[str] = None
    version: Optional[Union[int, str]] = None
    version_count: Optional[int] = None
    source: Optional[str] = None  # Optional: Source of the artifact (e.g., "project")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("version")
    @classmethod
    def validate_version_string(cls, v: Union[int, str]) -> Union[int, str]:
        if isinstance(v, str):
            if v.lower() == "latest":
                return v
            try:
                int(v)
                return v
            except ValueError as exc:
                raise ValueError(
                    f"String version must be 'latest' or a valid integer representation. Got: '{v}'"
                ) from exc
        return v
