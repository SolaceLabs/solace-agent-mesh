"""
Integration tests for TaskRepository.find_active_children() method.

Tests the SQL NULL handling and recursive child finding against real databases.
These replace the unit tests in tests/unit/gateway/http_sse/repository/test_task_repository.py
which mocked the entire SQLAlchemy query chain.

All tests run against both SQLite and PostgreSQL via pytest parametrization.
"""

import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestFindActiveChildren:
    """Integration tests for finding active child tasks."""

    def test_finds_child_with_null_status(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that children with NULL status (newly created) are found."""
        # Create session
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        # Create parent and child tasks directly in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            parent_id = "parent-null-1"
            child_id = "child-null-1"
            now = now_epoch_ms()

            # Insert parent task
            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent task",
                    start_time=now,
                    status="running",
                )
            )

            # Insert child task with NULL status
            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child task",
                    parent_task_id=parent_id,
                    start_time=now,
                    status=None,  # NULL - newly created
                )
            )

            # Insert request event for child with agent_name metadata
            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{child_id}",
                    task_id=child_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {"metadata": {"agent_name": "ChildAgent"}}
                        }
                    },
                )
            )
            conn.commit()

        # Act: Find active children
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: Child with NULL status was found
        assert len(results) == 1
        assert results[0][0] == child_id
        assert results[0][1] == "ChildAgent"

    def test_finds_child_with_running_status(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that children with 'running' status are found."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            parent_id = "parent-run-1"
            child_id = "child-run-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{child_id}",
                    task_id=child_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {"metadata": {"workflow_name": "TestWorkflow"}}
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert
        assert len(results) == 1
        assert results[0][0] == child_id
        assert results[0][1] == "TestWorkflow"

    def test_finds_child_with_pending_status(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that children with 'pending' status are found."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            parent_id = "parent-pend-1"
            child_id = "child-pend-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status="pending",
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{child_id}",
                    task_id=child_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {"metadata": {"agent_name": "PendingAgent"}}
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert
        assert len(results) == 1
        assert results[0][0] == child_id
        assert results[0][1] == "PendingAgent"

    def test_does_not_find_completed_child(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that children with 'completed' status are NOT found."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]

            parent_id = "parent-comp-1"
            child_id = "child-comp-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status="completed",
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: Completed child NOT found
        assert len(results) == 0

    def test_does_not_find_failed_child(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that children with 'failed' status are NOT found."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]

            parent_id = "parent-fail-1"
            child_id = "child-fail-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status="failed",
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: Failed child NOT found
        assert len(results) == 0

    def test_finds_nested_children_recursively(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that nested children (grandchildren) are found recursively."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        # Create parent -> child -> grandchild hierarchy
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            parent_id = "parent-nest-1"
            child_id = "child-nest-1"
            grandchild_id = "grandchild-nest-1"
            now = now_epoch_ms()

            # Parent
            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            # Child with NULL status
            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status=None,
                )
            )

            # Grandchild with running status
            conn.execute(
                sa.insert(tasks_table).values(
                    id=grandchild_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Grandchild",
                    parent_task_id=child_id,
                    start_time=now,
                    status="running",
                )
            )

            # Events for metadata
            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{child_id}",
                    task_id=child_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {"metadata": {"agent_name": "ChildAgent"}}
                        }
                    },
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{grandchild_id}",
                    task_id=grandchild_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {"metadata": {"agent_name": "GrandchildAgent"}}
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: Both child and grandchild found
        assert len(results) == 2
        task_ids = [r[0] for r in results]
        agent_names = [r[1] for r in results]
        assert child_id in task_ids
        assert grandchild_id in task_ids
        assert "ChildAgent" in agent_names
        assert "GrandchildAgent" in agent_names

    def test_returns_empty_when_no_children(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that empty list is returned when no children exist."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        # Create task with no children
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]

            parent_id = "parent-solo-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Lonely parent",
                    start_time=now,
                    status="running",
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: No children found
        assert results == []

    def test_extracts_workflow_name_over_agent_name(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that workflow_name is preferred over agent_name in metadata."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            parent_id = "parent-wf-1"
            child_id = "child-wf-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status=None,
                )
            )

            # Event has BOTH workflow_name and agent_name
            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{child_id}",
                    task_id=child_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {
                                "metadata": {
                                    "workflow_name": "CompleteOrderWorkflow",
                                    "agent_name": "OrchestratorAgent",
                                }
                            }
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: workflow_name is returned, not agent_name
        assert len(results) == 1
        assert results[0][1] == "CompleteOrderWorkflow"

    def test_handles_missing_event_gracefully(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that tasks without events are handled gracefully."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]

            parent_id = "parent-no-evt-1"
            child_id = "child-no-evt-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=parent_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Parent",
                    start_time=now,
                    status="running",
                )
            )

            # Child task WITHOUT any events
            conn.execute(
                sa.insert(tasks_table).values(
                    id=child_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="Child",
                    parent_task_id=parent_id,
                    start_time=now,
                    status=None,
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            repo = TaskRepository()
            results = repo.find_active_children(db_session, parent_id)

        # Assert: Child is found but with None as agent name
        assert len(results) == 1
        assert results[0][0] == child_id
        assert results[0][1] is None
