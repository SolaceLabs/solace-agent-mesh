"""
Defines types used within the embed processing system, like DataFormat.
"""

from enum import Enum, auto


class DataFormat(Enum):
    """Represents internal data formats during modifier chain execution."""

    BYTES = auto()
    STRING = auto()
    JSON_OBJECT = auto()
    LIST_OF_DICTS = auto()
