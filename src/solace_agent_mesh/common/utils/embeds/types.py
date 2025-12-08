"""
Defines types used within the embed processing system, like DataFormat.
"""

from enum import Enum, auto


class ResolutionMode(Enum):
    """Defines the context in which embed resolution is occurring."""

    A2A_MESSAGE_TO_USER = auto()
    TOOL_PARAMETER = auto()
    RECURSIVE_ARTIFACT_CONTENT = auto()
    ARTIFACT_STREAMING = auto()  # For streaming artifact chunks to browser


class DataFormat(Enum):
    """Represents internal data formats during modifier chain execution."""

    BYTES = auto()
    STRING = auto()
    JSON_OBJECT = auto()
    LIST_OF_DICTS = auto()
