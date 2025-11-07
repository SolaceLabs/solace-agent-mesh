"""
Database integrity tests for the task history feature.
"""

import uuid

from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse import dependencies
from solace_agent_mesh.gateway.http_sse.repository.models import (
    TaskEventModel,
    TaskModel,
)
from tests.integration.apis.persistence.test_task_history_api import (
    _create_task_and_get_ids,
)


def test_task_deletion_cascades_to_events(api_client: TestClient, api_client_factory, db_session_factory):
    """
    Tests that deleting a Task record correctly cascades the deletion to all
    associated TaskEvent records, verifying the `ondelete='CASCADE'` constraint.
    Corresponds to Test Plan 2.3.
    """
    # Arrange: Create a task via the API. The TaskLoggerService, running in the
    # background of the test harness, will automatically log events for it.
    task_id, _ = _create_task_and_get_ids(api_client, "Test message for cascade delete")

    # Manually log events to simulate the logger behavior, as the API test
    # harness does not have a live message broker.
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
    message_text = "Test message for cascade delete"

    # Log request event
    request_payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": message_text}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_logger_service.log_event(
        {
            "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
            "payload": request_payload,
            "user_properties": {"userId": "sam_dev_user"},
        }
    )

    # Log a final response event to complete the task record
    response_payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "result": {
            "id": task_id,
            "contextId": "some_session",
            "kind": "task",
            "status": {
                "state": "completed",
                "message": {
                    "role": "agent",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Done"}],
                },
            },
        },
    }
    task_logger_service.log_event(
        {
            "topic": f"test_namespace/a2a/v1/gateway/response/TestWebUIGateway_01/{task_id}",
            "payload": response_payload,
            "user_properties": {"userId": "sam_dev_user"},
        }
    )

    # Now, check the database directly. Use the service's own session factory
    # to ensure we are in the same transactional context.
    Session = task_logger_service.session_factory
    db_session = Session()
    try:
        events = (
            db_session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .all()
        )
        assert len(events) >= 2, (
            f"Task events were not logged correctly for task {task_id}."
        )
        print(f"Found {len(events)} events for task {task_id} before deletion.")

        task = db_session.query(TaskModel).filter(TaskModel.id == task_id).one()

        # Act: Delete the parent task directly from the database
        db_session.delete(task)
        db_session.commit()
        print(f"Deleted task {task_id} from the database.")

        # Assert: Verify the task and its events are gone
        task_after_delete = (
            db_session.query(TaskModel).filter(TaskModel.id == task_id).one_or_none()
        )
        assert task_after_delete is None, (
            "The task should have been deleted from the tasks table."
        )

        events_after_delete = (
            db_session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .all()
        )
        assert len(events_after_delete) == 0, (
            "Task events should have been deleted by the CASCADE constraint."
        )

        print(
            f"✓ Task deletion for {task_id} correctly cascaded to delete {len(events)} events."
        )

    finally:
        db_session.close()
