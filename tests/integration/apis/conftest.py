"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import pytest
import sqlalchemy as sa
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


@pytest.fixture(scope="session")
def api_client(db_provider, api_client_factory):
    """Creates a TestClient that uses the same app instance as the db_provider."""

    # For SQLite, use the original api_client_factory
    if isinstance(db_provider, SqliteProvider):
        app = api_client_factory.app
    else:
        # For containerized databases, use the WebUIBackendFactory we created
        app = db_provider._webui_factory.app

    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user

    async def override_get_current_user() -> dict:
        return {
            "id": "sam_dev_user",
            "name": "Sam Dev User",
            "email": "sam@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    print(
        f"[API Tests] FastAPI TestClient created from {db_provider.provider_type} db_provider"
    )
    try:
        yield client
    finally:
        app.dependency_overrides = {}


@pytest.fixture(scope="session")
def secondary_api_client_factory():
    """Creates a factory for the secondary API client."""
    secondary_user = {
        "id": "secondary_user",
        "name": "Secondary User",
        "email": "secondary@dev.local",
        "authenticated": True,
        "auth_method": "development",
    }
    factory = WebUIBackendFactory(user=secondary_user)
    yield factory
    factory.teardown()


@pytest.fixture(scope="session")
def secondary_api_client(secondary_db_provider, secondary_api_client_factory):
    """Creates a secondary TestClient that uses the secondary_db_provider."""

    # For SQLite, use the original secondary_api_client_factory
    if isinstance(secondary_db_provider, SqliteProvider):
        app = secondary_api_client_factory.app
    else:
        # For containerized databases, use the WebUIBackendFactory we created
        app = secondary_db_provider._webui_factory.app

    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user

    async def override_get_current_user() -> dict:
        return {
            "id": "secondary_user",
            "name": "Secondary User",
            "email": "secondary@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    print(
        f"[API Tests] Secondary FastAPI TestClient created from {secondary_db_provider.provider_type} secondary_db_provider."
    )
    try:
        yield client
    finally:
        app.dependency_overrides = {}


@pytest.fixture(scope="session")
def secondary_database_manager(secondary_db_provider):
    """Creates a new unified DatabaseManager for the secondary provider."""
    return DatabaseManager(secondary_db_provider)


@pytest.fixture(scope="session")
def secondary_gateway_adapter(secondary_database_manager: DatabaseManager):
    """Creates a new GatewayAdapter for the secondary provider."""
    return GatewayAdapter(secondary_database_manager)


@pytest.fixture(scope="session")
def secondary_database_inspector(secondary_database_manager):
    """Creates a new DatabaseInspector for the secondary provider."""
    return DatabaseInspector(secondary_database_manager)


@pytest.fixture(autouse=True)
def clean_database_between_tests(database_manager: DatabaseManager):
    """Cleans database state between tests"""
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    yield
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    print("[API Tests] Database cleaned between tests")


@pytest.fixture(autouse=True)
def clean_secondary_database_between_tests(secondary_database_manager: DatabaseManager):
    """Cleans the secondary database state between tests"""
    _clean_main_database(secondary_database_manager.provider.get_sync_gateway_engine())
    yield
    _clean_main_database(secondary_database_manager.provider.get_sync_gateway_engine())
    print("[API Tests] Secondary database cleaned between tests")


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
        _patch_mock_artifact_service(api_client_factory)
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
        _patch_mock_artifact_service(factory)

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
def secondary_db_provider(
    test_agents_list: list[str], secondary_api_client_factory, db_provider_type
):
    """A second, isolated database provider for multi-user tests."""

    # Create provider based on type
    provider = DatabaseProviderFactory.create_provider(db_provider_type)

    # All providers now use WebUIBackendFactory integration for proper schema setup
    if isinstance(provider, SqliteProvider):
        # SQLite: Use WebUIBackendFactory's engine and URL
        provider.setup(
            agent_names=test_agents_list,
            db_url=secondary_api_client_factory.db_url,
            engine=secondary_api_client_factory.engine,
        )
        _patch_mock_artifact_service(secondary_api_client_factory)
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

        secondary_user = {
            "id": "secondary_user",
            "name": "Secondary User",
            "email": "secondary@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }
        factory = WebUIBackendFactory(db_url=gateway_url, user=secondary_user)
        _patch_mock_artifact_service(factory)

        # Store factory for cleanup
        provider._webui_factory = factory

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
    "secondary_api_client_factory",
    "clean_database_between_tests",
    "clean_secondary_database_between_tests",
    "test_agents_list",
    "db_provider_type",
    "multi_db_provider_type",
    "db_provider",
    "secondary_db_provider",
    "database_manager",
    "gateway_adapter",
    "database_inspector",
    "secondary_database_manager",
    "secondary_gateway_adapter",
    "secondary_database_inspector",
    "multi_db_provider",
    "multi_database_manager",
]
