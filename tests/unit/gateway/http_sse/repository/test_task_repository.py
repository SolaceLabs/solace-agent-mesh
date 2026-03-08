"""Unit tests for TaskRepository, specifically the find_active_children method.

These tests verify the SQL NULL handling for finding active child tasks
so tasks with status=NULL (newly created tasks) are found.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy.orm import Session as DBSession


class TestFindActiveChildren:
    """Tests for TaskRepository.find_active_children method.
    
    The query must use `or_(status.is_(None), status.in_([...]))` instead of
    just `status.in_([None, ...])`.
    """
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock(spec=DBSession)
    
    @pytest.fixture
    def repository(self):
        """Create a TaskRepository instance."""
        from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
        return TaskRepository()
    
    def test_finds_child_with_null_status(self, repository, mock_session):
        """Test that children with NULL status are found.
        
        """
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        # Create a mock child task with NULL status (newly created task)
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task-123"
        mock_child.parent_task_id = "parent-task-456"
        mock_child.status = None  # NULL status - this is the key case
        
        # Create a mock request event for the child task
        mock_event = Mock(spec=TaskEventModel)
        mock_event.task_id = "child-task-123"
        mock_event.direction = "request"
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "agent_name": "TestAgent"
                    }
                }
            }
        }
        
        # Track call count to handle recursion
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                # First call returns the child, subsequent calls return empty (no grandchildren)
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                mock_event_filter.first.return_value = mock_event
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        # Call the method
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        # Verify the child was found
        assert len(results) == 1
        assert results[0][0] == "child-task-123"
        assert results[0][1] == "TestAgent"
    
    def test_finds_child_with_running_status(self, repository, mock_session):
        """Test that children with 'running' status are found."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task-running"
        mock_child.parent_task_id = "parent-task-456"
        mock_child.status = "running"
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.task_id = "child-task-running"
        mock_event.direction = "request"
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "workflow_name": "TestWorkflow"
                    }
                }
            }
        }
        
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                mock_event_filter.first.return_value = mock_event
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert len(results) == 1
        assert results[0][0] == "child-task-running"
        assert results[0][1] == "TestWorkflow"
    
    def test_finds_child_with_pending_status(self, repository, mock_session):
        """Test that children with 'pending' status are found."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task-pending"
        mock_child.parent_task_id = "parent-task-456"
        mock_child.status = "pending"
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.task_id = "child-task-pending"
        mock_event.direction = "request"
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "agent_name": "PendingAgent"
                    }
                }
            }
        }
        
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                mock_event_filter.first.return_value = mock_event
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert len(results) == 1
        assert results[0][0] == "child-task-pending"
    
    def test_does_not_find_completed_child(self, repository, mock_session):
        """Test that children with 'completed' status are NOT found."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel
        
        # The query should filter out completed tasks, so return empty list
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = []  # No active children
        mock_session.query.return_value = mock_query
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert len(results) == 0
    
    def test_does_not_find_failed_child(self, repository, mock_session):
        """Test that children with 'failed' status are NOT found."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = []  # No active children
        mock_session.query.return_value = mock_query
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert len(results) == 0
    
    def test_finds_nested_children_recursively(self, repository, mock_session):
        """Test that nested children (grandchildren) are found recursively."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        # Create parent -> child -> grandchild hierarchy
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task"
        mock_child.parent_task_id = "parent-task"
        mock_child.status = None
        
        mock_grandchild = Mock(spec=TaskModel)
        mock_grandchild.id = "grandchild-task"
        mock_grandchild.parent_task_id = "child-task"
        mock_grandchild.status = "running"
        
        mock_event_child = Mock(spec=TaskEventModel)
        mock_event_child.payload = {
            "params": {"message": {"metadata": {"agent_name": "ChildAgent"}}}
        }
        
        mock_event_grandchild = Mock(spec=TaskEventModel)
        mock_event_grandchild.payload = {
            "params": {"message": {"metadata": {"agent_name": "GrandchildAgent"}}}
        }
        
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                # First call: return child for parent
                # Second call: return grandchild for child
                # Third call: return empty for grandchild
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                elif call_count[0] == 1:
                    mock_filter.all.return_value = [mock_grandchild]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                
                # Return appropriate event based on call order
                if call_count[0] <= 1:
                    mock_event_filter.first.return_value = mock_event_child
                else:
                    mock_event_filter.first.return_value = mock_event_grandchild
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        results = repository.find_active_children(mock_session, "parent-task")
        
        # Should find both child and grandchild
        assert len(results) == 2
        task_ids = [r[0] for r in results]
        assert "child-task" in task_ids
        assert "grandchild-task" in task_ids
    
    def test_returns_empty_when_no_children(self, repository, mock_session):
        """Test that empty list is returned when no children exist."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = []
        mock_session.query.return_value = mock_query
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert results == []
    
    def test_extracts_workflow_name_over_agent_name(self, repository, mock_session):
        """Test that workflow_name is preferred over agent_name in metadata."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task-123"
        mock_child.parent_task_id = "parent-task-456"
        mock_child.status = None
        
        # Event has both workflow_name and agent_name
        mock_event = Mock(spec=TaskEventModel)
        mock_event.task_id = "child-task-123"
        mock_event.direction = "request"
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "workflow_name": "CompleteOrderWorkflow",
                        "agent_name": "OrchestratorAgent"
                    }
                }
            }
        }
        
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                mock_event_filter.first.return_value = mock_event
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        assert len(results) == 1
        # workflow_name should be returned, not agent_name
        assert results[0][1] == "CompleteOrderWorkflow"
    
    def test_handles_missing_event_gracefully(self, repository, mock_session):
        """Test that missing events are handled gracefully."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
        
        mock_child = Mock(spec=TaskModel)
        mock_child.id = "child-task-123"
        mock_child.parent_task_id = "parent-task-456"
        mock_child.status = None
        
        call_count = [0]
        
        def query_side_effect(model):
            if model == TaskModel:
                mock_query = Mock()
                mock_filter = Mock()
                mock_query.filter.return_value = mock_filter
                mock_filter.filter.return_value = mock_filter
                
                if call_count[0] == 0:
                    mock_filter.all.return_value = [mock_child]
                else:
                    mock_filter.all.return_value = []
                call_count[0] += 1
                return mock_query
            elif model == TaskEventModel:
                mock_event_query = Mock()
                mock_event_filter = Mock()
                mock_event_query.filter.return_value = mock_event_filter
                mock_event_filter.order_by.return_value = mock_event_filter
                mock_event_filter.first.return_value = None  # No event found
                return mock_event_query
            return Mock()
        
        mock_session.query.side_effect = query_side_effect
        
        results = repository.find_active_children(mock_session, "parent-task-456")
        
        # Should still return the child, but with None as agent name
        assert len(results) == 1
        assert results[0][0] == "child-task-123"
        assert results[0][1] is None


class TestExtractTargetAgentFromEvents:
    """Tests for TaskRepository._extract_target_agent_from_events method."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock(spec=DBSession)
    
    @pytest.fixture
    def repository(self):
        """Create a TaskRepository instance."""
        from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
        return TaskRepository()
    
    def test_extracts_agent_name(self, repository, mock_session):
        """Test extracting agent_name from event metadata."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "agent_name": "TestAgent"
                    }
                }
            }
        }
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_filter
        mock_filter.first.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        result = repository._extract_target_agent_from_events(mock_session, "task-123")
        
        assert result == "TestAgent"
    
    def test_extracts_workflow_name(self, repository, mock_session):
        """Test extracting workflow_name from event metadata."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.payload = {
            "params": {
                "message": {
                    "metadata": {
                        "workflow_name": "TestWorkflow"
                    }
                }
            }
        }
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_filter
        mock_filter.first.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        result = repository._extract_target_agent_from_events(mock_session, "task-123")
        
        assert result == "TestWorkflow"
    
    def test_returns_none_when_no_event(self, repository, mock_session):
        """Test that None is returned when no event is found."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_session.query.return_value = mock_query
        
        result = repository._extract_target_agent_from_events(mock_session, "task-123")
        
        assert result is None
    
    def test_returns_none_when_no_payload(self, repository, mock_session):
        """Test that None is returned when event has no payload."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.payload = None
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_filter
        mock_filter.first.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        result = repository._extract_target_agent_from_events(mock_session, "task-123")
        
        assert result is None
    
    def test_returns_none_when_malformed_payload(self, repository, mock_session):
        """Test that None is returned when payload is malformed."""
        from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
        
        mock_event = Mock(spec=TaskEventModel)
        mock_event.payload = {"invalid": "structure"}
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_filter
        mock_filter.first.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        result = repository._extract_target_agent_from_events(mock_session, "task-123")
        
        assert result is None


class TestSQLNullHandlingFix:
    """Tests specifically demonstrating the SQL NULL handling fix.
    """
    
    def test_query_uses_is_none_for_null_status(self):
        """Test that the query uses IS NULL for NULL status values.
        
        """
        from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
        import inspect
        
        # Get the source code of find_active_children
        source = inspect.getsource(TaskRepository.find_active_children)
        
        # Verify the fix is in place
        assert "or_" in source, "Query should use or_() for combining conditions"
        assert "is_(None)" in source, "Query should use is_(None) for NULL status"
        assert "status.in_" in source, "Query should use in_() for other statuses"
    
    def test_old_broken_query_pattern_not_used(self):
        """Test that the old broken query pattern is not used.
        
        The old pattern `status.in_([None, ...])` doesn't work for NULL values.
        """
        from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
        import inspect
        
        source = inspect.getsource(TaskRepository.find_active_children)
        
        # We check that the pattern is correct by verifying or_ is used
        assert "or_(" in source, "Should use or_() to combine NULL check with IN clause"
