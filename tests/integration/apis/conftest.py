"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa

from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    create_test_app,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .infrastructure.database_manager import DatabaseManager, SqliteProvider
from .infrastructure.gateway_adapter import GatewayAdapter
from .infrastructure.database_inspector import DatabaseInspector


@pytest.fixture(scope="session")
def api_client(db_provider):
    """Creates a TestClient that uses the same app instance as the db_provider."""
    client = TestClient(db_provider.app)
    print("[API Tests] FastAPI TestClient created from db_provider")
    yield client


@pytest.fixture
def authenticated_user():
    """Returns test user data for authenticated requests"""
    return {
        "id": "sam_dev_user",
        "name": "Sam Dev User",
        "email": "sam@dev.local",
        "authenticated": True,
        "auth_method": "development",
    }


@pytest.fixture(autouse=True)
def clean_database_between_tests(database_manager: DatabaseManager):
    """Cleans database state between tests"""
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    yield
    _clean_main_database(database_manager.provider.get_sync_gateway_engine())
    print("[API Tests] Database cleaned between tests")


def _clean_main_database(engine):
    """Clean the main API test database using SQLAlchemy Core"""

    # Define table names in dependency order for safe deletion
    table_names = [
        "feedback",
        "task_events",
        "tasks",
        "chat_messages",
        "sessions",
        "users",
    ]

    with engine.connect() as connection:
        try:
            # Reflect existing tables
            metadata = sa.MetaData()
            metadata.reflect(bind=connection)
            
            # Get existing tables from metadata
            existing_tables = metadata.tables

            # Turn off foreign keys for safe deletion
            if str(connection.engine.url).startswith("sqlite"):
                connection.execute(text("PRAGMA foreign_keys=OFF"))

            # Delete data from tables that exist
            for table_name in table_names:
                if table_name in existing_tables:
                    table = existing_tables[table_name]
                    connection.execute(sa.delete(table))
            
            # Commit the transaction
            if connection.in_transaction():
                connection.commit()

            # Turn foreign keys back on
            if str(connection.engine.url).startswith("sqlite"):
                connection.execute(text("PRAGMA foreign_keys=ON"))

        except Exception as e:
            if connection.in_transaction():
                connection.rollback()
            print(f"[API Tests] Database cleanup failed: {e}")




@pytest.fixture(scope="session")
def test_agents_list() -> list[str]:
    """List of test agent names for parameterized tests"""
    return ["TestAgent", "TestPeerAgentA", "TestPeerAgentB", "TestPeerAgentC"]


@pytest.fixture
def sample_messages() -> list[str]:
    """Sample messages for testing"""
    return [
        "Hello, I need help with project X",
        "Can you analyze this data for me?",
        "What's the weather like today?",
        "Help me understand this concept",
        "Generate a report for the team",
    ]


# Simple infrastructure fixtures for infrastructure tests
@pytest.fixture(scope="session")
def db_provider(test_agents_list: list[str]):
    """Database provider fixture that creates the app and all databases."""
    provider = SqliteProvider()
    provider.setup(agent_names=test_agents_list)
    yield provider
    provider.teardown()


@pytest.fixture(scope="session")
def database_manager(db_provider: SqliteProvider):
    """Creates a new unified DatabaseManager."""
    return DatabaseManager(db_provider)


@pytest.fixture(scope="session")
def gateway_adapter(database_manager):
    """Creates a new GatewayAdapter."""
    return GatewayAdapter(database_manager)


@pytest.fixture(scope="session")
def database_inspector(database_manager):
    """Creates a new DatabaseInspector."""
    return DatabaseInspector(database_manager)




# Export FastAPI testing fixtures
__all__ = [
    "api_client",
    "authenticated_user",
    "clean_database_between_tests",
    "test_agents_list",
    "sample_messages",
    "db_provider",
    "database_manager",
    "gateway_adapter",
    "database_inspector",
]
