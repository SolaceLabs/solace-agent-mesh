"""
FastAPI dependency injection for Platform Service.

Provides database sessions, component instance access, and user authentication.
"""

import logging
from typing import TYPE_CHECKING, Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from ..component import PlatformServiceComponent

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
    - SQLite: StaticPool, foreign key enforcement
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
                "poolclass": pool.StaticPool,
                "connect_args": {"check_same_thread": False},
            }
            log.info("Configuring SQLite database (single-connection mode)")

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
