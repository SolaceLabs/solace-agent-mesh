"""
Pagination utilities for API responses.

Provides standard pagination patterns for consistent API responses across the application.

Default pagination settings:
- Page number: 1
- Page size: 20
- Max page size: 100
"""

from pydantic import BaseModel, Field
from typing import TypeVar, Generic

T = TypeVar("T")

DEFAULT_PAGE_NUMBER = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PaginationParams(BaseModel):
    """
    Request parameters for pagination with sensible defaults.

    Defaults:
    - page_number: 1
    - page_size: 20
    """
    page_number: int = Field(default=DEFAULT_PAGE_NUMBER, ge=1, alias="pageNumber")
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize")

    @property
    def offset(self) -> int:
        """Calculate the offset for database queries."""
        return (self.page_number - 1) * self.page_size

    model_config = {"populate_by_name": True}


def get_pagination_or_default(pagination: PaginationParams | None = None) -> PaginationParams:
    """
    Get pagination parameters or return defaults if None.

    This helper ensures all paginated endpoints use the same defaults:
    - page_number: 1
    - page_size: 20

    Args:
        pagination: Optional pagination parameters

    Returns:
        PaginationParams with defaults if None provided

    Example:
        pagination = get_pagination_or_default(request_pagination)
        # Always returns valid PaginationParams with defaults if None
    """
    if pagination is None:
        return PaginationParams()
    return pagination


class PaginationMeta(BaseModel):
    """Pagination metadata for API responses."""
    page_number: int = Field(..., alias="pageNumber")
    count: int
    page_size: int = Field(..., alias="pageSize")
    next_page: int | None = Field(..., alias="nextPage")
    total_pages: int = Field(..., alias="totalPages")

    model_config = {"populate_by_name": True}


class Meta(BaseModel):
    """Metadata container for API responses."""
    pagination: PaginationMeta


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response with data and metadata."""
    data: list[T]
    meta: Meta

    @classmethod
    def create(
        cls, data: list[T], total_count: int, pagination: PaginationParams
    ) -> "PaginatedResponse[T]":
        """
        Create a paginated response from data and pagination parameters.

        Args:
            data: List of items for current page
            total_count: Total number of items across all pages
            pagination: Pagination parameters used for the request

        Returns:
            PaginatedResponse with data and calculated metadata
        """
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        next_page = pagination.page_number + 1 if pagination.page_number < total_pages else None

        pagination_meta = PaginationMeta(
            page_number=pagination.page_number,
            count=total_count,
            page_size=pagination.page_size,
            next_page=next_page,
            total_pages=total_pages,
        )

        return cls(
            data=data,
            meta=Meta(pagination=pagination_meta)
        )

    model_config = {"populate_by_name": True}


class DataResponse(BaseModel, Generic[T]):
    """Simple data response wrapper."""
    data: T

    @classmethod
    def create(cls, data: T) -> "DataResponse[T]":
        """Create a data response from data."""
        return cls(data=data)


__all__ = [
    "PaginationParams",
    "PaginationMeta",
    "PaginatedResponse",
    "DataResponse",
    "get_pagination_or_default",
    "DEFAULT_PAGE_NUMBER",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
]