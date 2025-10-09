"""
Shared Utilities and Constants

Contains common utilities, constants, enums, types, and exception handling
used across layers.
"""

from .auth_utils import get_current_user

# Repository base classes
from .base_repository import (
    BaseRepository,
    PaginatedRepository,
    ValidationMixin,
)

# Database utilities
from .database_exceptions import (
    DatabaseErrorDecorator,
    DatabaseExceptionHandler,
    handle_database_errors,
)

# Database helpers (SimpleJSON type only - transaction management removed)
from .database_helpers import SimpleJSON
from .error_dto import EventErrorDTO
from .exception_handlers import (
    business_rule_violation_handler,
    configuration_error_handler,
    create_error_response,
    data_integrity_error_handler,
    entity_already_exists_handler,
    entity_not_found_handler,
    external_service_error_handler,
    register_exception_handlers,
    validation_error_handler,
    webui_backend_exception_handler,
)

# Exception handling exports
from .exceptions import (
    BusinessRuleViolationError,
    ConfigurationError,
    DataIntegrityError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    EntityOperation,
    ExternalServiceError,
    ValidationError,
    ValidationErrorBuilder,
    WebUIBackendException,
)

# Pagination utilities
from .pagination import (
    DataResponse,
    PaginatedResponse,
    PaginationParams,
)

# Response utilities
from .response_utils import (
    StandardResponseMixin,
    create_data_response,
    create_empty_data_response,
    create_list_response,
    create_paginated_response,
    create_success_response,
)
from .timestamp_utils import (
    datetime_to_epoch_ms,
    epoch_ms_to_datetime,
    epoch_ms_to_iso8601,
    iso8601_to_epoch_ms,
    now_epoch_ms,
    validate_epoch_ms,
)

# Generic utilities
from .utils import generate_uuid, to_pascal_case, to_snake_case

__all__ = [
    # Utilities
    "get_current_user",
    "now_epoch_ms",
    "epoch_ms_to_iso8601",
    "iso8601_to_epoch_ms",
    "datetime_to_epoch_ms",
    "epoch_ms_to_datetime",
    "validate_epoch_ms",

    # Exception classes
    "WebUIBackendException",
    "ValidationError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "BusinessRuleViolationError",
    "ConfigurationError",
    "DataIntegrityError",
    "ExternalServiceError",
    "EntityOperation",
    "ValidationErrorBuilder",

    # Error response DTO
    "EventErrorDTO",

    # Exception handlers
    "register_exception_handlers",
    "create_error_response",
    "validation_error_handler",
    "entity_not_found_handler",
    "entity_already_exists_handler",
    "business_rule_violation_handler",
    "configuration_error_handler",
    "data_integrity_error_handler",
    "external_service_error_handler",
    "webui_backend_exception_handler",

    # Repository base classes
    "BaseRepository",
    "PaginatedRepository",
    "ValidationMixin",

    # Pagination utilities
    "PaginationParams",
    "PaginatedResponse",
    "DataResponse",

    # Database utilities
    "DatabaseExceptionHandler",
    "DatabaseErrorDecorator",
    "handle_database_errors",
    # Database transaction functions removed - use FastAPI dependency injection

    # Generic utilities
    "generate_uuid",
    "to_snake_case",
    "to_pascal_case",

    # Response utilities
    "create_data_response",
    "create_paginated_response",
    "create_empty_data_response",
    "create_success_response",
    "create_list_response",
    "StandardResponseMixin",
]
