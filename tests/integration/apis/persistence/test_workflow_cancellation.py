"""Integration tests for workflow cancellation.

These tests verify that the workflow cancellation feature works correctly,
specifically testing the SQL NULL handling fix that was causing child tasks
with NULL status to not be found.

The bug: SQL's IN clause doesn't match NULL values, so tasks with status=NULL
(newly created tasks) were not being found when looking for active children.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models.base import Base
from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel, TaskEventModel
from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def repository():
    """Create a TaskRepository instance."""
    return TaskRepository()


class TestWorkflowCancellationChildTaskLookup:
    """Tests for finding child tasks during workflow cancellation.
    
    These tests use a real SQLite database to verify the SQL NULL handling fix.
    Before the fix, tasks with status=NULL were not being found.
    """
    
    def test_finds_child_task_with_null_status_in_real_database(
        self, db_session, repository
    ):
        """Test that child tasks with NULL status are found in a real database.
        
        This is the key regression test for the SQL NULL handling fix.
        Before the fix, this test would have FAILED because SQL's IN clause
        doesn't match NULL values.
        """
        current_time = now_epoch_ms()
        
        # Create parent task (e.g., gdk-task from gateway)
        parent_task = TaskModel(
            id="gdk-task-parent-123",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status=None,  # NULL status - newly created
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        # Create child task (e.g., a2a_subtask from orchestrator)
        # This task has NULL status because it was just created
        child_task = TaskModel(
            id="a2a_subtask-child-456",
            user_id="test-user",
            parent_task_id="gdk-task-parent-123",  # Links to parent
            start_time=current_time,
            status=None,  # NULL status - this is the key case!
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        
        # Create request event for child task with agent metadata
        child_event = TaskEventModel(
            id="event-child-1",
            task_id="a2a_subtask-child-456",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "workflow_name": "CompleteOrderWorkflow"
                        }
                    }
                }
            },
        )
        db_session.add(child_event)
        db_session.commit()
        
        # Now try to find active children - this is what the cancel endpoint does
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-123"
        )
        
        # BEFORE THE FIX: This would return [] because NULL doesn't match IN clause
        # AFTER THE FIX: This should return the child task
        assert len(active_children) == 1, (
            "Child task with NULL status should be found. "
            "If this fails, the SQL NULL handling fix is broken."
        )
        assert active_children[0][0] == "a2a_subtask-child-456"
        assert active_children[0][1] == "CompleteOrderWorkflow"
    
    def test_finds_child_task_with_running_status(self, db_session, repository):
        """Test that child tasks with 'running' status are found."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-parent-running",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        child_task = TaskModel(
            id="a2a_subtask-child-running",
            user_id="test-user",
            parent_task_id="gdk-task-parent-running",
            start_time=current_time,
            status="running",  # Running status
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        
        child_event = TaskEventModel(
            id="event-child-running",
            task_id="a2a_subtask-child-running",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "agent_name": "TestAgent"
                        }
                    }
                }
            },
        )
        db_session.add(child_event)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-running"
        )
        
        assert len(active_children) == 1
        assert active_children[0][0] == "a2a_subtask-child-running"
        assert active_children[0][1] == "TestAgent"
    
    def test_finds_child_task_with_pending_status(self, db_session, repository):
        """Test that child tasks with 'pending' status are found."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-parent-pending",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        child_task = TaskModel(
            id="a2a_subtask-child-pending",
            user_id="test-user",
            parent_task_id="gdk-task-parent-pending",
            start_time=current_time,
            status="pending",  # Pending status
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        
        child_event = TaskEventModel(
            id="event-child-pending",
            task_id="a2a_subtask-child-pending",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "agent_name": "PendingAgent"
                        }
                    }
                }
            },
        )
        db_session.add(child_event)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-pending"
        )
        
        assert len(active_children) == 1
        assert active_children[0][0] == "a2a_subtask-child-pending"
    
    def test_does_not_find_completed_child_task(self, db_session, repository):
        """Test that completed child tasks are NOT found."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-parent-completed",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        child_task = TaskModel(
            id="a2a_subtask-child-completed",
            user_id="test-user",
            parent_task_id="gdk-task-parent-completed",
            start_time=current_time,
            status="completed",  # Completed - should NOT be found
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-completed"
        )
        
        assert len(active_children) == 0, "Completed tasks should not be found"
    
    def test_does_not_find_failed_child_task(self, db_session, repository):
        """Test that failed child tasks are NOT found."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-parent-failed",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        child_task = TaskModel(
            id="a2a_subtask-child-failed",
            user_id="test-user",
            parent_task_id="gdk-task-parent-failed",
            start_time=current_time,
            status="failed",  # Failed - should NOT be found
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-failed"
        )
        
        assert len(active_children) == 0, "Failed tasks should not be found"
    
    def test_finds_nested_children_recursively(self, db_session, repository):
        """Test that nested children (grandchildren) are found recursively.
        
        This tests the full task hierarchy:
        gdk-task (gateway) -> a2a_subtask (orchestrator) -> wf_a2a_subtask (workflow)
        """
        current_time = now_epoch_ms()
        
        # Create parent task (gateway)
        parent_task = TaskModel(
            id="gdk-task-grandparent",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status=None,
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        # Create child task (orchestrator)
        child_task = TaskModel(
            id="a2a_subtask-child",
            user_id="test-user",
            parent_task_id="gdk-task-grandparent",
            start_time=current_time,
            status=None,  # NULL status
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        
        # Create grandchild task (workflow)
        grandchild_task = TaskModel(
            id="wf_a2a_subtask-grandchild",
            user_id="test-user",
            parent_task_id="a2a_subtask-child",
            start_time=current_time,
            status="running",
            initial_request_text="Grandchild task",
        )
        db_session.add(grandchild_task)
        
        # Create events for child and grandchild
        child_event = TaskEventModel(
            id="event-child-nested",
            task_id="a2a_subtask-child",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "agent_name": "OrchestratorAgent"
                        }
                    }
                }
            },
        )
        db_session.add(child_event)
        
        grandchild_event = TaskEventModel(
            id="event-grandchild-nested",
            task_id="wf_a2a_subtask-grandchild",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "workflow_name": "CompleteOrderWorkflow"
                        }
                    }
                }
            },
        )
        db_session.add(grandchild_event)
        db_session.commit()
        
        # Find all active children from the root
        active_children = repository.find_active_children(
            db_session, "gdk-task-grandparent"
        )
        
        # Should find both child and grandchild
        assert len(active_children) == 2, (
            "Should find both child and grandchild tasks"
        )
        
        task_ids = [child[0] for child in active_children]
        assert "a2a_subtask-child" in task_ids
        assert "wf_a2a_subtask-grandchild" in task_ids
    
    def test_finds_multiple_children_with_mixed_statuses(
        self, db_session, repository
    ):
        """Test finding multiple children with different active statuses."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-parent-mixed",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        # Child 1: NULL status
        child1 = TaskModel(
            id="child-null-status",
            user_id="test-user",
            parent_task_id="gdk-task-parent-mixed",
            start_time=current_time,
            status=None,
            initial_request_text="Child 1",
        )
        db_session.add(child1)
        
        # Child 2: running status
        child2 = TaskModel(
            id="child-running-status",
            user_id="test-user",
            parent_task_id="gdk-task-parent-mixed",
            start_time=current_time,
            status="running",
            initial_request_text="Child 2",
        )
        db_session.add(child2)
        
        # Child 3: pending status
        child3 = TaskModel(
            id="child-pending-status",
            user_id="test-user",
            parent_task_id="gdk-task-parent-mixed",
            start_time=current_time,
            status="pending",
            initial_request_text="Child 3",
        )
        db_session.add(child3)
        
        # Child 4: completed status (should NOT be found)
        child4 = TaskModel(
            id="child-completed-status",
            user_id="test-user",
            parent_task_id="gdk-task-parent-mixed",
            start_time=current_time,
            status="completed",
            initial_request_text="Child 4",
        )
        db_session.add(child4)
        
        # Add events for active children
        for i, task_id in enumerate(["child-null-status", "child-running-status", "child-pending-status"]):
            event = TaskEventModel(
                id=f"event-mixed-{i}",
                task_id=task_id,
                user_id="test-user",
                created_time=current_time,
                topic="test/topic",
                direction="request",
                payload={
                    "params": {
                        "message": {
                            "metadata": {
                                "agent_name": f"Agent{i}"
                            }
                        }
                    }
                },
            )
            db_session.add(event)
        
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-parent-mixed"
        )
        
        # Should find 3 active children (NULL, running, pending)
        # Should NOT find the completed child
        assert len(active_children) == 3, (
            "Should find 3 active children (NULL, running, pending), "
            "but not the completed one"
        )
        
        task_ids = [child[0] for child in active_children]
        assert "child-null-status" in task_ids, "NULL status child should be found"
        assert "child-running-status" in task_ids, "Running status child should be found"
        assert "child-pending-status" in task_ids, "Pending status child should be found"
        assert "child-completed-status" not in task_ids, "Completed child should NOT be found"
    
    def test_returns_empty_when_no_children(self, db_session, repository):
        """Test that empty list is returned when no children exist."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-no-children",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-no-children"
        )
        
        assert active_children == []
    
    def test_extracts_workflow_name_over_agent_name(self, db_session, repository):
        """Test that workflow_name is preferred over agent_name in metadata."""
        current_time = now_epoch_ms()
        
        parent_task = TaskModel(
            id="gdk-task-workflow-pref",
            user_id="test-user",
            parent_task_id=None,
            start_time=current_time,
            status="running",
            initial_request_text="Test request",
        )
        db_session.add(parent_task)
        
        child_task = TaskModel(
            id="child-workflow-pref",
            user_id="test-user",
            parent_task_id="gdk-task-workflow-pref",
            start_time=current_time,
            status=None,
            initial_request_text="Child task",
        )
        db_session.add(child_task)
        
        # Event has both workflow_name and agent_name
        child_event = TaskEventModel(
            id="event-workflow-pref",
            task_id="child-workflow-pref",
            user_id="test-user",
            created_time=current_time,
            topic="test/topic",
            direction="request",
            payload={
                "params": {
                    "message": {
                        "metadata": {
                            "workflow_name": "CompleteOrderWorkflow",
                            "agent_name": "OrchestratorAgent"
                        }
                    }
                }
            },
        )
        db_session.add(child_event)
        db_session.commit()
        
        active_children = repository.find_active_children(
            db_session, "gdk-task-workflow-pref"
        )
        
        assert len(active_children) == 1
        # workflow_name should be returned, not agent_name
        assert active_children[0][1] == "CompleteOrderWorkflow"
