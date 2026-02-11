"""
Generic FastAPI exception handlers for consistent HTTP error responses.

This module provides FastAPI exception handlers that convert domain exceptions
into appropriate HTTP responses with consistent formatting. These handlers
can be used by any FastAPI application for uniform error handling.
"""

import logging

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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
)
from .error_dto import EventErrorDTO

log = logging.getLogger(__name__)


def create_error_response(
    status_code: int, message: str, validation_details: dict = None
) -> JSONResponse:
    """Create standardized error response using EventErrorDTO format."""
    if validation_details:
        error_dto = EventErrorDTO.validation_error(message, validation_details)
    else:
        error_dto = EventErrorDTO.create(message)

    return JSONResponse(status_code=status_code, content=error_dto.model_dump())


async def validation_error_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle domain validation errors - 422 Unprocessable Entity."""
    if exc.validation_details:
        error_dto = EventErrorDTO.validation_error(exc.message, exc.validation_details)
    else:
        error_dto = EventErrorDTO.create("bad request" if not exc.message else exc.message)

    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_dto.model_dump())


async def entity_not_found_handler(
    request: Request, exc: EntityNotFoundError
) -> JSONResponse:
    """Handle entity not found errors - 404 Not Found."""
    # Format: "Could not find applicationDomain with id: some-invalid-id"
    message = f"Could not find {exc.entity_type} with id: {exc.entity_id}"
    error_dto = EventErrorDTO.create(message)
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error_dto.model_dump())


async def entity_already_exists_handler(
    request: Request, exc: EntityAlreadyExistsError
) -> JSONResponse:
    """Handle entity already exists errors - 409 Conflict."""
    error_dto = EventErrorDTO.create(exc.message)
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=error_dto.model_dump())


async def business_rule_violation_handler(
    request: Request, exc: BusinessRuleViolationError
) -> JSONResponse:
    """Handle business rule violations - 422 Unprocessable Entity."""
    error_dto = EventErrorDTO.create(exc.message)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_dto.model_dump())


async def configuration_error_handler(
    request: Request, exc: ConfigurationError
) -> JSONResponse:
    """Handle configuration errors - 500 Internal Server Error."""
    error_dto = EventErrorDTO.create("An unexpected server error occurred.")
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_dto.model_dump())


async def data_integrity_error_handler(
    request: Request, exc: DataIntegrityError
) -> JSONResponse:
    """Handle data integrity errors - 422 Unprocessable Entity."""
    # Format: "An entity of type applicationDomain was passed in an invalid format"
    message = f"An entity of type {exc.entity_type} was passed in an invalid format" if hasattr(exc, 'entity_type') else "bad request"
    error_dto = EventErrorDTO.create(message)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_dto.model_dump())


async def external_service_error_handler(
    request: Request, exc: ExternalServiceError
) -> JSONResponse:
    """Handle external service errors - 503 Service Unavailable."""
    error_dto = EventErrorDTO.create("Service is unavailable.")
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=error_dto.model_dump())


async def internal_service_error_handler(
    request: Request, exc: InternalServiceError
) -> JSONResponse:
    """Handle unexpected internal errors - 500 Internal Server Error."""
    log.error(
        "InternalServiceError: %s",
        exc.message,
        extra={"path": request.url.path, "method": request.method},
        exc_info=True
    )
    error_dto = EventErrorDTO.create("An unexpected error occurred.")
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_dto.model_dump())


async def webui_backend_exception_handler(
    request: Request, exc: WebUIBackendException
) -> JSONResponse:
    """Handle generic WebUI backend exceptions - 500 Internal Server Error."""
    log.error(
        f"WebUIBackendException: {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "details": exc.details if hasattr(exc, 'details') else None
        },
        exc_info=True
    )

    message = exc.message if exc.message else "An unexpected server error occurred."
    error_dto = EventErrorDTO.create(message)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_dto.model_dump())


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Handle FastAPI HTTPExceptions with standardized format."""
    # Map common HTTP status codes to standard messages (only used as fallback)
    message_map = {
        401: "An authentication error occurred. Try logging out and in again.",
        403: "You do not have permissions to perform this operation",
        404: f"Resource not found with path {request.url.path}",
        405: f"Request method '{request.method}' is not supported",
        406: "Unacceptable Content-type.",
        429: "Rate limit exceeded message here",
        500: "An unexpected server error occurred.",
        501: "Not Implemented",
        503: "Service is unavailable.",
    }

    message = exc.detail if exc.detail else message_map.get(exc.status_code, "bad request")
    error_dto = EventErrorDTO.create(message)
    return JSONResponse(status_code=exc.status_code, content=error_dto.model_dump())


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI request validation errors - 422 Unprocessable Entity."""
    validation_details = {}
    for error in exc.errors():
        field_path = ".".join(str(x) for x in error["loc"] if x != "body")
        if field_path not in validation_details:
            validation_details[field_path] = []
        validation_details[field_path].append(error["msg"])

    if validation_details:
        message = "body must not be empty" if not validation_details else "Validation error"
        error_dto = EventErrorDTO.validation_error(message, validation_details)
    else:
        error_dto = EventErrorDTO.create("bad request")

    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_dto.model_dump())


async def pydantic_validation_exception_handler(
    request: Request, exc: PydanticValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors raised in service layer - 422 Unprocessable Entity."""
    validation_details = {}
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        if field_path not in validation_details:
            validation_details[field_path] = []
        validation_details[field_path].append(error["msg"])

    error_dto = EventErrorDTO.validation_error("Validation failed", validation_details)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_dto.model_dump())


def register_exception_handlers(app):
    """
    Register all exception handlers with a FastAPI app.

    This function registers all the generic exception handlers, providing
    consistent error responses across the entire application.

    Args:
        app: FastAPI application instance

    Example:
        from fastapi import FastAPI
        from solace_agent_mesh.shared.exceptions.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)
    """
    # Domain exception handlers
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
    app.add_exception_handler(EntityAlreadyExistsError, entity_already_exists_handler)
    app.add_exception_handler(
        BusinessRuleViolationError, business_rule_violation_handler
    )
    app.add_exception_handler(ConfigurationError, configuration_error_handler)
    app.add_exception_handler(DataIntegrityError, data_integrity_error_handler)
    app.add_exception_handler(ExternalServiceError, external_service_error_handler)
    app.add_exception_handler(InternalServiceError, internal_service_error_handler)
    app.add_exception_handler(WebUIBackendException, webui_backend_exception_handler)

    # FastAPI built-in exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_validation_exception_handler)
