"""
Database utilities for repositories and data access.

Provides:
- Base repository classes (PaginatedRepository, ValidationMixin)
- Database exception handlers
- Database helpers (SimpleJSON, OptimizedUUID types)
- Database helpers (SimpleJSON type)
- Base declarative base for SQLAlchemy models
- OptimizedUUID type for cross-database UUID support
- generate_uuidv7 for UUIDv7 ID generation
"""

from .base_repository import PaginatedRepository, ValidationMixin
from .database_exceptions import DatabaseExceptionHandler, DatabaseErrorDecorator
from .database_helpers import SimpleJSON, OptimizedUUID
from .base import Base
from .database_types import OptimizedUUID
from .id_generators import generate_uuidv7

__all__ = [
    "PaginatedRepository",
    "ValidationMixin",
    "DatabaseExceptionHandler",
    "DatabaseErrorDecorator",
    "SimpleJSON",
    "Base",
    "OptimizedUUID",
    "generate_uuidv7",
]
