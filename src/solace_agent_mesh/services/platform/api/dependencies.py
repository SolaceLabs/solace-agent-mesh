"""
FastAPI dependency injection for Platform Service.

Provides database sessions, component instance access, and user authentication.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Generator

from fastapi import Depends, HTTPException, status
from openfeature import api as openfeature_api
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from .routers.dto.responses.model_configuration_responses import ModelDependentResponse

if TYPE_CHECKING:
    from ..component import PlatformServiceComponent
    from ..services import ModelConfigService, ModelListService

log = logging.getLogger(__name__)

# Global state
platform_component_instance: "PlatformServiceComponent" = None
PlatformSessionLocal: sessionmaker = None


def set_component_instance(component: "PlatformServiceComponent"):
    """
    Store the component reference for dependency injection.

    Called by setup_dependencies during component startup.

    Args:
        component: The PlatformServiceComponent instance.
    """
    global platform_component_instance
    if platform_component_instance is None:
        platform_component_instance = component
        log.info("Platform component instance provided.")
    else:
        log.warning("Platform component instance already set.")


def init_database(database_url: str):
    """
    Initialize database connection with dialect-specific configuration.

    Configures appropriate connection pooling and settings for:
    - SQLite: NullPool with WAL mode for multi-threaded access
    - PostgreSQL/MySQL: Connection pooling with pre-ping

    Args:
        database_url: SQLAlchemy database URL string.
    """
    global PlatformSessionLocal
    if PlatformSessionLocal is None:
        url = make_url(database_url)
        dialect_name = url.get_dialect().name

        engine_kwargs = {}

        if dialect_name == "sqlite":
            engine_kwargs = {
                "poolclass": pool.NullPool,
                "connect_args": {"check_same_thread": False},
            }
            log.info("Configuring SQLite database with NullPool (per-thread connections)")

        elif dialect_name in ("postgresql", "mysql"):
            engine_kwargs = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
                "pool_pre_ping": True,
            }
            log.info(f"Configuring {dialect_name} database with connection pooling")

        else:
            log.warning(f"Using default configuration for dialect: {dialect_name}")

        engine = create_engine(database_url, **engine_kwargs)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Enable foreign key constraints for SQLite."""
            if dialect_name == "sqlite":
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        PlatformSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        log.info("Database initialized successfully")
    else:
        log.warning("Database already initialized.")


def get_platform_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for platform database session management.

    Provides a database session with automatic commit/rollback:
    - Commits on success
    - Rolls back on exception
    - Always closes the session

    Yields:
        SQLAlchemy database session for platform database.

    Raises:
        HTTPException: 503 if database is not initialized.
    """
    if PlatformSessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized.",
        )
    db = PlatformSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_heartbeat_tracker():
    """
    Get the heartbeat tracker from platform component.

    Used by deployer status endpoint to check if deployer is online.

    Returns:
        HeartbeatTracker instance if initialized, None otherwise.
    """
    if platform_component_instance is None:
        log.warning("Platform component not initialized - heartbeat tracker unavailable")
        return None
    return platform_component_instance.get_heartbeat_tracker()

def get_component_instance() -> "PlatformServiceComponent":
    """
    FastAPI dependency for accessing the PlatformServiceComponent instance.

    Returns:
        The PlatformServiceComponent instance.

    Raises:
        HTTPException: 503 if component is not initialized.
    """
    if platform_component_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform component not initialized.",
        )
    return platform_component_instance

def get_agent_registry():
    """
    Get the agent registry from platform component.

    Used for deployment status monitoring.

    Returns:
        AgentRegistry instance if initialized, None otherwise.
    """
    if platform_component_instance is None:
        log.warning("Platform component not initialized - agent registry unavailable")
        return None
    return platform_component_instance.get_agent_registry()


def get_gateway_registry():
    """
    Get the gateway registry from platform component.

    Used for gateway fleet health monitoring.

    Returns:
        GatewayRegistry instance if initialized, None otherwise.
    """
    if platform_component_instance is None:
        log.warning("Platform component not initialized - gateway registry unavailable")
        return None
    return platform_component_instance.get_gateway_registry()


def get_model_config_service() -> ModelConfigService:
    """
    FastAPI dependency for ModelConfigService.

    Provides a service instance for model configuration business logic.
    The service is stateless and takes db: Session as a parameter to each method,
    allowing database session lifecycle to be managed independently.

    Returns:
        ModelConfigService instance for accessing model configurations.
    """
    from solace_agent_mesh.services.platform.services import ModelConfigService

    return ModelConfigService()

def get_model_list_service() -> "ModelListService":
    """
    FastAPI dependency for ModelListService.
    Provides a service instance for fetching supported LLM models per provider.
    Returns:
        ModelListService instance for accessing model lists.
    """
    from solace_agent_mesh.services.platform.services import ModelListService

    return ModelListService()


class ModelDependentsHandler:
    """Interface for handling model-dependent agents on delete.

    The community default is a no-op. Enterprise overrides this to find
    and undeploy agents that depend on a given model configuration.
    """

    async def undeploy_dependents(self, model_alias: str, model_id: str, component: "PlatformServiceComponent") -> list[ModelDependentResponse]:
        """Undeploy agents depending on the given model (by alias or ID).

        Args:
            model_alias: The model alias being deleted.
            model_id: The model UUID being deleted.
            component: PlatformServiceComponent instance for publishing.

        Returns:
            List of dicts with info about undeployed agents.
        """
        return []


_model_dependents_handler: ModelDependentsHandler = ModelDependentsHandler()


def set_model_dependents_handler(handler: ModelDependentsHandler):
    """Register an enterprise handler for model-dependent agent management."""
    global _model_dependents_handler
    _model_dependents_handler = handler
    log.info("Model dependents handler registered.")


def get_model_dependents_handler() -> ModelDependentsHandler:
    """FastAPI dependency for the model dependents handler."""
    return _model_dependents_handler


def require_model_config_ui_enabled() -> bool:
    """Dependency that checks if model configuration UI feature is enabled.

    Checks the model_config_ui feature flag at request time.

    Returns:
        True if feature is enabled.

    Raises:
        HTTPException: 501 Not Implemented if feature is disabled.
    """
    is_enabled = openfeature_api.get_client().get_boolean_value("model_config_ui", False)
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Model configuration feature is not enabled",
        )
    return True
