"""
FastAPI application for Platform Service.
"""

import logging
import os
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from ..component import PlatformServiceComponent

log = logging.getLogger(__name__)

app = FastAPI(
    title="Platform Service API",
    version="1.0.0",
    description="Platform configuration management API (agents, connectors, toolsets, deployments)",
)



def _setup_alembic_config(database_url: str) -> Config:
    """
    Create and configure an Alembic Config object for community platform migrations.

    Args:
        database_url: Database connection string.

    Returns:
        Configured Alembic Config object.
    """
    alembic_cfg = Config()
    # Note: __file__ is in api/main.py, so we go up one level (..) to get to platform/
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "..", "alembic"),
    )
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    return alembic_cfg


def _run_community_migrations(database_url: str) -> None:
    """
    Run Alembic migrations for the community platform database schema.
    This includes any base tables defined in the community repo.

    Args:
        database_url: Database connection string.
    """
    try:
        from sqlalchemy import create_engine

        log.info("Starting community platform migrations...")
        engine = create_engine(database_url)
        inspector = sa.inspect(engine)
        existing_tables = inspector.get_table_names()

        if not existing_tables:
            log.info("Running initial community platform database setup")
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community platform database migrations completed")
        else:
            log.info("Checking for community platform schema updates")
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community platform database schema is current")
    except Exception as e:
        log.warning(
            "Community platform migration check failed: %s - attempting to run migrations",
            e,
        )
        try:
            alembic_cfg = _setup_alembic_config(database_url)
            command.upgrade(alembic_cfg, "head")
            log.info("Community platform database migrations completed")
        except Exception as migration_error:
            log.error("Community platform migration failed: %s", migration_error)
            log.error("Check database connectivity and permissions")
            raise RuntimeError(
                f"Community platform database migration failed: {migration_error}"
            ) from migration_error


def _run_enterprise_migrations(database_url: str) -> None:
    """
    Run migrations for enterprise platform features.
    This is optional and only runs if the enterprise package is available.

    Args:
        database_url: Database connection string.
    """
    try:
        from solace_agent_mesh_enterprise.platform_service.migration_runner import run_migrations

        log.info("[Platform Service] Starting enterprise migrations...")
        run_migrations(database_url)
        log.info("[Platform Service] Enterprise migrations completed successfully")
    except ImportError:
        log.debug("[Platform Service] Enterprise module not found - skipping enterprise migrations")
    except Exception as e:
        log.error("[Platform Service] Enterprise migration failed: %s", e)
        log.error("[Platform Service] Enterprise features may be unavailable")
        raise RuntimeError(f"Enterprise platform database migration failed: {e}") from e


def _setup_database(database_url: str) -> None:
    """Initialize database and run migrations."""
    log.info("[Platform Service] Initializing database and running migrations...")
    _run_enterprise_migrations(database_url)
    log.info("[Platform Service] Database initialization complete")


def setup_dependencies(component: "PlatformServiceComponent"):
    """
    Initialize FastAPI dependencies (middleware, routers).
    Database migrations are handled in component.__init__().

    Args:
        component: PlatformServiceComponent instance
    """
    log.info("Initializing Platform Service dependencies...")

    from . import dependencies
    dependencies.set_component_instance(component)

    _setup_middleware(component)
    _setup_routers()

    log.info("Platform Service dependencies initialized successfully")


async def _start_enterprise_platform_tasks(component: "PlatformServiceComponent") -> None:
    """
    Start enterprise platform background tasks if enterprise package is available.

    This follows the exact same pattern as WebUI Gateway:
    - Community calls enterprise function
    - Enterprise owns all background task logic
    - Graceful degradation if enterprise not available

    Background tasks (enterprise-only):
    - Heartbeat listener (deployer monitoring)
    - Deployment status checker (agent deployment monitoring)
    - Agent registry (tracks deployed agents)

    Args:
        component: PlatformServiceComponent instance
    """
    try:
        from solace_agent_mesh_enterprise.init_enterprise import (
            start_platform_background_tasks,
        )

        log.info("Starting enterprise platform background tasks...")
        await start_platform_background_tasks(component)
        log.info("Enterprise platform background tasks started successfully")

    except ImportError:
        log.info(
            "Enterprise package not available - platform background tasks will not start. "
            "Platform Service will run without deployment monitoring and deployer heartbeat tracking."
        )
    except RuntimeError as enterprise_err:
        log.warning(
            "Enterprise platform tasks disabled: %s - Platform Service will continue without deployment monitoring",
            enterprise_err,
        )
    except Exception as enterprise_err:
        log.error(
            "Failed to start enterprise platform tasks: %s - Platform Service will continue",
            enterprise_err,
            exc_info=True,
        )


def _setup_middleware(component: "PlatformServiceComponent"):
    """
    Add middleware to the FastAPI application.

    1. CORS middleware - allows cross-origin requests
    2. OAuth2 middleware - authentication (real token validation)

    Args:
        component: PlatformServiceComponent instance for configuration access.
    """
    # CORS middleware - automatically trust configured UI origins
    configured_origins = component.get_cors_origins().copy()

    # Automatically add frontend and platform service URLs as trusted origins
    # These are admin-controlled values that should always be trusted
    frontend_url = os.getenv("FRONTEND_SERVER_URL", "").strip()
    platform_url = os.getenv("PLATFORM_SERVICE_URL", "").strip()

    # Auto-construct frontend URL if not provided
    if not frontend_url:
        # Read WebUI Gateway configuration from environment variables
        fastapi_host = os.getenv("FASTAPI_HOST", "127.0.0.1").strip()
        fastapi_port = os.getenv("FASTAPI_PORT", "8000").strip()
        ssl_keyfile = os.getenv("SSL_KEYFILE", "").strip()
        ssl_certfile = os.getenv("SSL_CERTFILE", "").strip()

        # Determine protocol and port based on SSL configuration
        if ssl_keyfile and ssl_certfile:
            protocol = "https"
            port = os.getenv("FASTAPI_HTTPS_PORT", "8443").strip()
        else:
            protocol = "http"
            port = fastapi_port

        # Use 'localhost' if host is 127.0.0.1 for better compatibility
        host = "localhost" if fastapi_host == "127.0.0.1" else fastapi_host
        frontend_url = f"{protocol}://{host}:{port}"

        log.info(
            "FRONTEND_SERVER_URL not configured, auto-constructed from WebUI Gateway settings: %s",
            frontend_url
        )

    auto_trusted_origins = []
    if frontend_url:
        auto_trusted_origins.append(frontend_url)
    if platform_url:
        auto_trusted_origins.append(platform_url)

    # Combine and deduplicate
    allowed_origins = list(set(auto_trusted_origins + configured_origins))

    # Get optional regex pattern for CORS origins (useful for local dev with dynamic ports)
    cors_origin_regex = component.get_cors_origin_regex()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=cors_origin_regex if cors_origin_regex else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info(f"CORS middleware added with origins: {allowed_origins}")
    if cors_origin_regex:
        log.info(f"  CORS origin regex pattern: {cors_origin_regex}")
    if auto_trusted_origins:
        log.info(f"  Auto-added trusted origins: {auto_trusted_origins}")

    # OAuth2 authentication middleware
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    oauth_middleware_class = create_oauth_middleware(component)
    app.add_middleware(oauth_middleware_class, component=component)

    use_auth = component.get_config("frontend_use_authorization", False)
    if use_auth:
        log.info("OAuth2 middleware added (real token validation enabled)")
    else:
        log.info("OAuth2 middleware added (development mode - frontend_use_authorization=false)")


def _setup_routers():
    """
    Mount community and enterprise routers to the FastAPI application.

    All platform service routers (both community and enterprise) are mounted
    under the PLATFORM_SERVICE_PREFIX. This ensures a consistent API structure
    where /api/v1/platform/* contains all platform management endpoints.

    Community routers: Loaded from .routers
    Enterprise routers: Dynamically loaded from enterprise package if available
    """
    # Define the platform service API prefix
    # This is the single source of truth for all platform service endpoints
    PLATFORM_SERVICE_PREFIX = "/api/v1/platform"

    # Load community platform routers
    from .routers import get_community_platform_routers

    community_routers = get_community_platform_routers()
    for router_config in community_routers:
        app.include_router(
            router_config["router"],
            prefix=PLATFORM_SERVICE_PREFIX,
            tags=router_config["tags"],
        )
    log.info(f"Mounted {len(community_routers)} community platform routers")

    # Try to load enterprise platform routers
    try:
        from solace_agent_mesh_enterprise.platform_service.routers import get_enterprise_routers

        enterprise_routers = get_enterprise_routers()
        for router_config in enterprise_routers:
            app.include_router(
                router_config["router"],
                prefix=PLATFORM_SERVICE_PREFIX,
                tags=router_config["tags"],
            )
        log.info(f"Mounted {len(enterprise_routers)} enterprise platform routers under {PLATFORM_SERVICE_PREFIX}")

    except ImportError:
        log.info(
            "No enterprise package detected - running in community mode (no platform endpoints available)"
        )
    except Exception as e:
        log.warning(f"Failed to load enterprise platform routers: {e}")

    from solace_agent_mesh.shared.exceptions.exception_handlers import register_exception_handlers
    register_exception_handlers(app)
    log.info("Registered shared exception handlers")
