"""
Exception types and handlers for consistent error handling.

Provides:
- Business exception types (ValidationError, EntityNotFoundError, etc.)
- FastAPI exception handlers
- Error DTOs for API responses
"""

from .exceptions import (
    WebUIBackendException,
    ValidationError,
    EntityNotFoundError,
    DuplicateEntityError,
    BusinessRuleViolationError,
    ConflictError,
    EntityOperation,
)
from .exception_handlers import register_exception_handlers
from .error_dto import (
    ErrorResponse,
    ValidationErrorDetail,
    FieldError,
)

__all__ = [
    "WebUIBackendException",
    "ValidationError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "BusinessRuleViolationError",
    "ConflictError",
    "EntityOperation",
    "register_exception_handlers",
    "ErrorResponse",
    "ValidationErrorDetail",
    "FieldError",
]
