"""
Database utilities for repositories and data access.

Provides:
- Base repository classes (PaginatedRepository, ValidationMixin)
- Database exception handlers
- Database helpers (SimpleJSON type)
"""

from .base_repository import PaginatedRepository, ValidationMixin
from .database_exceptions import DatabaseExceptionHandler, DatabaseErrorDecorator
from .database_helpers import SimpleJSON

__all__ = [
    "PaginatedRepository",
    "ValidationMixin",
    "DatabaseExceptionHandler",
    "DatabaseErrorDecorator",
    "SimpleJSON",
]
