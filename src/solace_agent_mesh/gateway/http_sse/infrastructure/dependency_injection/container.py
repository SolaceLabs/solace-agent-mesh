"""
Modern dependency injection container using industry-standard patterns.
Simplified approach using SQLAlchemy context managers instead of complex factories.
"""

from typing import Dict, Any, Callable, TypeVar, Optional, Generator
from sqlalchemy.orm import Session

# Modern imports
from ...data.persistence.database_service import DatabaseService
from ...data.persistence import database_service as db_service_module
from ...business.services.session_service import ModernSessionService, SessionService
from ...business.services.user_service import UserService

# Legacy imports for backward compatibility
from ...data.repositories.session_repository import ISessionRepository, IMessageRepository, SessionRepository, MessageRepository
from ...data.repositories.user_repository import IUserRepository, UserRepository

T = TypeVar('T')


class DIContainer:
    """Dependency injection container."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register_singleton(self, service_type: type, instance: Any) -> None:
        """Register a singleton instance."""
        self._singletons[service_type.__name__] = instance
    
    def register_factory(self, service_type: type, factory: Callable) -> None:
        """Register a factory function for creating instances."""
        self._factories[service_type.__name__] = factory
    
    def register_transient(self, service_type: type, implementation: type) -> None:
        """Register a transient service (new instance each time)."""
        self._services[service_type.__name__] = implementation
    
    def get(self, service_type: type) -> Any:
        """Get an instance of the requested service."""
        service_name = service_type.__name__
        
        # Check singletons first
        if service_name in self._singletons:
            return self._singletons[service_name]
        
        # Check factories
        if service_name in self._factories:
            return self._factories[service_name]()
        
        # Check transient services
        if service_name in self._services:
            implementation = self._services[service_name]
            return self._create_instance(implementation)
        
        raise ValueError(f"Service {service_name} is not registered")
    
    def _create_instance(self, implementation: type) -> Any:
        """Create an instance with dependency injection."""
        # This is a simplified implementation
        # In a production system, you'd use a more sophisticated approach
        # like inspecting constructor parameters and resolving them automatically
        return implementation()


class ApplicationContainer:
    """Application-specific dependency injection container."""
    
    def __init__(self, database_url: str):
        self.container = DIContainer()
        self.database_url = database_url
        self._setup_dependencies()
    
    def _setup_dependencies(self) -> None:
        """Setup all application dependencies."""
        
        # Database service (singleton)
        database_service = DatabaseService(self.database_url)
        self.container.register_singleton(DatabaseService, database_service)
        
        # Set the global database service instance for legacy dependencies
        db_service_module.database_service = database_service
        
        # Repository factories (each request gets a new instance with fresh DB session)
        def create_session_repository():
            session = database_service.SessionLocal()
            return SessionRepository(session)
        
        def create_message_repository():
            session = database_service.SessionLocal()
            return MessageRepository(session)
        
        def create_user_repository():
            session = database_service.SessionLocal()
            return UserRepository(session)
        
        self.container.register_factory(ISessionRepository, create_session_repository)
        self.container.register_factory(IMessageRepository, create_message_repository)
        self.container.register_factory(IUserRepository, create_user_repository)
        
        # Business service factories
        self.container.register_factory(
            SessionService,
            lambda: SessionService(
                self.container.get(ISessionRepository),
                self.container.get(IMessageRepository)
            )
        )
        
        self.container.register_factory(
            UserService,
            lambda: UserService(
                self.container.get(IUserRepository)
            )
        )
    
    def get_session_service(self) -> SessionService:
        """Get session service instance."""
        return self.container.get(SessionService)
    
    def get_user_service(self) -> UserService:
        """Get user service instance."""
        return self.container.get(UserService)
    
    def get_database_service(self) -> DatabaseService:
        """Get database service instance."""
        return self.container.get(DatabaseService)


# Global container instance
_container: Optional[ApplicationContainer] = None


def initialize_container(database_url: str) -> ApplicationContainer:
    """Initialize the global DI container."""
    global _container
    _container = ApplicationContainer(database_url)
    
    # Initialize database tables
    database_service = _container.get_database_service()
    database_service.create_tables()
    
    return _container


def get_container() -> ApplicationContainer:
    """Get the global DI container."""
    if _container is None:
        raise RuntimeError("Container not initialized. Call initialize_container() first.")
    return _container


# Modern FastAPI dependency functions using industry standards
def get_session_service() -> SessionService:
    """
    FastAPI dependency for getting session service.
    
    Uses the modern approach where the service manages its own transactions
    via DatabaseService context managers. No manual session management needed.
    """
    container = get_container()
    database_service = container.get_database_service()
    
    # Return service that handles its own transactions internally
    return SessionService(db_service=database_service)


def get_modern_session_service() -> ModernSessionService:
    """
    FastAPI dependency for getting the modern session service.
    
    This is the recommended service to use for new code.
    """
    container = get_container()
    database_service = container.get_database_service()
    
    # Return modern service that handles its own transactions internally
    return ModernSessionService(database_service)


def get_user_service() -> UserService:
    """
    FastAPI dependency for getting user service.
    
    Note: UserService will be modernized in a future update.
    """
    container = get_container()
    database_service = container.get_database_service()
    
    # For now, return legacy service (will be modernized later)
    with database_service.session_scope() as db_session:
        user_repo = UserRepository(db_session)
        service = UserService(user_repo)
        yield service


# Legacy compatibility functions - gradually migrate away from these
def get_legacy_session_service():
    """
    DEPRECATED: Legacy FastAPI dependency.
    Use get_session_service() or get_modern_session_service() instead.
    """
    container = get_container()
    database_service = container.get_database_service()
    
    # Use legacy dependency injection pattern
    with database_service.session_scope() as db_session:
        session_repo = SessionRepository(db_session)
        message_repo = MessageRepository(db_session)
        service = SessionService(session_repo, message_repo, db_service=database_service)
        yield service