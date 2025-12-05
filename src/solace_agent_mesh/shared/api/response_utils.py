"""
Standardized Response Utilities

Provides consistent response formatting across all API endpoints.
Ensures uniform {data: ...} and {data: [...], meta: ...} response structure.
"""

from typing import TypeVar, Generic, Any, Dict, List
from pydantic import BaseModel
from .pagination import PaginationParams, PaginatedResponse, DataResponse


T = TypeVar('T')


def create_data_response(data: T) -> DataResponse[T]:
    """
    Create a standardized data response.

    Args:
        data: The response data

    Returns:
        DataResponse with format: {data: T}

    Example:
        create_data_response({"id": 1, "name": "test"})
        # Returns: {"data": {"id": 1, "name": "test"}}
    """
    return DataResponse.create(data)


def create_paginated_response(
    data: List[T],
    total_count: int,
    pagination_params: PaginationParams
) -> PaginatedResponse[T]:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total_count: Total number of items across all pages
        pagination_params: Pagination parameters used for the request

    Returns:
        PaginatedResponse with format: {data: [T], meta: {pagination: {...}}}

    Example:
        create_paginated_response([{"id": 1}, {"id": 2}], 50, params)
        # Returns: {
        #   "data": [{"id": 1}, {"id": 2}],
        #   "meta": {
        #     "pagination": {
        #       "pageNumber": 1,
        #       "pageSize": 20,
        #       "totalPages": 3,
        #       "count": 50,
        #       "nextPage": 2
        #     }
        #   }
        # }
    """
    return PaginatedResponse.create(data, total_count, pagination_params)


def create_empty_data_response() -> DataResponse[None]:
    """
    Create a standardized empty data response.

    Returns:
        DataResponse with format: {data: null}
    """
    return DataResponse.create(None)


def create_success_response(message: str = "Success") -> DataResponse[Dict[str, str]]:
    """
    Create a standardized success response.

    Args:
        message: Success message

    Returns:
        DataResponse with format: {data: {message: "Success"}}
    """
    return DataResponse.create({"message": message})


def create_list_response(items: List[T]) -> DataResponse[List[T]]:
    """
    Create a standardized list response (non-paginated).

    Args:
        items: List of items

    Returns:
        DataResponse with format: {data: [T]}

    Example:
        create_list_response([{"id": 1}, {"id": 2}])
        # Returns: {"data": [{"id": 1}, {"id": 2}]}
    """
    return DataResponse.create(items)


class StandardResponseMixin:
    """
    Mixin class to add standard response methods to services or controllers.
    """

    @staticmethod
    def data_response(data: T) -> DataResponse[T]:
        """Create a data response."""
        return create_data_response(data)

    @staticmethod
    def paginated_response(
        data: List[T],
        total_count: int,
        pagination_params: PaginationParams
    ) -> PaginatedResponse[T]:
        """Create a paginated response."""
        return create_paginated_response(data, total_count, pagination_params)

    @staticmethod
    def success_response(message: str = "Success") -> DataResponse[Dict[str, str]]:
        """Create a success response."""
        return create_success_response(message)

    @staticmethod
    def list_response(items: List[T]) -> DataResponse[List[T]]:
        """Create a list response."""
        return create_list_response(items)