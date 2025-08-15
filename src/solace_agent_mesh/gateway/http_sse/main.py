"""
FastAPI application using the 3-tiered architecture pattern.

This application implements clean separation of concerns with:
- Presentation Layer: Controllers handle HTTP requests/responses
- Business Layer: Services contain business logic
- Data Layer: Repositories handle data access

All API endpoints maintain backward compatibility while using modern architecture patterns.
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
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
import os
from pathlib import Path
import httpx
import sqlalchemy as sa

from solace_ai_connector.common.log import log

# Import new 3-tiered architecture components
from .api.controllers import session_router, user_router, task_router
from .data.persistence.database_service import DatabaseService

# Global database service instance
database_service: DatabaseService = None

# Import remaining routers that haven't been migrated to new architecture yet
from ...gateway.http_sse.routers import (
    agents,
    sse,
    config,
    artifacts,
    visualization,
    people,
    auth,
)

from ...gateway.http_sse import dependencies
from ...common.types import (
    JSONRPCResponse as A2AJSONRPCResponse,
    JSONRPCError,
    InternalError,
    InvalidRequestError,
)

from alembic.config import Config
from alembic import command
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

app = FastAPI(
    title="A2A Web UI Backend",
    version="1.0.0",  # Updated to reflect simplified architecture
    description="Backend API and SSE server for the A2A Web UI using 3-tiered architecture, hosted by Solace AI Connector.",
)


def setup_dependencies(component: "WebUIBackendComponent", persistence_service):
    """
    Setup function using 3-tiered architecture with dependency injection.
    
    This function initializes the modern architecture while maintaining full
    backward compatibility with existing API contracts.
    """
    log.info("Setting up FastAPI dependencies with 3-tiered architecture...")
    
    # Initialize database service for new architecture
    database_url = persistence_service.engine.url.__str__()
    global database_service
    database_service = DatabaseService(database_url)
    log.info("Database service initialized")
    
    # Set up existing component dependencies for backward compatibility
    dependencies.set_component_instance(component)
    
    # Run database migrations (only if needed)
    log.info("Checking database migrations...")
    try:
        # Check if tables already exist (common in test environments)
        inspector = sa.inspect(persistence_service.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables or "users" not in existing_tables:
            # Tables don't exist, run migrations
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
        log.warning(f"Migration check failed, attempting to run migrations anyway: {e}")
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
    
    # Set persistence service for backward compatibility with non-migrated routers
    dependencies.set_persistence_service(persistence_service)

    # Extract and set API configuration
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
    }

    dependencies.set_api_config(api_config_dict)
    log.info("API configuration extracted and stored.")

    # Authentication middleware
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
                    email_from_auth = user_info.get("email")

                    if not email_from_auth:
                        log.error(
                            "AuthMiddleware: Email not found in user info from external auth provider."
                        )
                        response = JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={
                                "detail": "User email not provided by auth provider",
                                "error_type": "email_missing",
                            },
                        )
                        await response(scope, receive, send)
                        return

                    identity_service = self.component.identity_service
                    if not identity_service:
                        log.error(
                            "AuthMiddleware: Internal IdentityService not configured on component. Falling back to using email as ID."
                        )
                        request.state.user = {
                            "id": email_from_auth,
                            "email": email_from_auth,
                            "name": user_info.get("name", email_from_auth),
                            "authenticated": True,
                            "auth_method": "oidc",
                        }
                    else:
                        user_profile = await identity_service.get_user_profile(
                            {identity_service.lookup_key: email_from_auth}
                        )
                        if not user_profile:
                            log.error(
                                "AuthMiddleware: User '%s' authenticated but not found in internal IdentityService.",
                                email_from_auth,
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
                        request.state.user["authenticated"] = True
                        request.state.user["auth_method"] = "oidc"
                        log.debug(
                            "AuthMiddleware: Enriched and stored user profile for id: %s",
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
    
    # Mount new 3-tiered architecture controllers
    app.include_router(session_router, prefix=api_prefix, tags=["Sessions"])
    app.include_router(user_router, prefix=f"{api_prefix}/users", tags=["Users"])
    app.include_router(task_router, prefix=f"{api_prefix}/tasks", tags=["Tasks"])
    log.info("3-tiered architecture controllers mounted")

    # Mount remaining routers that haven't been migrated yet
    app.include_router(config.router, prefix=api_prefix, tags=["Config"])
    app.include_router(agents.router, prefix=api_prefix, tags=["Agents"])
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

    log.info("FastAPI application setup complete with 3-tiered architecture")


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
    is_jsonrpc_endpoint = (
        request.url.path.startswith("/api/v1/tasks") or
        request.url.path.startswith("/api/v1/sse")
    )
    
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

        error_obj = JSONRPCError(code=error_code, message=error_message, data=error_data)
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
        
        return JSONResponse(
            status_code=exc.status_code, 
            content=error_response
        )


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
    
    # Check if this is a JSON-RPC endpoint
    is_jsonrpc_endpoint = (
        request.url.path.startswith("/api/v1/tasks") or
        request.url.path.startswith("/api/v1/sse")
    )
    
    if is_jsonrpc_endpoint:
        # Return JSON-RPC format for tasks/SSE endpoints with 422 for consistency
        error_obj = InvalidRequestError(
            message="Invalid request parameters", data=exc.errors()
        )
        response = A2AJSONRPCResponse(error=error_obj)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(exclude_none=True),
        )
    else:
        # Return standard REST validation error format
        error_response = {
            "detail": "Validation error",
            "errors": exc.errors()
        }
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response,
        )


@app.exception_handler(Exception)
async def generic_exception_handler(request: FastAPIRequest, exc: Exception):
    """
    Handles any other unexpected exceptions with format detection.
    """
    log.exception(
        "Unhandled Exception: %s, Request: %s %s", exc, request.method, request.url
    )
    
    # Check if this is a JSON-RPC endpoint
    is_jsonrpc_endpoint = (
        request.url.path.startswith("/api/v1/tasks") or
        request.url.path.startswith("/api/v1/sse")
    )
    
    if is_jsonrpc_endpoint:
        # Return JSON-RPC format for tasks/SSE endpoints
        error_obj = InternalError(
            message="An unexpected server error occurred: %s" % type(exc).__name__
        )
        response = A2AJSONRPCResponse(error=error_obj)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(exclude_none=True),
        )
    else:
        # Return standard REST error format
        error_response = {
            "detail": f"Internal server error: {type(exc).__name__}"
        }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response,
        )


@app.get("/health", tags=["Health"])
async def read_root():
    """Basic health check endpoint."""
    log.debug("Health check endpoint '/health' called")
    return {"status": "A2A Web UI Backend is running with 3-tiered architecture"}


log.info(
    "FastAPI application instance created with 3-tiered architecture."
)