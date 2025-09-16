"""
Defines FastAPI dependency injectors to access shared resources
managed by the WebUIBackendComponent.
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from fastapi import Depends, HTTPException, Request, status
from solace_ai_connector.common.log import log
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ...common.agent_registry import AgentRegistry
from ...common.middleware.config_resolver import ConfigResolver
from ...common.services.identity_service import BaseIdentityService
from ...core_a2a.service import CoreA2AService
from ...gateway.base.task_context import TaskContextManager
from ...gateway.http_sse.services.agent_card_service import AgentCardService
from ...gateway.http_sse.services.people_service import PeopleService
from ...gateway.http_sse.services.task_service import TaskService
from ...gateway.http_sse.session_manager import SessionManager
from ...gateway.http_sse.sse_manager import SSEManager
from .repository import Message, MessageRepository, SessionRepository
from .services.session_service import SessionService

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
        log.info("[Dependencies] SAC Component instance provided.")
    else:
        log.warning("[Dependencies] SAC Component instance already set.")


def init_database(database_url: str):
    """Initialize database with direct sessionmaker."""
    global SessionLocal
    if SessionLocal is None:
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        log.info("[Dependencies] Database initialized.")
    else:
        log.warning("[Dependencies] Database already initialized.")


def set_api_config(config: dict[str, Any]):
    """Called during startup to provide API configuration."""
    global api_config
    if api_config is None:
        api_config = config
        log.info("[Dependencies] API configuration provided.")
    else:
        log.warning("[Dependencies] API configuration already set.")


def get_sac_component() -> "WebUIBackendComponent":
    """FastAPI dependency to get the SAC component instance."""
    if sac_component_instance is None:
        log.critical(
            "[Dependencies] SAC Component instance accessed before it was set!"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend component not yet initialized.",
        )
    return sac_component_instance


def get_api_config() -> dict[str, Any]:
    """FastAPI dependency to get the API configuration."""
    if api_config is None:
        log.critical("[Dependencies] API configuration accessed before it was set!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API configuration not yet initialized.",
        )
    return api_config


def get_agent_registry(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> AgentRegistry:
    """FastAPI dependency to get the AgentRegistry."""
    log.debug("[Dependencies] get_agent_registry called")
    return component.get_agent_registry()


def get_sse_manager(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SSEManager:
    """FastAPI dependency to get the SSEManager."""
    log.debug("[Dependencies] get_sse_manager called")
    return component.get_sse_manager()


def get_session_manager(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SessionManager:
    """FastAPI dependency to get the SessionManager."""
    log.debug("[Dependencies] get_session_manager called")
    return component.get_session_manager()


def get_user_id_callable(
    session_manager: SessionManager = Depends(get_session_manager),
) -> Callable:
    """Dependency that provides the callable for getting user_id (client_id)."""
    log.debug("[Dependencies] Providing user_id callable")
    return session_manager.dep_get_client_id()


def ensure_session_id_callable(
    session_manager: SessionManager = Depends(get_session_manager),
) -> Callable:
    """Dependency that provides the callable for ensuring session_id."""
    log.debug("[Dependencies] Providing ensure_session_id callable")
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
    log.debug("[Dependencies] Resolving user_id string")

    # AuthMiddleware should always set user state for both auth enabled/disabled cases
    if hasattr(request.state, "user") and request.state.user:
        user_id = request.state.user.get("id")
        if user_id:
            log.debug(f"[Dependencies] Using user ID from AuthMiddleware: {user_id}")
            return user_id
        else:
            log.error(
                "[Dependencies] request.state.user exists but has no 'id' field: %s. This indicates a bug in AuthMiddleware.",
                request.state.user,
            )

    # If we reach here, AuthMiddleware didn't set user state properly
    use_authorization = session_manager.use_authorization

    if use_authorization:
        # When OAuth is enabled, we should never reach here - AuthMiddleware should have handled authentication
        log.error(
            "[Dependencies] OAuth is enabled but no authenticated user found. This indicates an authentication failure or middleware bug."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required but user not found",
        )
    else:
        # When auth is disabled, use development fallback user
        fallback_id = "sam_dev_user"
        log.info(
            "[Dependencies] Authorization disabled and no user in request state, using fallback user: %s",
            fallback_id,
        )
        return fallback_id


def ensure_session_id(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> str:
    """FastAPI dependency that directly returns the ensured session_id string."""
    log.debug("[Dependencies] Resolving ensured session_id string")
    return session_manager.ensure_a2a_session(request)


def get_identity_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> BaseIdentityService | None:
    """FastAPI dependency to get the configured IdentityService instance."""
    log.debug("[Dependencies] get_identity_service called")
    return component.identity_service


def get_people_service(
    identity_service: BaseIdentityService | None = Depends(get_identity_service),
) -> PeopleService:
    """FastAPI dependency to get an instance of PeopleService."""
    log.debug("[Dependencies] get_people_service called")
    return PeopleService(identity_service=identity_service)


PublishFunc = Callable[[str, dict, dict | None], None]


def get_publish_a2a_func(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> PublishFunc:
    """FastAPI dependency to get the component's publish_a2a method."""
    log.debug("[Dependencies] get_publish_a2a_func called")
    return component.publish_a2a


def get_namespace(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> str:
    """FastAPI dependency to get the namespace."""
    log.debug("[Dependencies] get_namespace called")
    return component.get_namespace()


def get_gateway_id(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> str:
    """FastAPI dependency to get the Gateway ID."""
    log.debug("[Dependencies] get_gateway_id called")
    return component.get_gateway_id()


def get_config_resolver(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> ConfigResolver:
    """FastAPI dependency to get the ConfigResolver."""
    log.debug("[Dependencies] get_config_resolver called")
    return component.get_config_resolver()


def get_app_config(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> dict[str, Any]:
    """
    FastAPI dependency to safely get the application configuration dictionary.
    """
    log.debug("[Dependencies] get_app_config called")
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
    log.debug(f"[Dependencies] get_user_config called for user_id: {user_id}")
    gateway_context = {
        "gateway_id": component.gateway_id,
        "gateway_app_config": app_config,
        "request": request,
    }
    return await config_resolver.resolve_user_config(
        user_id, gateway_context, app_config
    )


def get_shared_artifact_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> BaseArtifactService | None:
    """FastAPI dependency to get the shared ArtifactService."""
    log.debug("[Dependencies] get_shared_artifact_service called")
    return component.get_shared_artifact_service()


def get_embed_config(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> dict[str, Any]:
    """FastAPI dependency to get embed-related configuration."""
    log.debug("[Dependencies] get_embed_config called")
    return component.get_embed_config()


def get_core_a2a_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> CoreA2AService:
    """FastAPI dependency to get the CoreA2AService."""
    log.debug("[Dependencies] get_core_a2a_service called")
    core_service = component.get_core_a2a_service()
    if core_service is None:
        log.critical("[Dependencies] CoreA2AService accessed before initialization!")
        raise HTTPException(status_code=503, detail="Core service not ready.")
    return core_service


def get_task_context_manager_from_component(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> TaskContextManager:
    """FastAPI dependency to get the TaskContextManager from the component."""
    log.debug("[Dependencies] get_task_context_manager_from_component called")
    if component.task_context_manager is None:
        log.critical(
            "[Dependencies] TaskContextManager accessed before initialization!"
        )
        raise HTTPException(status_code=503, detail="Task context manager not ready.")
    return component.task_context_manager


def get_agent_card_service(
    registry: AgentRegistry = Depends(get_agent_registry),
) -> AgentCardService:
    """FastAPI dependency to get an instance of AgentCardService."""
    log.debug("[Dependencies] get_agent_card_service called")
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
    log.debug("[Dependencies] get_task_service called")
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


def get_session_business_service(
    db: Session = Depends(get_db),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> SessionService:
    log.debug("[Dependencies] get_session_business_service called")

    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)
    return SessionService(session_repository, message_repository, component)


@contextmanager
def create_session_service_with_transaction():
    """Create session data access service with its own transaction for non-HTTP contexts."""
    if SessionLocal is None:
        raise RuntimeError("Database not configured")

    db = SessionLocal()
    try:
        session_repository = SessionRepository(db)
        message_repository = MessageRepository(db)

        # Create a simple data access object for transaction contexts
        # This provides the basic repository operations without business logic
        class SessionDataAccess:
            def __init__(self, session_repo, message_repo):
                self.session_repository = session_repo
                self.message_repository = message_repo

            def add_message_to_session(
                self,
                session_id,
                user_id,
                message,
                sender_type,
                sender_name,
                agent_id=None,
            ):
                # Simple data access - just save the message
                from uuid import uuid4

                from .shared.enums import MessageType
                from .shared import now_epoch_ms

                message_entity = Message(
                    id=str(uuid4()),
                    session_id=session_id,
                    message=message,
                    sender_type=sender_type,
                    sender_name=sender_name,
                    message_type=MessageType.TEXT,
                    created_time=now_epoch_ms(),
                )
                return self.message_repository.save(message_entity)

            def get_session(self, session_id, user_id):
                # Use the session repository to find the session
                return self.session_repository.find_user_session(session_id, user_id)

            def create_session(
                self, user_id, name=None, agent_id=None, session_id=None
            ):
                # Create a new session using the session repository
                from uuid import uuid4

                from .repository.entities import Session
                from .shared import now_epoch_ms

                if not session_id:
                    session_id = str(uuid4())

                # Leave name as None/empty - frontend will generate display name if needed

                now_ms = now_epoch_ms()
                session = Session(
                    id=session_id,
                    user_id=user_id,
                    name=name,
                    agent_id=agent_id,
                    created_time=now_ms,
                    updated_time=now_ms,
                )

                return self.session_repository.save(session)

        session_service = SessionDataAccess(session_repository, message_repository)
        yield session_service, db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session_validator(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> Callable[[str, str], bool]:
    log.debug("[Dependencies] get_session_validator called")

    if SessionLocal:
        log.debug("Using database-backed session validation")

        def validate_with_database(session_id: str, user_id: str) -> bool:
            try:
                with create_session_service_with_transaction() as (session_service, db):
                    session_domain = session_service.get_session(session_id, user_id)
                    return session_domain is not None
            except:
                return False

        return validate_with_database
    else:
        log.debug("No database configured - using basic session validation")

        def validate_without_database(session_id: str, user_id: str) -> bool:
            if not session_id or not session_id.startswith("web-session-"):
                return False
            return bool(user_id)

        return validate_without_database
