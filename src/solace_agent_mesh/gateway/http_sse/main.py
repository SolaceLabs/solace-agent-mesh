import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import sqlalchemy as sa
from a2a.types import InternalError, JSONRPCError
from a2a.types import JSONRPCResponse as A2AJSONRPCResponse
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, status
from fastapi import Request as FastAPIRequest
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from solace_ai_connector.common.log import log
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from ...common import a2a
from ...gateway.http_sse import dependencies
from ...gateway.http_sse.routers import (
    agents,
    artifacts,
    auth,
    config,
    people,
    sse,
    tasks,
    visualization,
)

# Import persistence-aware controllers
from .api.controllers.session_controller import router as session_router
from .api.controllers.task_controller import router as task_router
from .api.controllers.user_controller import router as user_router
from .infrastructure.persistence.database_service import DatabaseService

if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

app = FastAPI(
    title="A2A Web UI Backend",
    version="1.0.0",  # Updated to reflect simplified architecture
    description="Backend API and SSE server for the A2A Web UI, hosted by Solace AI Connector.",
)


def setup_dependencies(component: "WebUIBackendComponent", persistence_service=None):
    """
    This function initializes the modern architecture while maintaining full
    backward compatibility with existing API contracts.

    If persistence_service is None, runs in compatibility mode with in-memory sessions.
    """

    if persistence_service:
        database_url = persistence_service.engine.url.__str__()
        global database_service
        database_service = DatabaseService(database_url)
        log.info("Database service initialized")

        from .infrastructure.dependency_injection.container import initialize_container

        initialize_container(database_url)
        log.info("Persistence enabled - sessions will be stored in database")
    else:
        from .infrastructure.dependency_injection.container import initialize_container

        initialize_container()
        log.warning(
            "No persistence service provided - using in-memory session storage (data not persisted across restarts)"
        )
        log.info("This maintains backward compatibility for existing SAM installations")

    dependencies.set_component_instance(component)

    if persistence_service:
        log.info("Checking database migrations...")
        try:
            inspector = sa.inspect(persistence_service.engine)
            existing_tables = inspector.get_table_names()

            if not existing_tables or "sessions" not in existing_tables:
                log.info("Running database migrations...")
                alembic_cfg = Config()
                alembic_cfg.set_main_option(
                    "script_location",
                    os.path.join(os.path.dirname(__file__), "alembic"),
                )
                alembic_cfg.set_main_option("sqlalchemy.url", database_url)
                command.upgrade(alembic_cfg, "head")
                log.info("Database migrations complete.")
            else:
                log.info("Database tables already exist, skipping migrations.")
        except Exception as e:
            log.warning(
                f"Migration check failed, attempting to run migrations anyway: {e}"
            )
            try:
                alembic_cfg = Config()
                alembic_cfg.set_main_option(
                    "script_location",
                    os.path.join(os.path.dirname(__file__), "alembic"),
                )
                alembic_cfg.set_main_option("sqlalchemy.url", database_url)
                command.upgrade(alembic_cfg, "head")
                log.info("Database migrations complete.")
            except Exception as migration_error:
                log.warning(f"Migration failed but continuing: {migration_error}")

        dependencies.set_persistence_service(persistence_service)
    else:
        log.info("Skipping database migrations - no persistence service configured")

    webui_app = component.get_app()
    app_config = {}
    if webui_app:
        app_config = getattr(webui_app, "app_config", {})
        if app_config is None:
            log.warning("webui_app.app_config is None, using empty dict.")
            app_config = {}
    else:
        log.warning("Could not get webui_app from component. Using empty app_config.")

    api_config_dict = {
        "external_auth_service_url": app_config.get(
            "external_auth_service_url", "http://localhost:8080"
        ),
        "external_auth_callback_uri": app_config.get(
            "external_auth_callback_uri", "http://localhost:8000/api/v1/auth/callback"
        ),
        "external_auth_provider": app_config.get("external_auth_provider", "azure"),
        "frontend_use_authorization": app_config.get(
            "frontend_use_authorization", False
        ),
        "frontend_redirect_url": app_config.get(
            "frontend_redirect_url", "http://localhost:3000"
        ),
        "persistence_enabled": persistence_service is not None,
    }

    dependencies.set_api_config(api_config_dict)
    log.info("API configuration extracted and stored.")

    class AuthMiddleware:
        def __init__(self, app, component):
            self.app = app
            self.component = component

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            request = FastAPIRequest(scope, receive)

            if not request.url.path.startswith("/api"):
                await self.app(scope, receive, send)
                return

            skip_paths = [
                "/api/v1/config",
                "/api/v1/auth/callback",
                "/api/v1/auth/login",
                "/api/v1/auth/refresh",
                "/api/v1/csrf-token",
                "/health",
            ]

            if any(request.url.path.startswith(path) for path in skip_paths):
                await self.app(scope, receive, send)
                return

            use_auth = dependencies.api_config and dependencies.api_config.get(
                "frontend_use_authorization"
            )

            if use_auth:
                access_token = None
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    access_token = auth_header[7:]

                if not access_token:
                    try:
                        if "access_token" in request.session:
                            access_token = request.session["access_token"]
                            log.debug("AuthMiddleware: Found token in session.")
                    except AssertionError:
                        log.debug("AuthMiddleware: Could not access request.session.")
                        pass

                if not access_token:
                    if "token" in request.query_params:
                        access_token = request.query_params["token"]

                if not access_token:
                    log.warning("AuthMiddleware: No access token found. Returning 401.")
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "detail": "Not authenticated",
                            "error_type": "authentication_required",
                        },
                    )
                    await response(scope, receive, send)
                    return

                try:
                    auth_service_url = dependencies.api_config.get(
                        "external_auth_service_url"
                    )
                    auth_provider = dependencies.api_config.get(
                        "external_auth_provider"
                    )

                    if not auth_service_url:
                        log.error("Auth service URL not configured.")
                        response = JSONResponse(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            content={"detail": "Auth service not configured"},
                        )
                        await response(scope, receive, send)
                        return

                    async with httpx.AsyncClient() as client:
                        validation_response = await client.post(
                            f"{auth_service_url}/is_token_valid",
                            json={"provider": auth_provider},
                            headers={"Authorization": f"Bearer {access_token}"},
                        )

                    if validation_response.status_code != 200:
                        log.warning(
                            "AuthMiddleware: Token validation failed with status %s: %s",
                            validation_response.status_code,
                            validation_response.text,
                        )
                        response = JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Invalid token",
                                "error_type": "invalid_token",
                            },
                        )
                        await response(scope, receive, send)
                        return

                    async with httpx.AsyncClient() as client:
                        userinfo_response = await client.get(
                            f"{auth_service_url}/user_info?provider={auth_provider}",
                            headers={"Authorization": f"Bearer {access_token}"},
                        )

                    if userinfo_response.status_code != 200:
                        log.warning(
                            "AuthMiddleware: Failed to get user info from external auth service: %s",
                            userinfo_response.status_code,
                        )
                        response = JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "Could not retrieve user info from auth provider",
                                "error_type": "user_info_failed",
                            },
                        )
                        await response(scope, receive, send)
                        return

                    user_info = userinfo_response.json()
                    log.info(
                        "AuthMiddleware: Raw user info from OAuth provider: %s",
                        user_info,
                    )

                    # Priority order for user identifier (most specific to least specific)
                    user_identifier = (
                        user_info.get("sub")  # Standard OIDC subject claim
                        or user_info.get("client_id")  # Mini IDP and some custom IDPs
                        or user_info.get("username")  # Mini IDP returns username field
                        or user_info.get("oid")  # Azure AD object ID
                        or user_info.get(
                            "preferred_username"
                        )  # Common in enterprise IDPs
                        or user_info.get("upn")  # Azure AD User Principal Name
                        or user_info.get("unique_name")  # Some Azure configurations
                        or user_info.get("email")  # Fallback to email
                        or user_info.get("name")  # Last resort
                        or user_info.get("azp")  # Authorized party (rare but possible)
                    )

                    # IMPORTANT: If the extracted identifier is "Unknown", it means the IDP
                    # didn't properly authenticate or is misconfigured. Use a fallback.
                    if user_identifier and user_identifier.lower() == "unknown":
                        log.warning(
                            "AuthMiddleware: IDP returned 'Unknown' as user identifier. This indicates misconfiguration. Using fallback."
                        )
                        # In development mode with mini IDP, default to sam_dev_user
                        # This is a workaround for the OAuth2 proxy service returning "Unknown"
                        user_identifier = "sam_dev_user"  # Fallback for development
                        log.info(
                            "AuthMiddleware: Using development fallback user: sam_dev_user"
                        )

                    # Extract email separately (may be different from user identifier)
                    email_from_auth = (
                        user_info.get("email")
                        or user_info.get("preferred_username")
                        or user_info.get("upn")
                        or user_identifier
                    )

                    # Extract display name
                    display_name = (
                        user_info.get("name")
                        or user_info.get("given_name", "")
                        + " "
                        + user_info.get("family_name", "")
                        or user_info.get("preferred_username")
                        or user_identifier
                    ).strip()

                    log.info(
                        "AuthMiddleware: Extracted user identifier: %s, email: %s, name: %s",
                        user_identifier,
                        email_from_auth,
                        display_name,
                    )

                    if not user_identifier or user_identifier.lower() in [
                        "null",
                        "none",
                        "",
                    ]:
                        log.error(
                            "AuthMiddleware: No valid user identifier from OAuth provider. Full user info: %s. Expected valid user identifier.",
                            user_info,
                        )
                        response = JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "OAuth provider returned no valid user identifier. Provider must return at least one of: sub, username, client_id, preferred_username, email, or name field.",
                                "error_type": "invalid_user_identifier_from_provider",
                                "received_user_info": user_info,
                            },
                        )
                        await response(scope, receive, send)
                        return

                    identity_service = self.component.identity_service
                    if not identity_service:
                        # Make absolutely sure we have a valid user ID - never "Unknown"
                        final_user_id = (
                            user_identifier or email_from_auth or "sam_dev_user"
                        )
                        if not final_user_id or final_user_id.lower() in [
                            "unknown",
                            "null",
                            "none",
                            "",
                        ]:
                            final_user_id = "sam_dev_user"
                            log.warning(
                                "AuthMiddleware: Had to use fallback user ID due to invalid identifier: %s",
                                user_identifier,
                            )

                        log.error(
                            "AuthMiddleware: Internal IdentityService not configured on component. Using user ID: %s",
                            final_user_id,
                        )
                        request.state.user = {
                            "id": final_user_id,
                            "email": email_from_auth or final_user_id,
                            "name": display_name or final_user_id,
                            "authenticated": True,
                            "auth_method": "oidc",
                        }
                        log.info(
                            "AuthMiddleware: Set fallback user state with id: %s",
                            final_user_id,
                        )
                    else:
                        # Try to look up user profile using the email or user identifier
                        lookup_value = (
                            email_from_auth
                            if "@" in email_from_auth
                            else user_identifier
                        )
                        user_profile = await identity_service.get_user_profile(
                            {identity_service.lookup_key: lookup_value}
                        )
                        if not user_profile:
                            log.error(
                                "AuthMiddleware: User '%s' authenticated but not found in internal IdentityService.",
                                lookup_value,
                            )
                            response = JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={
                                    "detail": "User not authorized for this application",
                                    "error_type": "not_authorized",
                                },
                            )
                            await response(scope, receive, send)
                            return

                        request.state.user = user_profile.copy()
                        # Ensure the ID is set from the OAuth provider if not present in the profile
                        if not request.state.user.get("id"):
                            request.state.user["id"] = user_identifier
                        # Also ensure email and name are set if not in profile
                        if not request.state.user.get("email"):
                            request.state.user["email"] = email_from_auth
                        if not request.state.user.get("name"):
                            request.state.user["name"] = display_name
                        request.state.user["authenticated"] = True
                        request.state.user["auth_method"] = "oidc"
                        log.info(
                            "AuthMiddleware: Set enriched user profile with id: %s",
                            request.state.user.get("id"),
                        )

                except httpx.RequestError as exc:
                    log.error("Error calling auth service: %s", exc)
                    response = JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": "Auth service is unavailable"},
                    )
                    await response(scope, receive, send)
                    return
                except Exception as exc:
                    log.error(
                        "An unexpected error occurred during token validation: %s", exc
                    )
                    response = JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "detail": "An internal error occurred during authentication"
                        },
                    )
                    await response(scope, receive, send)
                    return
            else:
                # If auth is not used, set a default user
                request.state.user = {
                    "id": "sam_dev_user",
                    "name": "Sam Dev User",
                    "email": "sam@dev.local",
                    "authenticated": True,
                    "auth_method": "development",
                }
                log.debug(
                    "AuthMiddleware: Set development user state with id: sam_dev_user"
                )

            await self.app(scope, receive, send)

    # Add middleware
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

    app.add_middleware(AuthMiddleware, component=component)
    log.info("AuthMiddleware added.")

    # Mount API routers
    api_prefix = "/api/v1"

    # Mount persistence-aware controllers (your original controllers with full functionality)
    # These provide the complete API surface with database persistence
    app.include_router(
        session_router, prefix=api_prefix, tags=["Sessions"]
    )  # Provides /api/v1/sessions/* endpoints
    app.include_router(
        user_router, prefix=f"{api_prefix}/users", tags=["Users"]
    )  # Provides /api/v1/users/me
    app.include_router(
        task_router, prefix=f"{api_prefix}/tasks", tags=["Tasks"]
    )  # Provides /api/v1/tasks/send, /subscribe, /cancel

    # Mount new A2A SDK routers with different paths to avoid conflicts
    app.include_router(config.router, prefix=api_prefix, tags=["Config"])
    app.include_router(agents.router, prefix=api_prefix, tags=["Agents"])
    # New A2A message endpoints (non-conflicting paths)
    app.include_router(
        tasks.router, prefix=api_prefix, tags=["A2A Messages"]
    )  # Provides /api/v1/message:send, /message:stream
    # Note: We only use the full-featured session_router (from api/controllers/session_controller.py)
    # which provides complete session management with database persistence
    app.include_router(sse.router, prefix=f"{api_prefix}/sse", tags=["SSE"])
    app.include_router(
        artifacts.router, prefix=f"{api_prefix}/artifacts", tags=["Artifacts"]
    )
    app.include_router(
        visualization.router,
        prefix=f"{api_prefix}/visualization",
        tags=["Visualization"],
    )
    app.include_router(
        people.router,
        prefix=api_prefix,
        tags=["People"],
    )
    app.include_router(auth.router, prefix=api_prefix, tags=["Auth"])
    log.info("Legacy routers mounted for endpoints not yet migrated")

    # Mount static files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = Path(os.path.normpath(os.path.join(current_dir, "..", "..")))
    static_files_dir = Path.joinpath(root_dir, "client", "webui", "frontend", "static")
    if not os.path.isdir(static_files_dir):
        log.warning(
            "Static files directory '%s' not found. Frontend may not be served.",
            static_files_dir,
        )
    else:
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
        "HTTP Exception: Status=%s, Detail=%s, Request: %s %s",
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
        "Request Validation Error: %s, Request: %s %s",
        exc.errors(),
        request.method,
        request.url,
    )
    response = a2a.create_invalid_request_error_response(
        message="Invalid request parameters", data=exc.errors(), request_id=None
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(exclude_none=True),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: FastAPIRequest, exc: Exception):
    """
    Handles any other unexpected exceptions with format detection.
    """
    log.exception(
        "Unhandled Exception: %s, Request: %s %s", exc, request.method, request.url
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
