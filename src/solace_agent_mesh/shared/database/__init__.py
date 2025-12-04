"""
Database utilities for repositories and data access.

Provides:
- Base repository classes (PaginatedRepository, ValidationMixin)
- Database exceptions (ConnectionError, TransactionError, etc.)
- Database helpers (connection management, query utilities)
"""

from .base_repository import PaginatedRepository, ValidationMixin
from .database_exceptions import (
    DatabaseError,
    ConnectionError,
    TransactionError,
    IntegrityError,
    QueryError,
    MigrationError,
)
from .database_helpers import (
    get_db_dialect,
    is_sqlite,
)

__all__ = [
    "PaginatedRepository",
    "ValidationMixin",
    "DatabaseError",
    "ConnectionError",
    "TransactionError",
    "IntegrityError",
    "QueryError",
    "MigrationError",
    "get_db_dialect",
    "is_sqlite",
]
