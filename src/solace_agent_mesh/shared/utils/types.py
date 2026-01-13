"""
Custom types and type aliases used throughout the application.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

# Basic type aliases
UserId = str
SessionId = str
MessageId = str
TaskId = str
AgentId = str

# Dictionary types
JsonDict = dict[str, Any]
Headers = dict[str, str]
QueryParams = dict[str, str | list[str]]


# Common data structures
class Timestamp(BaseModel):
    """Standardized timestamp representation using epoch milliseconds."""

    created_time: int  # Epoch milliseconds
    updated_time: int | None = None  # Epoch milliseconds


class LegacyTimestamp(BaseModel):
    """Legacy timestamp representation (deprecated - use Timestamp instead)."""

    created_at: datetime
    updated_at: datetime | None = None


class SortInfo(BaseModel):
    """Sorting information for list requests."""

    field: str
    direction: str = "asc"  # asc or desc


class FilterInfo(BaseModel):
    """Filtering information for list requests."""

    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, contains, in
    value: Any
