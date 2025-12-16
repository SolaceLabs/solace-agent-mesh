"""
Defines FastAPI dependency injectors to access shared resources
managed by the WebUIBackendComponent.
"""

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from fastapi import Depends, HTTPException, Request, status, Path, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ...common.agent_registry import AgentRegistry
from ...common.middleware.config_resolver import ConfigResolver
from ...common.services.identity_service import BaseIdentityService
from ...core_a2a.service import CoreA2AService
from ...gateway.base.task_context import TaskContextManager
from ...gateway.http_sse.services.agent_card_service import AgentCardService
from ...gateway.http_sse.services.audio_service import AudioService
from ...gateway.http_sse.services.project_service import ProjectService
from ...gateway.http_sse.services.feedback_service import FeedbackService
from ...gateway.http_sse.services.people_service import PeopleService
from ...gateway.http_sse.services.task_logger_service import TaskLoggerService
from ...gateway.http_sse.services.task_service import TaskService
from ...gateway.http_sse.services.data_retention_service import DataRetentionService
from ...gateway.http_sse.session_manager import SessionManager
from ...gateway.http_sse.sse_manager import SSEManager
from .repository import SessionRepository
from .repository.interfaces import ITaskRepository
from .repository.project_repository import ProjectRepository
from .repository.task_repository import TaskRepository
from .services.session_service import SessionService

log = logging.getLogger(__name__)

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:
    # Mock BaseArtifactService for environments without Google ADK
    class BaseArtifactService:
        pass


if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

sac_component_instance: "WebUIBackendComponent" = None
SessionLocal: sessionmaker = None

api_config: dict[str, Any] | None = None


def set_component_instance(component: "WebUIBackendComponent"):
    """Called by the component during its startup to provide its instance."""
    global sac_component_instance
    if sac_component_instance is None:
        sac_component_instance = component
        log.info("SAC Component instance provided.")
    else:
        log.warning("SAC Component instance already set.")


def init_database(database_url: str):
    """Initialize database with appropriate configuration based on database dialect."""
    global SessionLocal
    if SessionLocal is None:
        from sqlalchemy import event, pool
        from sqlalchemy.engine.url import make_url

        url = make_url(database_url)
        dialect_name = url.get_dialect().name

        engine_kwargs = {}

        if dialect_name == "sqlite":
            engine_kwargs = {
                "poolclass": pool.StaticPool,
                "connect_args": {"check_same_thread": False}
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
            if dialect_name == "sqlite":
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        log.debug(f"Database initialized: {url}")
        log.info("Database initialized successfully")
    else:
        log.warning("Database already initialized.")


def set_api_config(config: dict[str, Any]):
    """Called during startup to provide API configuration."""
    global api_config
    if api_config is None:
        api_config = config
        log.debug("API configuration provided.")
    else:
        log.warning("API configuration already set.")


def get_sac_component() -> "WebUIBackendComponent":
    """FastAPI dependency to get the SAC component instance."""
    if sac_component_instance is None:
        log.critical(
            "SAC Component instance accessed before it was set!"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend component not yet initialized.",
        )
    return sac_component_instance


def get_api_config() -> dict[str, Any]:
    """FastAPI dependency to get the API configuration."""
    if api_config is None:
        log.critical("API configuration accessed before it was set!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API configuration not yet initialized.",
        )
    return api_config


def get_agent_registry(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> AgentRegistry:
    """FastAPI dependency to get the AgentRegistry."""
    log.debug("get_agent_registry called")
    return component.get_agent_registry()


def get_sse_manager(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SSEManager:
    """FastAPI dependency to get the SSEManager."""
    log.debug("get_sse_manager called")
    return component.get_sse_manager()


def get_session_manager(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SessionManager:
    """FastAPI dependency to get the SessionManager."""
    log.debug("get_session_manager called")
    return component.get_session_manager()


def get_user_id_callable(
    session_manager: SessionManager = Depends(get_session_manager),
) -> Callable:
    """Dependency that provides the callable for getting user_id (client_id)."""
    log.debug("Providing user_id callable")
    return session_manager.dep_get_client_id()


def ensure_session_id_callable(
    session_manager: SessionManager = Depends(get_session_manager),
) -> Callable:
    """Dependency that provides the callable for ensuring session_id."""
    log.debug("Providing ensure_session_id callable")
    return session_manager.dep_ensure_session_id()


def get_user_id(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> str:
    """
    FastAPI dependency that returns the user's identity.
    When FRONTEND_USE_AUTHORIZATION is true: Fully relies on OAuth - user must be authenticated by AuthMiddleware.
    When FRONTEND_USE_AUTHORIZATION is false: Uses development fallback user.
    """
    log.debug("Resolving user_id string")

    # AuthMiddleware should always set user state for both auth enabled/disabled cases
    if hasattr(request.state, "user") and request.state.user:
        user_id = request.state.user.get("id")
        if user_id:
            log.debug(f"Using user ID from AuthMiddleware: {user_id}")
            return user_id
        else:
            log.error(
                "request.state.user exists but has no 'id' field: %s. This indicates a bug in AuthMiddleware.",
                request.state.user,
            )

    # If we reach here, AuthMiddleware didn't set user state properly
    use_authorization = session_manager.use_authorization

    if use_authorization:
        # When OAuth is enabled, we should never reach here - AuthMiddleware should have handled authentication
        log.error(
            "OAuth is enabled but no authenticated user found. This indicates an authentication failure or middleware bug."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required but user not found",
        )
    else:
        # When auth is disabled, use development fallback user
        fallback_id = "sam_dev_user"
        log.info(
            "Authorization disabled and no user in request state, using fallback user: %s",
            fallback_id,
        )
        return fallback_id


def ensure_session_id(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> str:
    """FastAPI dependency that directly returns the ensured session_id string."""
    log.debug("Resolving ensured session_id string")
    return session_manager.ensure_a2a_session(request)


def get_identity_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> BaseIdentityService | None:
    """FastAPI dependency to get the configured IdentityService instance."""
    log.debug("get_identity_service called")
    return component.identity_service


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Session management requires database configuration.",
        )
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_people_service(
    identity_service: BaseIdentityService | None = Depends(get_identity_service),
) -> PeopleService:
    """FastAPI dependency to get an instance of PeopleService."""
    log.debug("get_people_service called")
    return PeopleService(identity_service=identity_service)


def get_task_repository() -> ITaskRepository:
    """FastAPI dependency to get an instance of TaskRepository."""
    log.debug("get_task_repository called")
    return TaskRepository()


def get_feedback_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    task_repo: ITaskRepository = Depends(get_task_repository),
) -> FeedbackService:
    """FastAPI dependency to get an instance of FeedbackService."""
    log.debug("get_feedback_service called")
    # The session factory is needed for the existing DB save logic.
    session_factory = SessionLocal if component.database_url else None
    return FeedbackService(
        session_factory=session_factory, component=component, task_repo=task_repo
    )


def get_data_retention_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> DataRetentionService | None:
    """
    FastAPI dependency to get the DataRetentionService instance.

    Returns:
        DataRetentionService instance if database is configured and service is initialized,
        None otherwise.

    Note:
        This dependency is primarily for future API endpoints that might expose
        data retention statistics or manual cleanup triggers. The service itself
        runs automatically via timer in the component.
    """
    log.debug("get_data_retention_service called")

    if not component.database_url:
        log.debug(
            "Database not configured, returning None for data retention service"
        )
        return None

    if (
        not hasattr(component, "data_retention_service")
        or component.data_retention_service is None
    ):
        log.warning("DataRetentionService not initialized on component")
        return None

    return component.data_retention_service


def get_task_logger_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> TaskLoggerService:
    """FastAPI dependency to get an instance of TaskLoggerService."""
    log.debug("get_task_logger_service called")
    task_logger_service = component.get_task_logger_service()
    if task_logger_service is None:
        log.error("TaskLoggerService is not available.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task logging service is not configured or available.",
        )
    return task_logger_service


PublishFunc = Callable[[str, dict, dict | None], None]


def get_publish_a2a_func(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> PublishFunc:
    """FastAPI dependency to get the component's publish_a2a method."""
    log.debug("get_publish_a2a_func called")
    return component.publish_a2a


def get_namespace(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> str:
    """FastAPI dependency to get the namespace."""
    log.debug("get_namespace called")
    return component.get_namespace()


def get_gateway_id(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> str:
    """FastAPI dependency to get the Gateway ID."""
    log.debug("get_gateway_id called")
    return component.get_gateway_id()


def get_config_resolver(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> ConfigResolver:
    """FastAPI dependency to get the ConfigResolver."""
    log.debug("get_config_resolver called")
    return component.get_config_resolver()


def get_app_config(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> dict[str, Any]:
    """
    FastAPI dependency to safely get the application configuration dictionary.
    """
    log.debug("get_app_config called")
    return component.component_config.get("app_config", {})


async def get_user_config(
    request: Request,
    user_id: str = Depends(get_user_id),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    app_config: dict[str, Any] = Depends(get_app_config),
) -> dict[str, Any]:
    """
    FastAPI dependency to get the user-specific configuration.
    """
    log.debug(f"get_user_config called for user_id: {user_id}")

    # TODO: DATAGO-114659-split-cleanup
    gateway_context = {}
    if getattr(component, "gateway_id", None):
        gateway_context = {
            "gateway_id": component.gateway_id,
            "gateway_app_config": app_config,
            "request": request,
        }
    return await config_resolver.resolve_user_config(
        user_id, gateway_context, app_config
    )


class ValidatedUserConfig:
    """
    FastAPI dependency class for validating user scopes and returning user config.

    This class creates a callable dependency that validates a user has the required
    scopes before allowing access to protected endpoints.

    Args:
        required_scopes: List of scope strings required for authorization

    Raises:
        HTTPException: 403 if user lacks required scopes

    Example:
        @router.get("/artifacts")
        async def list_artifacts(
            user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
        ):
    """

    def __init__(self, required_scopes: list[str]):
        self.required_scopes = required_scopes

    async def __call__(
        self,
        request: Request,
        config_resolver: ConfigResolver = Depends(get_config_resolver),
        user_config: dict[str, Any] = Depends(get_user_config),
    ) -> dict[str, Any]:
        user_id = user_config.get("user_profile", {}).get("id")

        log.debug(
            f"ValidatedUserConfig called for user_id: {user_id} with required scopes: {self.required_scopes}"
        )

        # Validate scopes
        if not config_resolver.is_feature_enabled(
            user_config,
            {"tool_metadata": {"required_scopes": self.required_scopes}},
            {},
        ):
            log.warning(
                f"Authorization denied for user '{user_id}'. Required scopes: {self.required_scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized. Required scopes: {self.required_scopes}",
            )

        return user_config


def get_shared_artifact_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> BaseArtifactService | None:
    """FastAPI dependency to get the shared ArtifactService."""
    log.debug("get_shared_artifact_service called")
    return component.get_shared_artifact_service()


def get_embed_config(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> dict[str, Any]:
    """FastAPI dependency to get embed-related configuration."""
    log.debug("get_embed_config called")
    return component.get_embed_config()


def get_core_a2a_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> CoreA2AService:
    """FastAPI dependency to get the CoreA2AService."""
    log.debug("get_core_a2a_service called")
    core_service = component.get_core_a2a_service()
    if core_service is None:
        log.critical("CoreA2AService accessed before initialization!")
        raise HTTPException(status_code=503, detail="Core service not ready.")
    return core_service


def get_task_context_manager_from_component(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> TaskContextManager:
    """FastAPI dependency to get the TaskContextManager from the component."""
    log.debug("get_task_context_manager_from_component called")
    if component.task_context_manager is None:
        log.critical(
            "TaskContextManager accessed before initialization!"
        )
        raise HTTPException(status_code=503, detail="Task context manager not ready.")
    return component.task_context_manager


def get_agent_card_service(
    registry: AgentRegistry = Depends(get_agent_registry),
) -> AgentCardService:
    """FastAPI dependency to get an instance of AgentCardService."""
    log.debug("get_agent_card_service called")
    return AgentCardService(agent_registry=registry)


def get_task_service(
    core_a2a_service: CoreA2AService = Depends(get_core_a2a_service),
    publish_func: PublishFunc = Depends(get_publish_a2a_func),
    namespace: str = Depends(get_namespace),
    gateway_id: str = Depends(get_gateway_id),
    sse_manager: SSEManager = Depends(get_sse_manager),
    task_context_manager: TaskContextManager = Depends(
        get_task_context_manager_from_component
    ),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> TaskService:
    """FastAPI dependency to get an instance of TaskService."""
    log.debug("get_task_service called")
    app_name = component.get_config("name", "WebUIBackendApp")
    return TaskService(
        core_a2a_service=core_a2a_service,
        publish_func=publish_func,
        namespace=namespace,
        gateway_id=gateway_id,
        sse_manager=sse_manager,
        task_context_map=task_context_manager._contexts,
        task_context_lock=task_context_manager._lock,
        app_name=app_name,
    )


def get_session_business_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SessionService:
    log.debug("get_session_business_service called")

    # Note: Session and message repositories will be created per request
    # when the SessionService methods receive the db parameter
    return SessionService(component=component)


def get_session_validator(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> Callable[[str, str], bool]:
    log.debug("get_session_validator called")

    if SessionLocal:
        log.debug("Using database-backed session validation")

        def validate_with_database(session_id: str, user_id: str) -> bool:
            try:
                db = SessionLocal()
                try:
                    session_repository = SessionRepository()
                    session_domain = session_repository.find_user_session(
                        db, session_id, user_id
                    )
                    return session_domain is not None
                finally:
                    db.close()
            except Exception:
                return False

        return validate_with_database
    else:
        log.debug("No database configured - using basic session validation")

        def validate_without_database(session_id: str, user_id: str) -> bool:
            if not session_id or not session_id.startswith("web-session-"):
                return False
            return bool(user_id)

        return validate_without_database


def get_db_optional() -> Generator[Session | None, None, None]:
    """Optional database dependency that returns None if database is not configured."""
    if SessionLocal is None:
        log.debug("Database not configured, returning None")
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

def get_project_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> ProjectService:
    """Dependency factory for ProjectService."""
    return ProjectService(component=component)


def get_project_service_optional(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> ProjectService | None:
    """Optional project service dependency that returns None if database is not configured."""
    if SessionLocal is None:
        log.debug("Database not configured, projects unavailable")
        return None
    return ProjectService(component=component)

def get_session_business_service_optional(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SessionService | None:
    """Optional session service dependency that returns None if database is not configured."""
    if SessionLocal is None:
        log.debug(
            "Database not configured, returning None for session service"
        )
        return None
    return SessionService(component=component)


def get_audio_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> AudioService:
    """FastAPI dependency to get an instance of AudioService."""
    log.debug("[get_audio_service] called")
    # AudioService expects app_config which contains the speech configuration
    app_config = component.component_config.get('app_config', {}) if hasattr(component, 'component_config') else {}
    log.debug(f"[get_audio_service] app_config keys: {app_config.keys()}")
    return AudioService(config=app_config)



def get_user_display_name(
    request: Request,
    user_id: str = Depends(get_user_id),
) -> str:
    """
    FastAPI dependency to get a user's display name.
    Returns email if available, otherwise returns user_id.
    """
    # Try to get user info from request state (set by AuthMiddleware)
    if hasattr(request.state, "user") and request.state.user:
        user_info = request.state.user
        # Try email first, then name, then fall back to user_id
        return user_info.get("email") or user_info.get("name") or user_id
    
    return user_id
