from collections.abc import Callable
from typing import Any, TypeVar

from ...application.services.session_service import SessionService
from ...domain.repositories.session_repository import (
    IMessageRepository,
    ISessionRepository,
)
from ...infrastructure.persistence import database_service as db_service_module
from ...infrastructure.persistence.database_service import DatabaseService
from ...infrastructure.repositories.session_repository import (
    MessageRepository,
    SessionRepository,
)

T = TypeVar("T")


class DIContainer:
    """Dependency injection container."""

    def __init__(self):
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable] = {}
        self._singletons: dict[str, Any] = {}

    def register_singleton(self, service_type: type, instance: Any) -> None:
        self._singletons[service_type.__name__] = instance

    def register_factory(self, service_type: type, factory: Callable) -> None:
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

    def __init__(self, database_url: str | None = None):
        self.container = DIContainer()
        self.database_url = database_url
        self.has_database = database_url is not None
        self._setup_dependencies()

    def _setup_dependencies(self) -> None:
        if self.has_database:
            database_service = DatabaseService(self.database_url)
            self.container.register_singleton(DatabaseService, database_service)
            db_service_module.database_service = database_service

            session_repository = SessionRepository(database_service)
            message_repository = MessageRepository(database_service)

            self.container.register_singleton(ISessionRepository, session_repository)
            self.container.register_singleton(IMessageRepository, message_repository)

            def session_service_factory():
                return SessionService(session_repository, message_repository)

            self.container.register_factory(SessionService, session_service_factory)

    def get_database_service(self) -> DatabaseService | None:
        if not self.has_database:
            return None
        return self.container.get(DatabaseService)

    def get_session_service(self) -> SessionService | None:
        if not self.has_database:
            return None
        return self.container.get(SessionService)


# Global container instance
_container: ApplicationContainer | None = None


def initialize_container(database_url: str | None = None) -> ApplicationContainer:
    global _container
    _container = ApplicationContainer(database_url)

    # Only create tables if database is available
    if _container.has_database:
        database_service = _container.get_database_service()
        if database_service:
            database_service.create_tables()

    return _container


def get_container() -> ApplicationContainer:
    if _container is None:
        raise RuntimeError(
            "Container not initialized. Call initialize_container() first."
        )
    return _container
