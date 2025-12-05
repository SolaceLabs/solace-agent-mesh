"""
API utilities for REST endpoints.

Provides:
- Pagination patterns (PaginationParams, PaginatedResponse, DataResponse)
- Response utilities (create_data_response, create_paginated_response)
- Auth utilities (get_current_user)

Note: Error responses are handled by exception_handlers in shared.exceptions
"""

from .pagination import (
    PaginationParams,
    PaginatedResponse,
    DataResponse,
    PaginationMeta,
    Meta,
    get_pagination_or_default,
    DEFAULT_PAGE_NUMBER,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)
from .response_utils import (
    create_data_response,
    create_paginated_response,
)
from .auth_utils import get_current_user

__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "DataResponse",
    "PaginationMeta",
    "Meta",
    "get_pagination_or_default",
    "DEFAULT_PAGE_NUMBER",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "create_data_response",
    "create_paginated_response",
    "get_current_user",
]
