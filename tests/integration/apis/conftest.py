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

from .infrastructure.simple_database_inspector import SimpleDatabaseInspector
from .infrastructure.simple_database_manager import SimpleDatabaseManager
from .infrastructure.simple_gateway_adapter import SimpleGatewayAdapter


@pytest.fixture(scope="session")
def test_database_url():
    """Creates a temporary SQLite database URL for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_api.db"
    return f"sqlite:///{db_path}"


@pytest.fixture(scope="session")
def test_database_engine(test_database_url):
    """Creates SQLAlchemy engine for test database"""
    engine = create_engine(
        test_database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=300,
    )

    # Enable foreign keys for SQLite (database-agnostic)
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        if test_database_url.startswith("sqlite"):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Tables will be created by Alembic migrations in setup_dependencies()
    print(f"[API Tests] Test database engine created at {test_database_url}")

    yield engine

    # Cleanup
    engine.dispose()
    print("[API Tests] Test database engine disposed")


@pytest.fixture(scope="session")
def test_database_url_for_setup(test_database_url):
    """Provides database URL for setup - replaces persistence service"""
    print("[API Tests] Test database URL prepared for setup")
    yield test_database_url


@pytest.fixture(scope="session")
def test_app(test_database_url_for_setup):
    """Creates configured FastAPI test application using the factory"""
    app = create_test_app(db_url=test_database_url_for_setup)
    print("[API Tests] FastAPI app configured with test dependencies via factory")
    yield app


@pytest.fixture(scope="session")
def api_client(test_app):
    """Creates FastAPI TestClient for making HTTP requests"""
    client = TestClient(test_app)
    print("[API Tests] FastAPI TestClient created")

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
def clean_database_between_tests(request, test_database_engine):
    """Cleans database state between tests"""

    # Clean BEFORE the test runs to ensure clean starting state
    _clean_main_database(test_database_engine)
    _clean_simple_databases_if_needed(request)

    yield  # Let the test run

    # Clean AFTER the test runs to clean up
    _clean_main_database(test_database_engine)
    _clean_simple_databases_if_needed(request)

    print("[API Tests] Database cleaned between tests")


def _clean_main_database(test_database_engine):
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

    with test_database_engine.connect() as connection:
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


def _clean_simple_databases_if_needed(request):
    """Clean simple databases if the test uses them"""
    if hasattr(request, "node"):
        # Check if this test uses simple database fixtures
        for fixture_name in request.fixturenames:
            if "simple_database_manager" in fixture_name:
                try:
                    # Get the simple database manager fixture
                    simple_manager = request.getfixturevalue("simple_database_manager")
                    _clean_simple_databases(simple_manager)
                    print("[API Tests] Simple databases cleaned")
                except Exception as e:
                    print(f"[API Tests] Simple database cleanup failed: {e}")
                break


def _clean_simple_databases(simple_manager: SimpleDatabaseManager):
    """Clean data from simple databases using SQLAlchemy Core"""

    # Tables to clean in the gateway database
    gateway_tables_to_clean = [
        "gateway_messages",
        "gateway_sessions",
        "chat_messages",
        "sessions",
        "users",
    ]

    # Clean gateway database
    try:
        with simple_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            existing_tables = metadata.tables

            for table_name in gateway_tables_to_clean:
                if table_name in existing_tables:
                    table = existing_tables[table_name]
                    conn.execute(sa.delete(table))
            
            if conn.in_transaction():
                conn.commit()
    except Exception as e:
        print(f"[API Tests] Simple gateway database cleanup failed: {e}")


    # Tables to clean in agent databases
    agent_tables_to_clean = ["agent_sessions", "agent_messages", "sessions", "messages"]

    # Clean agent databases
    for agent_name in simple_manager.agent_db_paths.keys():
        try:
            with simple_manager.get_agent_connection(agent_name) as conn:
                metadata = sa.MetaData()
                metadata.reflect(bind=conn)
                existing_tables = metadata.tables

                for table_name in agent_tables_to_clean:
                    if table_name in existing_tables:
                        table = existing_tables[table_name]
                        conn.execute(sa.delete(table))

                if conn.in_transaction():
                    conn.commit()
        except Exception as e:
            print(f"[API Tests] Simple agent '{agent_name}' db cleanup failed: {e}")


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
def simple_database_manager(test_agents_list):
    """Creates SimpleDatabaseManager for testing"""
    manager = SimpleDatabaseManager()
    manager.setup_test_databases(test_agents_list)
    print("[Simple Infrastructure] Database manager created")

    yield manager

    # Cleanup
    manager.cleanup_all_databases()
    print("[Simple Infrastructure] Database manager cleaned up")


@pytest.fixture(scope="session")
def simple_database_inspector(simple_database_manager):
    """Creates SimpleDatabaseInspector for testing"""
    inspector = SimpleDatabaseInspector(simple_database_manager)
    print("[Simple Infrastructure] Database inspector created")

    yield inspector


@pytest.fixture(scope="session")
def simple_gateway_adapter(simple_database_manager):
    """Creates SimpleGatewayAdapter for testing"""
    adapter = SimpleGatewayAdapter(simple_database_manager)
    print("[Simple Infrastructure] Gateway adapter created")

    yield adapter


# Export FastAPI testing fixtures
__all__ = [
    "test_database_url",
    "test_database_engine",
    "test_database_url_for_setup",
    "test_app",
    "api_client",
    "authenticated_user",
    "clean_database_between_tests",
    "test_agents_list",
    "sample_messages",
    # Simple infrastructure fixtures
    "simple_database_manager",
    "simple_database_inspector",
    "simple_gateway_adapter",
]
