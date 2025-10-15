"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import pytest
import sqlalchemy as sa

from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)
from sqlalchemy import text

from .infrastructure.database_manager import DatabaseManager, SqliteProvider
from .infrastructure.gateway_adapter import GatewayAdapter
from .infrastructure.database_inspector import DatabaseInspector


@pytest.fixture(scope="session")
def api_client_factory():
    """Creates a factory for the main API client."""
    factory = WebUIBackendFactory()
    yield factory
    factory.teardown()


@pytest.fixture(scope="session")
def api_client(api_client_factory):
    """Creates a TestClient that uses the same app instance as the db_provider."""
    client = TestClient(api_client_factory.app)
    print("[API Tests] FastAPI TestClient created from db_provider")
    yield client


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
def secondary_api_client(secondary_api_client_factory):
    """Creates a secondary TestClient that uses the secondary_db_provider."""
    client = TestClient(secondary_api_client_factory.app)
    print("[API Tests] Secondary FastAPI TestClient created from secondary_db_provider.")
    yield client


@pytest.fixture(scope="session")
def secondary_database_manager(secondary_db_provider: SqliteProvider):
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
    with engine.connect() as connection:
        with connection.begin():
            metadata = sa.MetaData()
            metadata.reflect(bind=connection)
            if str(connection.engine.url).startswith("sqlite"):
                connection.execute(text("PRAGMA foreign_keys=OFF"))
            for table in reversed(metadata.sorted_tables):
                if table.name == "alembic_version":
                    continue
                connection.execute(table.delete())
            if str(connection.engine.url).startswith("sqlite"):
                connection.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture(scope="session")
def test_agents_list() -> list[str]:
    """List of test agent names for parameterized tests"""
    return ["TestAgent", "TestPeerAgentA", "TestPeerAgentB", "TestPeerAgentC"]



# Simple infrastructure fixtures for infrastructure tests
@pytest.fixture(scope="session")
def db_provider(test_agents_list: list[str], api_client_factory):
    """Database provider fixture that creates the app and all databases."""
    provider = SqliteProvider()
    provider.setup(
        agent_names=test_agents_list,
        db_url=api_client_factory.db_url,
        engine=api_client_factory.engine,
    )
    yield provider
    provider.teardown()


@pytest.fixture(scope="session")
def secondary_db_provider(test_agents_list: list[str], secondary_api_client_factory):
    """A second, isolated database provider for multi-user tests."""
    provider = SqliteProvider()
    provider.setup(
        agent_names=test_agents_list,
        db_url=secondary_api_client_factory.db_url,
        engine=secondary_api_client_factory.engine,
    )
    yield provider
    provider.teardown()


@pytest.fixture(scope="session")
def database_manager(db_provider: SqliteProvider):
    """Creates a new unified DatabaseManager."""
    return DatabaseManager(db_provider)


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
    "db_provider",
    "secondary_db_provider",
    "database_manager",
    "gateway_adapter",
    "database_inspector",
    "secondary_database_manager",
    "secondary_gateway_adapter",
    "secondary_database_inspector",
]
