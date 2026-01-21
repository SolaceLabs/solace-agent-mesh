from __future__ import annotations

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
    from .component import WebUIBackendComponent

log = logging.getLogger(__name__)


app = FastAPI(
    title="A2A Web UI Backend",
    version="1.0.0",  # Updated to reflect simplified architecture
    description="Backend API and SSE server for the A2A Web UI, hosted by Solace AI Connector.",
)




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

        log.info("[WebUI Gateway] Starting community migrations...")
        engine = create_engine(database_url)
        inspector = sa.inspect(engine)
        existing_tables = inspector.get_table_names()

        alembic_cfg = _setup_alembic_config(database_url)
        if not existing_tables or "sessions" not in existing_tables:
            log.info("[WebUI Gateway] Running initial database setup")
        else:
            log.info("[WebUI Gateway] Checking for schema updates")

        command.upgrade(alembic_cfg, "head")
        log.info("[WebUI Gateway] Community migrations completed")
    except Exception as e:
        log.warning("[WebUI Gateway] Migration check failed: %s - attempting to run migrations", e)
        try:
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("[WebUI Gateway] Community migrations completed")
        except Exception as migration_error:
            log.error("[WebUI Gateway] Migration failed: %s", migration_error)
            log.error("[WebUI Gateway] Check database connectivity and permissions")
            raise RuntimeError(
                f"Community database migration failed: {migration_error}"
            ) from migration_error




def _setup_database(database_url: str) -> None:
    """
    Initialize database and run migrations for WebUI Gateway.

    Args:
        database_url: Chat database URL (sessions, tasks, feedback)
    """
    dependencies.init_database(database_url)
    log.info("[WebUI Gateway] Running database migrations...")
    _run_community_migrations(database_url)


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


def setup_dependencies(component: "WebUIBackendComponent"):
    """
    Initialize FastAPI dependencies (middleware, routers, static files).
    Database migrations are handled in component.__init__().

    Args:
        component: WebUIBackendComponent instance
    """
    dependencies.set_component_instance(component)

    app_config = _get_app_config(component)
    api_config_dict = _create_api_config(app_config, component.database_url)
    dependencies.set_api_config(api_config_dict)

    _setup_middleware(component)
    _setup_routers()
    _setup_static_files()


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

    api_config = dependencies.get_api_config()
    use_auth = api_config.get("frontend_use_authorization", False) if api_config else False
    if use_auth:
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