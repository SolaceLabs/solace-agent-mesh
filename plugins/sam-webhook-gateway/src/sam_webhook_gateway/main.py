"""
Defines the FastAPI application instance for the Universal Webhook Gateway,
mounts routers (if any static ones are needed), and configures middleware.
"""

from fastapi import (
    FastAPI,
    Request as FastAPIRequest,
    HTTPException,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from solace_ai_connector.common.log import log

from .dependencies import set_component_instance

from solace_agent_mesh.common.types import (
    JSONRPCError,
    InternalError,
    InvalidRequestError,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .component import WebhookGatewayComponent

app = FastAPI(
    title="Universal Webhook Gateway",
    version="0.1.0",
    description="HTTP/S Webhook Gateway for the Solace AI Connector, enabling A2A task initiation from external systems.",
)


def setup_dependencies(component: "WebhookGatewayComponent"):
    """
    Sets up the component instance reference and configures middleware and routers
    that depend on the component being available.
    Called from the component's startup sequence.
    """
    log.info(
        "[%s] Setting up FastAPI dependencies, middleware, and routers...",
        component.log_identifier,
    )
    set_component_instance(component)
    allowed_origins = component.cors_allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info(
        "[%s] CORSMiddleware added with origins: %s",
        component.log_identifier,
        allowed_origins,
    )

    log.info("[%s] FastAPI setup complete.", component.log_identifier)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: FastAPIRequest, exc: HTTPException):
    """Handles FastAPI's built-in HTTPExceptions and formats them as JSONRPC-like errors."""
    log.warning(
        "HTTP Exception: Status=%s, Detail=%s, Request: %s %s",
        exc.status_code,
        exc.detail,
        request.method,
        request.url,
    )
    error_data = None
    error_code = InternalError().code
    error_message = str(exc.detail)

    if isinstance(exc.detail, dict):
        if "code" in exc.detail and "message" in exc.detail:
            error_code = exc.detail["code"]
            error_message = exc.detail["message"]
            error_data = exc.detail.get("data")
        else:
            error_data = exc.detail
    elif isinstance(exc.detail, str):
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            error_code = InvalidRequestError().code
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = -32000
            error_message = "Authentication required"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = -32000
            error_message = "Forbidden"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = -32601
            error_message = "Webhook endpoint not found"

    error_obj = JSONRPCError(code=error_code, message=error_message, data=error_data)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_obj.model_dump(exclude_none=True)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: FastAPIRequest, exc: RequestValidationError
):
    """Handles Pydantic validation errors (422) and formats them."""
    log.warning(
        "Request Validation Error: %s, Request: %s %s",
        exc.errors(),
        request.method,
        request.url,
    )
    error_obj = InvalidRequestError(
        message="Invalid request parameters", data=exc.errors()
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": error_obj.model_dump(exclude_none=True)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: FastAPIRequest, exc: Exception):
    """Handles any other unexpected exceptions."""
    log.exception(
        "Unhandled Exception: %s, Request: %s %s", exc, request.method, request.url
    )
    error_obj = InternalError(
        code=InternalError().code,
        message="An unexpected server error occurred: %s" % type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": error_obj.model_dump(exclude_none=True)},
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint for the Webhook Gateway."""
    log.debug("Health check endpoint '/health' called")
    return {"status": "Universal Webhook Gateway is running"}


log.info(
    "FastAPI application instance created for Webhook Gateway (endpoints/middleware setup deferred until component startup)."
)
