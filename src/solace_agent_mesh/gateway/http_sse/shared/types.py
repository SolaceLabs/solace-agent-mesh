"""
Custom types and type aliases used throughout the application.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel

# Basic type aliases
UserId = str
SessionId = str
MessageId = str
TaskId = str
AgentId = str

# Dictionary types
JsonDict = Dict[str, Any]
Headers = Dict[str, str]
QueryParams = Dict[str, Union[str, List[str]]]

# Common data structures
class Timestamp(BaseModel):
    """Standardized timestamp representation."""
    created_at: datetime
    updated_at: Optional[datetime] = None

class PaginationInfo(BaseModel):
    """Pagination information for list responses."""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool

class SortInfo(BaseModel):
    """Sorting information for list requests."""
    field: str
    direction: str = "asc"  # asc or desc

class FilterInfo(BaseModel):
    """Filtering information for list requests."""
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, contains, in
    value: Any