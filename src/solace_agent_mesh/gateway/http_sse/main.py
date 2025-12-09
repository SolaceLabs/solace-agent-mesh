import logging
import os
from pathlib import Path

import httpx
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from typing import TYPE_CHECKING

from a2a.types import InternalError, InvalidRequestError, JSONRPCError
from a2a.types import JSONRPCResponse as A2AJSONRPCResponse

from ...common import a2a
from ...gateway.http_sse import dependencies
from ...shared.auth.middleware import create_oauth_middleware
from .routers import (
    agent_cards,
    artifacts,
    auth,
    config,
    feedback,
    people,
    sse,
    speech,
    version,
    visualization,
    projects,
    prompts,
)
from .routers.sessions import router as session_router
from .routers.tasks import router as task_router
from .routers.users import router as user_router


if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)

app = FastAPI(
    title="A2A Web UI Backend",
    version="1.0.0",  # Updated to reflect simplified architecture
    description="Backend API and SSE server for the A2A Web UI, hosted by Solace AI Connector.",
)

# Global flag to track if dependencies have been initialized
_dependencies_initialized = False


def _extract_access_token(request: FastAPIRequest) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    try:
        if "access_token" in request.session:
            log.debug("AuthMiddleware: Found token in session.")
            return request.session["access_token"]
    except AssertionError:
        log.debug("AuthMiddleware: Could not access request.session.")

    if "token" in request.query_params:
        return request.query_params["token"]

    return None


async def _validate_token(
    auth_service_url: str, auth_provider: str, access_token: str
) -> bool:
    async with httpx.AsyncClient() as client:
        validation_response = await client.post(
            f"{auth_service_url}/is_token_valid",
            json={"provider": auth_provider},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return validation_response.status_code == 200


async def _get_user_info(
    auth_service_url: str, auth_provider: str, access_token: str
) -> dict:
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            f"{auth_service_url}/user_info?provider={auth_provider}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.status_code != 200:
        return None

    return userinfo_response.json()


def _extract_user_identifier(user_info: dict) -> str:
    user_identifier = (
        user_info.get("sub")
        or user_info.get("client_id")
        or user_info.get("username")
        or user_info.get("oid")
        or user_info.get("preferred_username")
        or user_info.get("upn")
        or user_info.get("unique_name")
        or user_info.get("email")
        or user_info.get("name")
        or user_info.get("azp")
        or user_info.get("user_id") # internal /user_info endpoint format maps identifier to user_id
    )

    if user_identifier and user_identifier.lower() == "unknown":
        log.warning(
            "AuthMiddleware: IDP returned 'Unknown' as user identifier. Using fallback."
        )
        return "sam_dev_user"

    return user_identifier


def _extract_user_details(user_info: dict, user_identifier: str) -> tuple:
    email_from_auth = (
        user_info.get("email")
        or user_info.get("preferred_username")
        or user_info.get("upn")
        or user_identifier
    )

    display_name = (
        user_info.get("name")
        or user_info.get("given_name", "") + " " + user_info.get("family_name", "")
        or user_info.get("preferred_username")
        or user_identifier
    ).strip()

    return email_from_auth, display_name


async def _create_user_state_without_identity_service(
    user_identifier: str, email_from_auth: str, display_name: str
) -> dict:
    final_user_id = user_identifier or email_from_auth or "sam_dev_user"
    if not final_user_id or final_user_id.lower() in ["unknown", "null", "none", ""]:
        final_user_id = "sam_dev_user"
        log.warning(
            "AuthMiddleware: Had to use fallback user ID due to invalid identifier: %s",
            user_identifier,
        )

    log.debug(
        "AuthMiddleware: Internal IdentityService not configured on component. Using user ID: %s",
        final_user_id,
    )
    return {
        "id": final_user_id,
        "email": email_from_auth or final_user_id,
        "name": display_name or final_user_id,
        "authenticated": True,
        "auth_method": "oidc",
    }


async def _create_user_state_with_identity_service(
    identity_service,
    user_identifier: str,
    email_from_auth: str,
    display_name: str,
    user_info: dict,
) -> dict:
    lookup_value = email_from_auth if "@" in email_from_auth else user_identifier
    user_profile = await identity_service.get_user_profile(
        {identity_service.lookup_key: lookup_value, "user_info": user_info}
    )

    if not user_profile:
        return None

    user_state = user_profile.copy()
    if not user_state.get("id"):
        user_state["id"] = user_identifier
    if not user_state.get("email"):
        user_state["email"] = email_from_auth
    if not user_state.get("name"):
        user_state["name"] = display_name
    user_state["authenticated"] = True
    user_state["auth_method"] = "oidc"

    return user_state

def setup_dependencies(
    component: "WebUIBackendComponent",
    database_url: str = None,
):
    """
    Initialize dependencies for WebUI Gateway (chat only).

    Args:
        component: WebUIBackendComponent instance
        database_url: Chat database URL (sessions, tasks, feedback).
                     If None, runs in compatibility mode with in-memory sessions.

    This function is idempotent and safe to call multiple times.
    """
    global _dependencies_initialized

    if _dependencies_initialized:
        log.debug("[setup_dependencies] Dependencies already initialized, skipping")
        return

    dependencies.set_component_instance(component)

    if database_url:
        _setup_database(component, database_url)
    else:
        log.warning(
            "No database URL provided - using in-memory session storage (data not persisted across restarts)"
        )
        log.info("This maintains backward compatibility for existing SAM installations")

    app_config = _get_app_config(component)
    api_config_dict = _create_api_config(app_config, database_url)

    dependencies.set_api_config(api_config_dict)
    log.debug("API configuration extracted and stored.")

    _setup_middleware(component)
    _setup_routers()
    _setup_static_files()

    _dependencies_initialized = True
    log.debug("[setup_dependencies] Dependencies initialization complete")


def _setup_middleware(component: "WebUIBackendComponent") -> None:
    allowed_origins = component.get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info("CORSMiddleware added with origins: %s", allowed_origins)

    session_manager = component.get_session_manager()
    app.add_middleware(SessionMiddleware, secret_key=session_manager.secret_key)
    log.info("SessionMiddleware added.")

    auth_middleware_class = create_oauth_middleware(component)
    app.add_middleware(auth_middleware_class, component=component)

    if component.use_authorization:
        log.info("OAuth middleware added (real token validation enabled)")
    else:
        log.info("OAuth middleware added (development mode - community/dev user)")


def _setup_routers() -> None:
    api_prefix = "/api/v1"

    app.include_router(session_router, prefix=api_prefix, tags=["Sessions"])
    app.include_router(user_router, prefix=f"{api_prefix}/users", tags=["Users"])
    app.include_router(config.router, prefix=api_prefix, tags=["Config"])
    app.include_router(version.router, prefix=api_prefix, tags=["Version"])
    app.include_router(agent_cards.router, prefix=api_prefix, tags=["Agent Cards"])
    app.include_router(task_router, prefix=api_prefix, tags=["Tasks"])
    app.include_router(sse.router, prefix=f"{api_prefix}/sse", tags=["SSE"])
    app.include_router(
        artifacts.router, prefix=f"{api_prefix}/artifacts", tags=["Artifacts"]
    )
    app.include_router(
        visualization.router,
        prefix=f"{api_prefix}/visualization",
        tags=["Visualization"],
    )
    app.include_router(people.router, prefix=api_prefix, tags=["People"])
    app.include_router(auth.router, prefix=api_prefix, tags=["Auth"])
    app.include_router(projects.router, prefix=api_prefix, tags=["Projects"])
    app.include_router(feedback.router, prefix=api_prefix, tags=["Feedback"])
    app.include_router(prompts.router, prefix=f"{api_prefix}/prompts", tags=["Prompts"])
    app.include_router(speech.router, prefix=f"{api_prefix}/speech", tags=["Speech"])
    log.info("Legacy routers mounted for endpoints not yet migrated")

    # Register shared exception handlers
    from solace_agent_mesh.shared.exceptions.exception_handlers import register_exception_handlers

    register_exception_handlers(app)
    log.info("Registered shared exception handlers")


def _setup_static_files() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = Path(os.path.normpath(os.path.join(current_dir, "..", "..")))
    static_files_dir = Path.joinpath(root_dir, "client", "webui", "frontend", "static")

    if not os.path.isdir(static_files_dir):
        log.warning(
            "Static files directory '%s' not found. Frontend may not be served.",
            static_files_dir,
        )
    # try to mount static files directory anyways, might work for enterprise
    try:
        app.mount(
            "/", StaticFiles(directory=static_files_dir, html=True), name="static"
        )
        log.info("Mounted static files directory '%s' at '/'", static_files_dir)
    except Exception as static_mount_err:
        log.error(
            "Failed to mount static files directory '%s': %s",
            static_files_dir,
            static_mount_err,
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: FastAPIRequest, exc: HTTPException):
    """
    HTTP exception handler with automatic format detection.
    Returns JSON-RPC format for tasks/SSE endpoints, REST format for others.
    """
    log.warning(
        "HTTP Exception Handler triggered: Status=%s, Detail=%s, Request: %s %s",
        exc.status_code,
        exc.detail,
        request.method,
        request.url,
    )

    # Check if this is a JSON-RPC endpoint (tasks and SSE endpoints use JSON-RPC)
    is_jsonrpc_endpoint = request.url.path.startswith(
        "/api/v1/tasks"
    ) or request.url.path.startswith("/api/v1/sse")

    if is_jsonrpc_endpoint:
        # Use JSON-RPC format for tasks and SSE endpoints
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
                error_code = -32600
            elif exc.status_code == status.HTTP_404_NOT_FOUND:
                error_code = -32601
                error_message = "Resource not found"

        error_obj = JSONRPCError(
            code=error_code, message=error_message, data=error_data
        )
        response = A2AJSONRPCResponse(error=error_obj)
        return JSONResponse(
            status_code=exc.status_code, content=response.model_dump(exclude_none=True)
        )
    else:
        # Use standard REST format for sessions and other REST endpoints
        if isinstance(exc.detail, dict):
            error_response = exc.detail
        elif isinstance(exc.detail, str):
            error_response = {"detail": exc.detail}
        else:
            error_response = {"detail": str(exc.detail)}

        return JSONResponse(status_code=exc.status_code, content=error_response)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: FastAPIRequest, exc: RequestValidationError
):
    """
    Handles Pydantic validation errors with format detection.
    """
    log.warning(
        "Validation Exception Handler triggered: %s, Request: %s %s",
        exc.errors(),
        request.method,
        request.url,
    )
    response = a2a.create_invalid_request_error_response(
        message="Invalid request parameters", data=exc.errors(), request_id=None
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(exclude_none=True),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: FastAPIRequest, exc: Exception):
    """
    Handles any other unexpected exceptions with format detection.
    """
    log.exception(
        "Generic Exception Handler triggered: %s, Request: %s %s",
        exc,
        request.method,
        request.url,
    )
    error_obj = a2a.create_internal_error(
        message="An unexpected server error occurred: %s" % type(exc).__name__
    )
    response = a2a.create_error_response(error=error_obj, request_id=None)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(exclude_none=True),
    )


@app.get("/health", tags=["Health"])
async def read_root():
    """Basic health check endpoint."""
    log.debug("Health check endpoint '/health' called")
    return {"status": "A2A Web UI Backend is running"}
