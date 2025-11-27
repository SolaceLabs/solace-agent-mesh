"""
FastAPI application for Platform Service.

Provides REST API endpoints for platform configuration management:
- Agents
- Connectors
- Toolsets
- Deployments
- AI Assistant

This is NOT a gateway - it only handles CRUD operations with OAuth2 token validation.
"""

import logging
from typing import TYPE_CHECKING

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

    # Initialize database
    if database_url:
        dependencies.init_database(database_url)
        log.info("Platform database initialized")
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
    2. OAuth2 stub middleware - authentication (Phase 1: stub, Phase 2: real)

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

    # OAuth2 stub middleware (Phase 1)
    from .middleware import oauth2_stub_middleware

    app.middleware("http")(oauth2_stub_middleware)
    log.info(
        "OAuth2 stub middleware added (Phase 1 - REPLACE IN PHASE 2 WITH REAL VALIDATION)"
    )


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
        from solace_agent_mesh_enterprise.platform.routers import get_platform_routers

        enterprise_routers = get_platform_routers()
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
    except ModuleNotFoundError:
        log.debug(
            "Enterprise platform module not found - skipping enterprise platform routers"
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
