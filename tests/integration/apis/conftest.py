"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import logging
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

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
            return "A2A_WebUI_App"
        elif key == "projects":
            return {"enabled": True}
        elif key == "gateway_max_upload_size_bytes":
            return 100 * 1024 * 1024  # Default 100MB for tests

        if callable(original_side_effect):
            return original_side_effect(key, default)

        return default

    factory.mock_component.get_config.side_effect = get_config_side_effect
    log.info("Patched mock_component.get_config to handle 'name' and 'projects' keys.")


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
def api_client_factory(db_provider):
    """Returns the WebUIBackendFactory created by db_provider."""
    # The factory is created by db_provider using the correct database
    return db_provider.factory


@pytest.fixture(scope="session")
def api_client(db_provider, api_client_factory):
    """Creates a TestClient using the api_client_factory app (works for both SQLite and PostgreSQL)."""
    app = api_client_factory.app

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
def secondary_api_client(api_client_factory):
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
    print(
        "[API Tests] Secondary FastAPI TestClient created (same database, different user)"
    )

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
def db_provider(test_agents_list: list[str], db_provider_type):
    """Database provider fixture - creates the database AND the WebUIBackendFactory."""
    # Create provider based on type and let it create its own database
    provider = DatabaseProviderFactory.create_provider(db_provider_type)
    provider.setup(agent_names=test_agents_list)

    # Get database URL from the provider (with credentials for PostgreSQL)
    if hasattr(provider, "get_gateway_url_with_credentials"):
        db_url = provider.get_gateway_url_with_credentials()
    else:
        db_url = str(provider.get_sync_gateway_engine().url)

    # Create ONE WebUIBackendFactory for this database (SQLite or PostgreSQL)
    factory = WebUIBackendFactory(db_url=db_url)

    # Apply all patches to make it test-ready
    _patch_mock_auth_header_aware(factory)
    _patch_mock_artifact_service(factory)
    _patch_mock_component_config(factory)

    # Set up multi-user testing overrides (centralized in factory)
    factory.setup_multi_user_testing(provider, TEST_USER_HEADER)

    # Store factory on provider so api_client_factory can access it
    provider.factory = factory

    log.info(f"[API Tests] Created unified WebUIBackendFactory with {provider.provider_type} database")

    yield provider

    factory.teardown()
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


@pytest.fixture
def db_session_factory(api_client_factory):
    """
    Provides the SQLAlchemy session factory that matches the current database provider.
    This ensures tests use the same database as the api_client (SQLite or PostgreSQL).
    """
    return api_client_factory.Session


@pytest.fixture
def db_engine(api_client_factory):
    """
    Provides the SQLAlchemy engine that matches the current database provider.
    This ensures tests query the same database as the api_client.
    """
    return api_client_factory.engine


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
