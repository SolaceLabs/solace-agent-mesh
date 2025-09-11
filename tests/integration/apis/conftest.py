"""
Pytest fixtures for high-level FastAPI functional testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa

# FastAPI and database imports
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# Remove old persistence service import - using direct SQLAlchemy now
from solace_agent_mesh.gateway.http_sse.repository.models.base import Base

# Import FastAPI components
from solace_agent_mesh.gateway.http_sse.main import app as fastapi_app
from solace_agent_mesh.gateway.http_sse.main import setup_dependencies

from .infrastructure.simple_database_inspector import SimpleDatabaseInspector

# Import test infrastructure components
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
        pool_timeout=30,
        max_overflow=0,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print(f"[API Tests] Test database created at {test_database_url}")

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
def mock_component():
    """Creates a mock WebUIBackendComponent for testing"""
    component = Mock()

    # Mock basic component methods
    component.get_app.return_value = Mock(
        app_config={
            "frontend_use_authorization": False,
            "external_auth_service_url": "http://localhost:8080",
            "external_auth_callback_uri": "http://localhost:8000/api/v1/auth/callback",
            "external_auth_provider": "azure",
            "frontend_redirect_url": "http://localhost:3000",
        }
    )
    component.get_cors_origins.return_value = ["*"]

    # Mock session manager with proper methods
    import uuid

    mock_session_manager = Mock(secret_key="test-secret-key")
    mock_session_manager.get_a2a_client_id.return_value = "test-client-id"
    mock_session_manager.start_new_a2a_session.side_effect = (
        lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
    )
    mock_session_manager.ensure_a2a_session.side_effect = (
        lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
    )
    component.get_session_manager.return_value = mock_session_manager

    component.identity_service = None

    # Mock A2A methods with task tracking for validation
    submitted_tasks = {
        "test-task-id"
    }  # Pre-populate with default task ID for existing tests

    async def mock_submit_task(*args, **kwargs):
        task_id = "test-task-id"  # Keep original behavior for existing tests
        submitted_tasks.add(task_id)
        return task_id

    async def mock_cancel_task(task_id, *args, **kwargs):
        if task_id not in submitted_tasks:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

    component.submit_a2a_task = AsyncMock(side_effect=mock_submit_task)
    component.cancel_a2a_task = AsyncMock(side_effect=mock_cancel_task)
    component._translate_external_input = AsyncMock(
        return_value=(
            "TestAgent",  # target_agent
            [],  # a2a_parts
            {},  # external_request_context
        )
    )

    # Mock authentication method - use same user ID as default auth middleware
    component.authenticate_and_enrich_user = AsyncMock(
        return_value={
            "id": "sam_dev_user",
            "name": "Sam Dev User",
            "email": "sam@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }
    )

    print("[API Tests] Mock component created")
    yield component


@pytest.fixture(scope="session")
def test_app(test_database_url_for_setup, mock_component):
    """Creates configured FastAPI test application"""
    # Set up dependencies and configure the app properly
    setup_dependencies(mock_component, test_database_url_for_setup)

    print("[API Tests] FastAPI app configured with test dependencies")
    yield fastapi_app


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
    """Clean the main API test database"""
    from sqlalchemy.orm import sessionmaker
    
    SessionLocal = sessionmaker(bind=test_database_engine)
    session = SessionLocal()
    try:
        # Check if tables exist before trying to delete from them
        inspector = sa.inspect(session.bind)
        existing_tables = inspector.get_table_names()

        # Delete in correct order to handle foreign key constraints
        if "chat_messages" in existing_tables:
            session.execute(text("DELETE FROM chat_messages"))
        if "sessions" in existing_tables:
            session.execute(text("DELETE FROM sessions"))
        if "users" in existing_tables:
            session.execute(text("DELETE FROM users"))
        session.commit()
    except Exception as e:
        # If cleanup fails, just rollback and continue
        session.rollback()
        print(
            f"[API Tests] Database cleanup failed (this may be normal for some tests): {e}"
        )
    finally:
        session.close()


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


def _clean_simple_databases(simple_manager):
    """Clean data from simple databases without destroying the schema"""
    import sqlite3

    # Clean gateway database
    if simple_manager.gateway_db_path and simple_manager.gateway_db_path.exists():
        with sqlite3.connect(simple_manager.gateway_db_path) as conn:
            cursor = conn.cursor()
            # Check which tables exist and clean them
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # Clean simple framework tables (different from main API tables)
            if "gateway_messages" in tables:
                conn.execute("DELETE FROM gateway_messages")
            if "gateway_sessions" in tables:
                conn.execute("DELETE FROM gateway_sessions")
            # Also clean main API tables if they exist (for mixed tests)
            if "chat_messages" in tables:
                conn.execute("DELETE FROM chat_messages")
            if "sessions" in tables:
                conn.execute("DELETE FROM sessions")
            if "users" in tables:
                conn.execute("DELETE FROM users")
            conn.commit()

    # Clean agent databases
    for agent_name, db_path in simple_manager.agent_db_paths.items():
        if db_path and db_path.exists():
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                # Clean simple framework agent tables
                if "agent_sessions" in tables:
                    conn.execute("DELETE FROM agent_sessions")
                if "agent_messages" in tables:
                    conn.execute("DELETE FROM agent_messages")
                # Also clean legacy table names if they exist
                if "sessions" in tables:
                    conn.execute("DELETE FROM sessions")
                if "messages" in tables:
                    conn.execute("DELETE FROM messages")
                conn.commit()


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
    "mock_component",
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
