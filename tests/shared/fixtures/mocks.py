"""Shared mock factories for tests."""
from unittest.mock import AsyncMock, MagicMock


def create_mock_artifact_service():
    """Create a standard mock artifact service."""
    service = AsyncMock()
    service.load_artifact = AsyncMock(return_value=None)
    service.save_artifact = AsyncMock(return_value=1)
    service.delete_artifact = AsyncMock(return_value=True)
    service.list_artifacts = AsyncMock(return_value=[])
    return service


def create_mock_sse_manager():
    """Create a mock SSE manager for testing."""
    manager = MagicMock()
    manager.send_event = AsyncMock()
    manager._connections = {}
    manager._background_task_cache = {}
    manager._tasks_with_prior_connection = set()
    return manager


def create_mock_component(gateway_id="test-gateway", namespace="test_namespace"):
    """Create a mock gateway component."""
    component = MagicMock()
    component.gateway_id = gateway_id
    component.namespace = namespace
    component.log_identifier = f"[{gateway_id}]"
    component.get_config = MagicMock(side_effect=lambda key, default=None: default)
    return component


def create_mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session

