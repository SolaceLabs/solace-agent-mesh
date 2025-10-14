from unittest.mock import Mock, AsyncMock
import tempfile
from pathlib import Path
import uuid

from sqlalchemy import event, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from solace_agent_mesh.gateway.http_sse.main import app as fastapi_app, setup_dependencies
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from solace_agent_mesh.gateway.http_sse.services.data_retention_service import DataRetentionService
from solace_agent_mesh.gateway.http_sse.services.task_logger_service import TaskLoggerService
from solace_agent_mesh.core_a2a.service import CoreA2AService
from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager

def create_test_app(db_url: str = None):
    """
    Creates and configures a FastAPI application instance for testing the WebUI backend.

    This factory function encapsulates the logic for setting up a test-ready
    version of the main FastAPI application, including mock dependencies and
    a test database. It ensures all routers are correctly registered.
    """
    if db_url is None:
        # If no database URL is provided, create a temporary SQLite DB for isolation.
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / f"test_api_{uuid.uuid4().hex}.db"
        db_url = f"sqlite:///{db_path}"

    # Create a mock WebUIBackendComponent
    mock_component = Mock(spec=WebUIBackendComponent)
    mock_component.get_app.return_value = Mock(
        app_config={
            "frontend_use_authorization": False,
            "external_auth_service_url": "http://localhost:8080",
            "external_auth_callback_uri": "http://localhost:8000/api/v1/auth/callback",
            "external_auth_provider": "azure",
            "frontend_redirect_url": "http://localhost:3000",
        }
    )
    mock_component.get_cors_origins.return_value = ["*"]
    mock_session_manager = Mock(secret_key="test-secret-key")
    mock_session_manager.create_new_session_id.side_effect = (
        lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
    )
    mock_component.get_session_manager.return_value = mock_session_manager
    mock_component.get_session_manager.return_value = mock_session_manager
    mock_component.identity_service = None
    mock_component.gateway_id = "test-gateway"

    # Mock authentication method - use same user ID as default auth middleware
    mock_component.authenticate_and_enrich_user = AsyncMock(
        return_value={
            "id": "sam_dev_user",
            "name": "Sam Dev User",
            "email": "sam@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }
    )
    mock_component.task_context_manager = Mock()
    mock_component.component_config = {"app_config": {}}

    # Mock the config resolver to handle async user config resolution
    mock_config_resolver = Mock()
    mock_config_resolver.resolve_user_config = AsyncMock(return_value={})
    mock_component.get_config_resolver.return_value = mock_config_resolver

    # Mock the A2A task submission to return just the task ID string
    async def mock_submit_task(*args, **kwargs):
        return f"task-{uuid.uuid4().hex[:8]}"

    mock_component.submit_a2a_task = AsyncMock(side_effect=mock_submit_task)

    # Create a mock CoreA2AService instance for task cancellation tests
    mock_core_a2a_service = Mock(spec=CoreA2AService)
    def mock_cancel_task_service(agent_name, task_id, client_id, user_id):
        target_topic = f"test_namespace/a2a/v1/agent/cancel/{agent_name}"
        payload = {
            "jsonrpc": "2.0",
            "id": f"cancel-{task_id}",
            "method": "tasks/cancel",
            "params": {"id": task_id}
        }
        user_properties = {"userId": user_id}
        return target_topic, payload, user_properties
    mock_core_a2a_service.cancel_task = mock_cancel_task_service
    mock_component.get_core_a2a_service.return_value = mock_core_a2a_service

    # Create a mock SSEManager instance
    mock_sse_manager = Mock(spec=SSEManager)
    mock_component.get_sse_manager.return_value = mock_sse_manager

    # Create a test database engine and session factory
    engine = create_engine(
        db_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        if db_url.startswith('sqlite'):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Session = sessionmaker(bind=engine)

    # Create real instances of services required for persistence tests
    task_logger_config = {"enabled": True}
    real_task_logger_service = TaskLoggerService(
        session_factory=Session, config=task_logger_config
    )
    mock_component.get_task_logger_service.return_value = real_task_logger_service

    data_retention_config = {
        "enabled": True,
        "task_retention_days": 90,
        "feedback_retention_days": 90,
        "cleanup_interval_hours": 24,
        "batch_size": 1000,
    }
    real_data_retention_service = DataRetentionService(
        session_factory=Session, config=data_retention_config
    )
    mock_component.data_retention_service = real_data_retention_service
    
    # Add the database_url attribute that the tests expect
    mock_component.database_url = db_url

    # This function initializes the app, including middleware, dependencies,
    # exceptions, and calls _setup_routers() to mount all API endpoints.
    setup_dependencies(component=mock_component, database_url=db_url)

    # Return the fully configured application instance
    return fastapi_app
