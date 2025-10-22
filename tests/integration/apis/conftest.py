"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import logging
import pytest
import sqlalchemy as sa
from contextvars import ContextVar
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)
from sqlalchemy import text

from .infrastructure.database_inspector import DatabaseInspector
from .infrastructure.database_manager import (
    DatabaseManager,
    DatabaseProviderFactory,
    SqliteProvider,
)
from .infrastructure.gateway_adapter import GatewayAdapter

log = logging.getLogger(__name__)

# Custom header for test user identification
# Each TestClient injects this header with their user ID
# Auth overrides read this header to determine which user made the request
TEST_USER_HEADER = "X-Test-User-Id"


def _patch_mock_auth_header_aware(factory):
    """
    Patches the mock component's authenticate_and_enrich_user to be header-aware.
    This enables multi-user testing by reading X-Test-User-Id header.
    """
    if not hasattr(factory, "mock_component"):
        return

    from unittest.mock import AsyncMock

    async def mock_authenticate_from_header(request):
        # Check for test header first (for multi-user tests)
        test_user_id = request.headers.get(TEST_USER_HEADER, "sam_dev_user")
        if test_user_id == "secondary_user":
            return {
                "id": "secondary_user",
                "name": "Secondary User",
                "email": "secondary@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }
        # Default to primary user
        return {
            "id": "sam_dev_user",
            "name": "Sam Dev User",
            "email": "sam@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }

    factory.mock_component.authenticate_and_enrich_user = AsyncMock(
        side_effect=mock_authenticate_from_header
    )
    log.info("Patched mock_component.authenticate_and_enrich_user to be header-aware.")


def _patch_mock_component_config(factory):
    """
    Explicitly patches the mock component's get_config method to ensure it returns
    a string for the 'name' key, preventing TypeError in urlunparse.
    """
    if not hasattr(factory, "mock_component"):
        return

    original_side_effect = factory.mock_component.get_config.side_effect

    def get_config_side_effect(key, default=None):
        if key == "name":
            # Force return a string for the app name
            return "A2A_WebUI_App"

        # Fallback to the original side_effect if it exists
        if callable(original_side_effect):
            return original_side_effect(key, default)

        # Fallback to default value
        return default

    factory.mock_component.get_config.side_effect = get_config_side_effect
    log.info("Patched mock_component.get_config to handle 'name' key explicitly.")


def _patch_mock_artifact_service(factory):
    """Patches the mock artifact service to make save_artifact awaitable."""
    if not hasattr(factory, "mock_component"):
        return

    artifact_service_mock = factory.mock_component.get_shared_artifact_service()
    if artifact_service_mock:
        # The save_artifact method is awaited, so it must be an AsyncMock in tests.
        # It should return a version number.
        artifact_service_mock.save_artifact = AsyncMock(return_value=1)


@pytest.fixture(scope="session")
def api_client_factory():
    """Creates a factory for the main API client."""
    factory = WebUIBackendFactory()
    yield factory
    factory.teardown()


@pytest.fixture(scope="session", autouse=True)
def setup_multi_user_auth(api_client_factory):
    """Sets up multi-user authentication for all API clients (autouse fixture)."""
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    from solace_agent_mesh.gateway.http_sse.dependencies import get_user_id
    from fastapi import Request

    app = api_client_factory.app

    async def override_get_current_user(request: Request) -> dict:
        # Get user ID from custom test header - this is request-scoped and thread-safe
        user_id = request.headers.get(TEST_USER_HEADER, "sam_dev_user")

        if user_id == "secondary_user":
            return {
                "id": "secondary_user",
                "name": "Secondary User",
                "email": "secondary@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }
        else:
            return {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }

    def override_get_user_id(request: Request) -> str:
        return request.headers.get(TEST_USER_HEADER, "sam_dev_user")

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_user_id] = override_get_user_id

    yield


@pytest.fixture(scope="session")
def api_client(db_provider, api_client_factory, setup_multi_user_auth):
    """Creates a TestClient that uses the same app instance as the db_provider."""
    # For SQLite, use the original api_client_factory
    if isinstance(db_provider, SqliteProvider):
        app = api_client_factory.app
    else:
        # For containerized databases, use the WebUIBackendFactory we created
        app = db_provider._webui_factory.app

    # Create a header-based client that injects user ID via custom header
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            # Inject user ID via custom header for every request
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)

    client = HeaderBasedTestClient(app, "sam_dev_user")
    print(
        f"[API Tests] FastAPI TestClient created from {db_provider.provider_type} db_provider"
    )

    yield client


@pytest.fixture(scope="session")
def secondary_api_client(api_client_factory, setup_multi_user_auth):
    """Creates a secondary TestClient using the SAME app/database but different user auth."""
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            # Inject user ID via custom header for every request
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)

    client = HeaderBasedTestClient(api_client_factory.app, "secondary_user")
    print("[API Tests] Secondary FastAPI TestClient created (same database, different user)")

    yield client


@pytest.fixture(scope="session")
def secondary_gateway_adapter(database_manager: DatabaseManager):
    """Creates a GatewayAdapter for secondary user (same database)."""
    return GatewayAdapter(database_manager)


@pytest.fixture(scope="session")
def secondary_database_inspector(database_manager):
    """Creates a DatabaseInspector for secondary user (same database)."""
    return DatabaseInspector(database_manager)


@pytest.fixture(autouse=True)
def clean_database_between_tests(database_manager: DatabaseManager):
    """Cleans database state between tests (used by both primary and secondary clients)"""
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    yield
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    print("[API Tests] Database cleaned between tests")


def _clean_main_database(engine):
    """Clean the main API test database using SQLAlchemy Core"""
    with engine.connect() as connection, connection.begin():
        metadata = sa.MetaData()
        metadata.reflect(bind=connection)

        # Handle database-specific foreign key constraints
        db_url = str(connection.engine.url)
        if db_url.startswith("sqlite"):
            connection.execute(text("PRAGMA foreign_keys=OFF"))
        elif db_url.startswith("postgresql"):
            # PostgreSQL handles FK constraints differently - no need to disable
            pass

        # Delete from all tables except alembic_version
        for table in reversed(metadata.sorted_tables):
            if table.name == "alembic_version":
                continue
            connection.execute(table.delete())

        # Re-enable foreign key constraints
        if db_url.startswith("sqlite"):
            connection.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture(scope="session")
def test_agents_list() -> list[str]:
    """List of test agent names for parameterized tests"""
    return ["TestAgent", "TestPeerAgentA", "TestPeerAgentB", "TestPeerAgentC"]


# Parameterized database provider fixtures
@pytest.fixture(scope="session", params=["sqlite", "postgresql"])
def db_provider_type(request):
    """Parameterized fixture for database provider type.

    To run against multiple databases, use:
    pytest --db-provider=sqlite,postgresql

    Or override this fixture in specific test files.
    """
    return request.param


@pytest.fixture(scope="session", params=["sqlite", "postgresql"])
def multi_db_provider_type(request):
    """Parameterized fixture that runs tests against all database types."""
    return request.param


# Simple infrastructure fixtures for infrastructure tests
@pytest.fixture(scope="session")
def db_provider(test_agents_list: list[str], api_client_factory, db_provider_type):
    """Database provider fixture that creates the app and all databases."""

    # Create provider based on type
    provider = DatabaseProviderFactory.create_provider(db_provider_type)

    # All providers now use WebUIBackendFactory integration for proper schema setup
    if isinstance(provider, SqliteProvider):
        # SQLite: Use WebUIBackendFactory's engine and URL
        provider.setup(
            agent_names=test_agents_list,
            db_url=api_client_factory.db_url,
            engine=api_client_factory.engine,
        )
        _patch_mock_auth_header_aware(api_client_factory)
        _patch_mock_artifact_service(api_client_factory)
        _patch_mock_component_config(api_client_factory)
    else:
        # PostgreSQL: Setup container first, then create WebUIBackendFactory with container URL
        provider.setup(agent_names=test_agents_list)

        # Create a WebUIBackendFactory using the container's gateway database
        # Get the URL directly from the provider to ensure proper credentials
        if hasattr(provider, "_container") and provider._container:
            # For testcontainer providers, build URL with correct credentials
            host = provider._container.get_container_host_ip()
            port = provider._container.get_exposed_port(5432)
            user = provider._container.username
            password = provider._container.password
            database = provider._container.dbname

            gateway_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        else:
            # Fallback to engine URL
            gateway_url = str(provider.get_sync_gateway_engine().url)

        # Use the same gateway_id as the original factory to ensure component compatibility
        factory = WebUIBackendFactory(
            db_url=gateway_url, gateway_id=api_client_factory.mock_component.gateway_id
        )
        _patch_mock_auth_header_aware(factory)
        _patch_mock_artifact_service(factory)
        _patch_mock_component_config(factory)

        # Store factory for cleanup
        provider._webui_factory = factory

        # Force update the global dependencies to use the new component for tests to work
        from solace_agent_mesh.gateway.http_sse import dependencies

        # Force set the component instance (bypass the None check)
        dependencies.sac_component_instance = factory.mock_component
        dependencies.SessionLocal = None  # Reset session factory
        dependencies.init_database(gateway_url)  # Re-initialize with new database

    yield provider
    provider.teardown()




@pytest.fixture(scope="session")
def database_manager(db_provider):
    """Creates a new unified DatabaseManager."""
    return DatabaseManager(db_provider)


# Multi-database test fixtures
@pytest.fixture(scope="session")
def multi_db_provider(test_agents_list: list[str], multi_db_provider_type):
    """Parameterized fixture that runs tests against all database types.

    This fixture creates independent database instances for each provider type.
    Use this for tests that should run against all supported databases.
    """
    provider = DatabaseProviderFactory.create_provider(multi_db_provider_type)
    provider.setup(agent_names=test_agents_list)
    yield provider
    provider.teardown()


@pytest.fixture(scope="session")
def multi_database_manager(multi_db_provider):
    """Creates a DatabaseManager for multi-database parameterized tests."""
    return DatabaseManager(multi_db_provider)


@pytest.fixture(scope="session")
def gateway_adapter(database_manager: DatabaseManager):
    """Creates a new GatewayAdapter for the primary provider."""
    return GatewayAdapter(database_manager)


@pytest.fixture(scope="session")
def database_inspector(database_manager):
    """Creates a new DatabaseInspector."""
    return DatabaseInspector(database_manager)


# Export FastAPI testing fixtures
__all__ = [
    "api_client",
    "api_client_factory",
    "secondary_api_client",
    "clean_database_between_tests",
    "test_agents_list",
    "db_provider_type",
    "multi_db_provider_type",
    "db_provider",
    "database_manager",
    "gateway_adapter",
    "database_inspector",
    "secondary_gateway_adapter",
    "secondary_database_inspector",
    "multi_db_provider",
    "multi_database_manager",
]
