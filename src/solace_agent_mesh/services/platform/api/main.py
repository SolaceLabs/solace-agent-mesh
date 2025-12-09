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

# Global flag to track initialization (idempotent)
_dependencies_initialized = False


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
        component: PlatformServiceComponent instance.
        database_url: Database connection string.
    """
    try:
        from solace_agent_mesh_enterprise.webui_backend.migration_runner import run_migrations

        log.info("Starting enterprise platform migrations...")
        run_migrations(database_url)
        log.info("Enterprise platform migrations completed")
    except ImportError:
        log.debug("Enterprise platform module not found - skipping enterprise migrations")
    except Exception as e:
        log.error("Enterprise platform migration failed: %s", e)
        log.error("Enterprise platform features may be unavailable")
        raise RuntimeError(f"Enterprise platform database migration failed: {e}") from e


def _setup_database(database_url: str) -> None:
    """
    Initialize database connection and run all required migrations.
    Sets up both community and enterprise platform database schemas.

    This follows the same pattern as gateway/http_sse:
    1. Initialize database (create engine and SessionLocal)
    2. Run community migrations
    3. Run enterprise migrations (if available)

    Args:
        component: PlatformServiceComponent instance.
        database_url: Platform database URL (agents, connectors, deployments, toolsets) - REQUIRED
    """
    from . import dependencies

    # MIGRATION PHASE 1: DB is initialized in enterprise repo. In next phase, platform db will be initialized here
    # dependencies.init_database(database_url)
    # log.info("Platform database initialized - running migrations...")

    # MIGRATION PHASE 1: No community migrations yet - only enterprise migrations
    # _run_community_migrations(database_url)
    _run_enterprise_migrations(database_url)


def setup_dependencies(component: "PlatformServiceComponent", database_url: str):
    """
    Initialize dependencies for the Platform Service.

    This function is idempotent and safe to call multiple times.
    It sets up:
    1. Component instance reference
    2. Database connection
    3. Middleware (CORS, OAuth2)
    4. Routers (community and enterprise)

    Args:
        component: PlatformServiceComponent instance.
        database_url: Database connection string.
    """
    global _dependencies_initialized

    if _dependencies_initialized:
        log.debug("Platform service dependencies already initialized, skipping")
        return

    log.info("Initializing Platform Service dependencies...")

    # Store component reference for dependency injection
    from . import dependencies

    dependencies.set_component_instance(component)

    # ALSO set gateway dependencies to allow webui_backend routers to work
    # webui_backend routers use ValidatedUserConfig which expects sac_component_instance
    try:
        from solace_agent_mesh.gateway.http_sse import dependencies as gateway_deps
        gateway_deps.sac_component_instance = component
        log.info("Gateway dependencies configured to use platform component")
    except ImportError:
        log.debug("Gateway module not available - skipping gateway dependency setup")

    # Initialize database and run migrations
    if database_url:
        _setup_database(database_url)
        log.info("Platform database initialized with migrations")
    else:
        log.warning("No database URL provided - platform service will not function")

    # Setup middleware
    _setup_middleware(component)

    # Setup routers
    _setup_routers()

    _dependencies_initialized = True
    log.info("Platform Service dependencies initialized successfully")


def _setup_middleware(component: "PlatformServiceComponent"):
    """
    Add middleware to the FastAPI application.

    1. CORS middleware - allows cross-origin requests
    2. OAuth2 middleware - authentication (uses enterprise implementation if available)

    Args:
        component: PlatformServiceComponent instance for configuration access.
    """
    # CORS middleware
    allowed_origins = component.get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info(f"CORS middleware added with origins: {allowed_origins}")

    # OAuth2 middleware - try enterprise implementation first, fall back to stub
    # try:
    #     from solace_agent_mesh_enterprise.platform_service.middleware import create_oauth2_middleware
    #
    #     oauth2_middleware_class = create_oauth2_middleware(component)
    #     app.add_middleware(oauth2_middleware_class)
    #     log.info("Enterprise OAuth2 middleware added (real token validation)")
    # except ImportError:
    #     # Fall back to stub middleware if enterprise package not available
    #     from .middleware import oauth2_stub_middleware
    #
    #     app.middleware("http")(oauth2_stub_middleware)
    #     log.info("OAuth2 stub middleware added (development mode - no enterprise package)")


def _setup_routers():
    """
    Mount community and enterprise routers to the FastAPI application.

    Community routers: Loaded from .routers (empty in Phase 1)
    Enterprise routers: Dynamically loaded from enterprise package if available
    """
    # Load community platform routers (empty in Phase 1)
    from .routers import get_community_platform_routers

    community_routers = get_community_platform_routers()
    for router_config in community_routers:
        app.include_router(
            router_config["router"],
            prefix=router_config["prefix"],
            tags=router_config["tags"],
        )
    log.info(f"Mounted {len(community_routers)} community platform routers")

    # Try to load enterprise platform routers
    try:
        from solace_agent_mesh_enterprise.webui_backend.routers import get_enterprise_routers

        enterprise_routers = get_enterprise_routers()
        for router_config in enterprise_routers:
            app.include_router(
                router_config["router"],
                prefix=router_config["prefix"],
                tags=router_config["tags"],
            )
        log.info(f"Mounted {len(enterprise_routers)} enterprise platform routers")

    except ImportError:
        log.info(
            "No enterprise package detected - running in community mode (no platform endpoints available)"
        )
    except Exception as e:
        log.warning(f"Failed to load enterprise platform routers: {e}")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Platform Service health check endpoint.

    Returns:
        Dictionary with status and service name.
    """
    log.debug("Health check endpoint '/health' called")
    return {"status": "healthy", "service": "Platform Service"}
