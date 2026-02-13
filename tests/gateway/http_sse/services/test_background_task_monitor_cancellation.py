"""
Unit tests for background task monitor cancellation functionality.
Tests the fix for properly cancelling timed-out background tasks.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor import BackgroundTaskMonitor
from src.solace_agent_mesh.gateway.http_sse.repository.entities.task import Task


@pytest.fixture
def mock_session_factory():
    """Create a mock database session factory."""
    mock_session = Mock()
    mock_session.query = Mock()
    mock_session.commit = Mock()
    mock_session.rollback = Mock()
    mock_session.close = Mock()
    
    def factory():
        return mock_session
    
    return factory, mock_session


@pytest.fixture
def mock_task_service():
    """Create a mock task service."""
    service = Mock()
    service.cancel_task = AsyncMock()
    return service


@pytest.fixture
def background_task_monitor(mock_session_factory, mock_task_service):
    """Create a BackgroundTaskMonitor instance with mocked dependencies."""
    factory, _ = mock_session_factory
    return BackgroundTaskMonitor(
        session_factory=factory,
        task_service=mock_task_service,
        default_timeout_ms=3600000  # 1 hour
    )


def create_test_task(
    task_id: str,
    agent_name: str | None,
    last_activity_time: int,
    background_execution_enabled: bool = True,
    max_execution_time_ms: int | None = None
) -> Task:
    """Helper to create a test task."""
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    return Task(
        id=task_id,
        user_id="test_user",
        agent_name=agent_name,
        start_time=current_time - 7200000,  # 2 hours ago
        status="running",
        last_activity_time=last_activity_time,
        background_execution_enabled=background_execution_enabled,
        max_execution_time_ms=max_execution_time_ms,
        execution_mode="background" if background_execution_enabled else "foreground"
    )


@pytest.mark.asyncio
async def test_cancel_timed_out_task_with_agent_name(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test that timed-out tasks WITH agent_name are properly cancelled."""
    _, mock_session = mock_session_factory
    
    # Create a timed-out task with agent_name
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    timed_out_time = current_time - 7200000  # 2 hours ago (past 1 hour timeout)
    
    timed_out_task = create_test_task(
        task_id="task-123",
        agent_name="TestAgent",
        last_activity_time=timed_out_time,
        max_execution_time_ms=3600000  # 1 hour timeout
    )
    
    # Mock the repository to return the timed-out task
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = [timed_out_task]
        mock_repo.save_task.return_value = timed_out_task
        
        # Run the timeout check
        stats = await background_task_monitor.check_timeouts()
        
        # Verify task was marked as timeout
        assert stats["timed_out"] == 1
        assert stats["cancelled"] == 1
        
        # Verify save_task was called to update status
        assert mock_repo.save_task.called
        saved_task = mock_repo.save_task.call_args[0][1]
        assert saved_task.status == "timeout"
        assert saved_task.end_time is not None
        
        # Verify cancel_task was called on the task service
        mock_task_service.cancel_task.assert_called_once_with(
            agent_name="TestAgent",
            task_id="task-123",
            client_id="background_task_monitor",
            user_id="test_user"
        )


@pytest.mark.asyncio
async def test_cancel_timed_out_task_without_agent_name(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test that timed-out tasks WITHOUT agent_name are marked as timeout but cancellation is skipped."""
    _, mock_session = mock_session_factory
    
    # Create a timed-out task WITHOUT agent_name
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    timed_out_time = current_time - 7200000  # 2 hours ago
    
    timed_out_task = create_test_task(
        task_id="task-456",
        agent_name=None,  # No agent name
        last_activity_time=timed_out_time,
        max_execution_time_ms=3600000
    )
    
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = [timed_out_task]
        mock_repo.save_task.return_value = timed_out_task
        
        # Run the timeout check
        stats = await background_task_monitor.check_timeouts()
        
        # Verify task was marked as timeout
        assert stats["timed_out"] == 1
        assert stats["cancelled"] == 1
        
        # Verify save_task was called
        assert mock_repo.save_task.called
        
        # Verify cancel_task was NOT called (no agent name)
        mock_task_service.cancel_task.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_timed_out_tasks(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test handling multiple timed-out tasks."""
    _, mock_session = mock_session_factory
    
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    timed_out_time = current_time - 7200000
    
    # Create multiple timed-out tasks
    tasks = [
        create_test_task(f"task-{i}", f"Agent{i}", timed_out_time, max_execution_time_ms=3600000)
        for i in range(5)
    ]
    
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = tasks
        mock_repo.save_task.return_value = tasks[0]
        
        # Run the timeout check
        stats = await background_task_monitor.check_timeouts()
        
        # Verify all tasks were processed
        assert stats["timed_out"] == 5
        assert stats["cancelled"] == 5
        
        # Verify cancel_task was called for each task
        assert mock_task_service.cancel_task.call_count == 5


@pytest.mark.asyncio
async def test_task_within_timeout_not_cancelled(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test that tasks within timeout period are not cancelled."""
    _, mock_session = mock_session_factory
    
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    recent_activity = current_time - 1800000  # 30 minutes ago (within 1 hour timeout)
    
    active_task = create_test_task(
        task_id="task-789",
        agent_name="TestAgent",
        last_activity_time=recent_activity,
        max_execution_time_ms=3600000
    )
    
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = [active_task]
        
        # Run the timeout check
        stats = await background_task_monitor.check_timeouts()
        
        # Verify no tasks were timed out
        assert stats["timed_out"] == 0
        assert stats["cancelled"] == 0
        
        # Verify cancel_task was NOT called
        mock_task_service.cancel_task.assert_not_called()


@pytest.mark.asyncio
async def test_cancellation_failure_handled_gracefully(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test that cancellation failures are handled gracefully."""
    _, mock_session = mock_session_factory
    
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    timed_out_time = current_time - 7200000
    
    timed_out_task = create_test_task(
        task_id="task-fail",
        agent_name="TestAgent",
        last_activity_time=timed_out_time,
        max_execution_time_ms=3600000
    )
    
    # Make cancel_task raise an exception
    mock_task_service.cancel_task.side_effect = Exception("Agent not reachable")
    
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = [timed_out_task]
        mock_repo.save_task.return_value = timed_out_task
        
        # Run the timeout check - should not raise exception
        stats = await background_task_monitor.check_timeouts()
        
        # Task should still be marked as timed out even if cancellation fails
        assert stats["timed_out"] == 1
        assert stats["cancelled"] == 1
        
        # Verify save_task was still called
        assert mock_repo.save_task.called


@pytest.mark.asyncio
async def test_custom_timeout_per_task(
    background_task_monitor,
    mock_session_factory,
    mock_task_service
):
    """Test that tasks with custom timeouts are handled correctly."""
    _, mock_session = mock_session_factory
    
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # Task with 30-minute custom timeout, last activity 45 minutes ago
    timed_out_task = create_test_task(
        task_id="task-custom",
        agent_name="TestAgent",
        last_activity_time=current_time - 2700000,  # 45 minutes ago
        max_execution_time_ms=1800000  # 30 minute timeout
    )
    
    with patch('src.solace_agent_mesh.gateway.http_sse.services.background_task_monitor.TaskRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.find_background_tasks_by_status.return_value = [timed_out_task]
        mock_repo.save_task.return_value = timed_out_task
        
        # Run the timeout check
        stats = await background_task_monitor.check_timeouts()
        
        # Verify task was timed out based on custom timeout
        assert stats["timed_out"] == 1
        assert stats["cancelled"] == 1
        
        # Verify cancellation was sent
        mock_task_service.cancel_task.assert_called_once()
