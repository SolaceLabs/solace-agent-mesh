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
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
    ConfigurationError,
    DataIntegrityError,
    ExternalServiceError,
    InternalServiceError,
    EntityOperation,
)
from .exception_handlers import register_exception_handlers
from .error_dto import EventErrorDTO

__all__ = [
    "WebUIBackendException",
    "ValidationError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "BusinessRuleViolationError",
    "ConfigurationError",
    "DataIntegrityError",
    "ExternalServiceError",
    "InternalServiceError",
    "EntityOperation",
    "register_exception_handlers",
    "EventErrorDTO",
]
