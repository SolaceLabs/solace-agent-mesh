import logging
import os
from pathlib import Path

import httpx
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi import status
from typing import TYPE_CHECKING

import sqlalchemy as sa
from a2a.types import InternalError, JSONRPCError
from a2a.types import JSONRPCResponse as A2AJSONRPCResponse
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

from .routers.sessions import router as session_router
from .routers.tasks import router as task_router
from .routers.users import router as user_router
from ...common import a2a
from ...gateway.http_sse import dependencies
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

from alembic import command
from alembic.config import Config

from a2a.types import InternalError, InvalidRequestError, JSONRPCError
from a2a.types import JSONRPCResponse as A2AJSONRPCResponse
from ...common import a2a
from ...gateway.http_sse import dependencies


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


def _create_auth_middleware(component):
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
                "/api/v1/auth/tool/callback",
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
                await self._handle_authenticated_request(request, scope, receive, send)
            else:
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

        async def _handle_authenticated_request(self, request, scope, receive, send):
            access_token = _extract_access_token(request)

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
                auth_provider = dependencies.api_config.get("external_auth_provider")

                if not auth_service_url:
                    log.error("Auth service URL not configured.")
                    response = JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Auth service not configured"},
                    )
                    await response(scope, receive, send)
                    return

                if not await _validate_token(
                    auth_service_url, auth_provider, access_token
                ):
                    log.warning("AuthMiddleware: Token validation failed")
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "detail": "Invalid token",
                            "error_type": "invalid_token",
                        },
                    )
                    await response(scope, receive, send)
                    return

                user_info = await _get_user_info(
                    auth_service_url, auth_provider, access_token
                )
                if not user_info:
                    log.warning(
                        "AuthMiddleware: Failed to get user info from external auth service"
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

                user_identifier = _extract_user_identifier(user_info)
                if not user_identifier or user_identifier.lower() in [
                    "null",
                    "none",
                    "",
                ]:
                    log.error(
                        "AuthMiddleware: No valid user identifier from OAuth provider"
                    )
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "detail": "OAuth provider returned no valid user identifier",
                            "error_type": "invalid_user_identifier_from_provider",
                        },
                    )
                    await response(scope, receive, send)
                    return

                email_from_auth, display_name = _extract_user_details(
                    user_info, user_identifier
                )

                identity_service = self.component.identity_service
                if not identity_service:
                    request.state.user = (
                        await _create_user_state_without_identity_service(
                            user_identifier, email_from_auth, display_name
                        )
                    )
                else:
                    user_state = await _create_user_state_with_identity_service(
                        identity_service,
                        user_identifier,
                        email_from_auth,
                        display_name,
                        user_info,
                    )
                    if not user_state:
                        log.error(
                            "AuthMiddleware: User authenticated but not found in internal IdentityService"
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
                    request.state.user = user_state

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

    return AuthMiddleware


def _setup_alembic_config(database_url: str) -> Config:
    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "alembic"),
    )
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    return alembic_cfg


def _run_community_migrations(database_url: str) -> None:
    """
    Run Alembic migrations for the community database schema.
    This includes sessions, chat_messages tables and their indexes.
    """
    try:
        from sqlalchemy import create_engine

        log.info("Starting community migrations...")
        engine = create_engine(database_url)
        inspector = sa.inspect(engine)
        existing_tables = inspector.get_table_names()

        if not existing_tables or "sessions" not in existing_tables:
            log.info("Running initial community database setup")
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community database migrations completed")
        else:
            log.info("Checking for community schema updates")
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community database schema is current")
    except Exception as e:
        log.warning(
            "Community migration check failed: %s - attempting to run migrations",
            e,
        )
        try:
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community database migrations completed")
        except Exception as migration_error:
            log.error("Community migration failed: %s", migration_error)
            log.error("Check database connectivity and permissions")
            raise RuntimeError(
                f"Community database migration failed: {migration_error}"
            ) from migration_error


def _run_enterprise_migrations(
    component: "WebUIBackendComponent", database_url: str
) -> None:
    """
    Run migrations for enterprise features like advanced analytics, audit logs, etc.
    This is optional and only runs if the enterprise package is available.
    """
    try:
        from solace_agent_mesh_enterprise.webui_backend.migration_runner import (
            run_migrations,
        )

        webui_app = component.get_app()
        app_config = getattr(webui_app, "app_config", {}) if webui_app else {}
        log.info("Starting enterprise migrations...")
        run_migrations(database_url, app_config)
        log.info("Enterprise migrations completed")
    except (ImportError, ModuleNotFoundError):
        log.debug("Enterprise module not found - skipping enterprise migrations")
    except Exception as e:
        log.error("Enterprise migration failed: %s", e)
        log.error("Advanced features may be unavailable")
        raise RuntimeError(f"Enterprise database migration failed: {e}") from e


def _setup_database(
    component: "WebUIBackendComponent",
    database_url: str,
    platform_database_url: str = None
) -> None:
    """
    Initialize database connections and run all required migrations.
    Sets up both runtime and platform database schemas.

    Args:
        component: WebUIBackendComponent instance
        database_url: Runtime database URL (sessions, tasks, chat) - REQUIRED
        platform_database_url: Platform database URL (agents, connectors, deployments).
                                If None, platform features will be unavailable.
    """
    dependencies.init_database(database_url)
    log.info("Persistence enabled - sessions will be stored in database")
    log.info("Running database migrations...")

    _run_community_migrations(database_url)

    if platform_database_url:
        log.info("Platform database configured - running migrations")
        _run_enterprise_migrations(component, platform_database_url)
    else:
        log.info("No platform database configured - skipping platform migrations")


def _get_app_config(component: "WebUIBackendComponent") -> dict:
    webui_app = component.get_app()
    app_config = {}
    if webui_app:
        app_config = getattr(webui_app, "app_config", {})
        if app_config is None:
            log.warning("webui_app.app_config is None, using empty dict.")
            app_config = {}
    else:
        log.warning("Could not get webui_app from component. Using empty app_config.")
    return app_config


def _create_api_config(app_config: dict, database_url: str) -> dict:
    return {
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
        "persistence_enabled": database_url is not None,
    }


def setup_dependencies(
    component: "WebUIBackendComponent",
    database_url: str = None,
    platform_database_url: str = None
):
    """
    Initialize dependencies for both runtime and platform databases.

    Args:
        component: WebUIBackendComponent instance
        database_url: Runtime database URL (sessions, tasks, chat).
                     If None, runs in compatibility mode with in-memory sessions.
        platform_database_url: Platform database URL (agents, connectors, deployments).
                                If None, platform features will be unavailable (returns 501).

    This function is idempotent and safe to call multiple times.
    """
    global _dependencies_initialized

    if _dependencies_initialized:
        log.debug("[setup_dependencies] Dependencies already initialized, skipping")
        return

    dependencies.set_component_instance(component)

    if database_url:
        _setup_database(component, database_url, platform_database_url)
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

    auth_middleware_class = _create_auth_middleware(component)
    app.add_middleware(auth_middleware_class, component=component)
    log.info("AuthMiddleware added.")


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

    # Register shared exception handlers from community repo
    from .shared.exception_handlers import register_exception_handlers

    register_exception_handlers(app)
    log.info("Registered shared exception handlers from community repo")

    # Mount enterprise routers if available
    try:
        from solace_agent_mesh_enterprise.webui_backend.routers import (
            get_enterprise_routers,
        )

        enterprise_routers = get_enterprise_routers()
        for router_config in enterprise_routers:
            app.include_router(
                router_config["router"],
                prefix=router_config["prefix"],
                tags=router_config["tags"],
            )
        log.info("Mounted %d enterprise routers", len(enterprise_routers))

    except ImportError:
        log.debug("No enterprise package detected - skipping enterprise routers")
    except ModuleNotFoundError:
        log.debug(
            "Enterprise module not found - skipping enterprise routers and exception handlers"
        )
    except Exception as e:
        log.warning("Failed to load enterprise routers and exception handlers: %s", e)


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
