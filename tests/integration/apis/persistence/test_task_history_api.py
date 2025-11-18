"""
API integration tests for the /api/v1/tasks router.

These tests verify the functionality of the task history and retrieval endpoints.
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse import dependencies
from solace_agent_mesh.gateway.http_sse.repository.models import (
    TaskEventModel,
    TaskModel,
)


class TimeController:
    """A simple class to control the 'current' time in tests."""

    def __init__(self, start_time: datetime):
        self._current_time = start_time

    def now(self) -> int:
        """Returns the current time as epoch milliseconds."""
        return int(self._current_time.timestamp() * 1000)

    def set_time(self, new_time: datetime):
        """Sets the current time to a specific datetime."""
        self._current_time = new_time

    def advance(self, seconds: int = 0, minutes: int = 0, hours: int = 0):
        """Advances the current time by a given amount."""
        self._current_time += timedelta(seconds=seconds, minutes=minutes, hours=hours)


@pytest.fixture
def mock_time(monkeypatch) -> TimeController:
    """
    Pytest fixture that mocks the `now_epoch_ms` function used by services
    and provides a TimeController to manipulate the time during tests.
    """
    # Start time is set to a fixed point to make tests deterministic
    start_time = datetime(2025, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    time_controller = TimeController(start_time)

    # The target is the `now_epoch_ms` function inside the module where it's used.
    # This ensures that when TaskLoggerService calls it, it gets our mocked version.
    monkeypatch.setattr(
        "solace_agent_mesh.gateway.http_sse.services.task_logger_service.now_epoch_ms",
        time_controller.now,
    )

    yield time_controller


def _create_task_and_get_ids(
    api_client: TestClient, message: str, agent_name: str = "TestAgent"
) -> tuple[str, str]:
    """
    Submits a streaming task via the API and returns the resulting task_id and session_id.

    This helper abstracts the JSON-RPC payload construction for creating tasks in tests.
    """
    request_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    task_payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": message_id,
                "kind": "message",
                "parts": [{"kind": "text", "text": message}],
                "metadata": {"agent_name": agent_name},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    response_data = response.json()

    assert "result" in response_data
    assert "id" in response_data["result"]
    assert "contextId" in response_data["result"]

    task_id = response_data["result"]["id"]
    session_id = response_data["result"]["contextId"]
    return task_id, session_id


def test_get_tasks_empty_state(api_client: TestClient):
    """
    Tests that GET /tasks returns an empty list when no tasks exist.
    Corresponds to Test Plan 1.1.
    """
    # Act
    response = api_client.get("/api/v1/tasks")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_get_basic_task(api_client: TestClient, api_client_factory):
    """
    Tests creating a task and retrieving it from the /tasks list.
    Corresponds to Test Plan 1.2.
    """
    # Arrange
    message_text = "This is a basic test task."
    task_id, _ = _create_task_and_get_ids(api_client, message_text)

    # Manually log the task creation event to simulate the logger behavior,
    # as the API test harness does not have a live message broker.
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
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
    mock_event_data = {
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    }
    task_logger_service.log_event(mock_event_data)

    # Act
    response = api_client.get("/api/v1/tasks")

    # Assert
    assert response.status_code == 200
    tasks = response.json()

    assert len(tasks) == 1
    task = tasks[0]

    assert task["id"] == task_id
    assert task["user_id"] == "sam_dev_user"  # From default mock auth in conftest
    assert task["initial_request_text"] == message_text
    assert isinstance(task["start_time"], int)
    assert task["end_time"] is None
    assert task["status"] is None


def test_task_logging_disabled(api_client: TestClient, api_client_factory, db_session_factory, monkeypatch):
    """
    Tests that no tasks or events are logged when task_logging is disabled.
    Corresponds to Test Plan 3.1.
    """
    # Arrange: Disable task logging via monkeypatching the service's config
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
    monkeypatch.setitem(task_logger_service.config, "enabled", False)

    # Act: Create a task and attempt to log an event for it
    message_text = "This task should not be logged."
    task_id, _ = _create_task_and_get_ids(api_client, message_text)

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
    mock_event_data = {
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    }
    # This call should do nothing because logging is disabled
    task_logger_service.log_event(mock_event_data)

    # Assert: Verify that no records were created in the database
    db_session = db_session_factory()
    try:
        tasks = db_session.query(TaskModel).all()
        events = db_session.query(TaskEventModel).all()

        assert len(tasks) == 0, "No tasks should be created when logging is disabled."
        assert len(events) == 0, (
            "No task events should be created when logging is disabled."
        )
    finally:
        db_session.close()


def _create_file_part_event_data(
    task_id: str, file_content: bytes, filename: str = "test.txt"
) -> dict:
    """Helper to create a mock event with a file part."""
    encoded_content = base64.b64encode(file_content).decode("utf-8")
    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [
                    {"kind": "text", "text": "Here is a file."},
                    {
                        "kind": "file",
                        "file": {
                            "name": filename,
                            "bytes": encoded_content,
                            "mime_type": "text/plain",
                        },
                    },
                ],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    return {
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": payload,
        "user_properties": {"userId": "sam_dev_user"},
    }


def assert_file_part_stripped(payload: dict):
    """Assert that the file part has been removed."""
    parts = payload.get("params", {}).get("message", {}).get("parts", [])
    assert len(parts) == 1, "Expected only one part after stripping file part."
    assert parts[0]["kind"] == "text", "The remaining part should be the text part."


def assert_file_content_truncated(payload: dict, max_bytes: int):
    """Assert that the file content has been truncated."""
    parts = payload.get("params", {}).get("message", {}).get("parts", [])
    assert len(parts) == 2, "Expected two parts."
    file_part = parts[1]
    assert file_part["kind"] == "file"
    file_content = file_part.get("file", {}).get("bytes", "")
    assert file_content == f"[Content stripped, size > {max_bytes} bytes]"


def test_get_task_events_basic(api_client: TestClient, api_client_factory):
    """
    Test GET /tasks/{task_id}/events returns task events in correct format.
    """
    # Create a task
    message_text = "Test task for events endpoint"
    task_id, _ = _create_task_and_get_ids(api_client, message_text)

    # Log a request event
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
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
    mock_event_data = {
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    }
    task_logger_service.log_event(mock_event_data)

    # Act: Get task events via API
    response = api_client.get(f"/api/v1/tasks/{task_id}/events")

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert "tasks" in data
    assert task_id in data["tasks"]

    task_data = data["tasks"][task_id]
    assert "events" in task_data
    assert "initial_request_text" in task_data
    assert task_data["initial_request_text"] == message_text

    events = task_data["events"]
    assert len(events) >= 1

    # Verify event structure matches A2AEventSSEPayload format
    first_event = events[0]
    assert "event_type" in first_event
    assert "timestamp" in first_event
    assert "direction" in first_event
    assert "task_id" in first_event
    assert first_event["task_id"] == task_id
    assert "full_payload" in first_event


def test_get_task_events_with_parent_child(api_client: TestClient, api_client_factory, db_session_factory):
    """
    Test GET /tasks/{task_id}/events returns parent and child tasks.
    """
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()

    # Create parent task
    parent_message = "Parent task"
    parent_task_id, _ = _create_task_and_get_ids(api_client, parent_message)

    parent_request_payload = {
        "jsonrpc": "2.0",
        "id": parent_task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": parent_message}],
                "metadata": {"agent_name": "OrchestratorAgent"},
            }
        },
    }
    task_logger_service.log_event({
        "topic": "test_namespace/a2a/v1/agent/request/OrchestratorAgent",
        "payload": parent_request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    })

    # Create child task with parentTaskId
    child_task_id = f"child-task-{uuid.uuid4().hex}"
    child_message = "Child task"
    child_request_payload = {
        "jsonrpc": "2.0",
        "id": child_task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": child_message}],
                "metadata": {
                    "agent_name": "SubAgent",
                    "parentTaskId": parent_task_id,  # Link to parent
                },
            }
        },
    }
    task_logger_service.log_event({
        "topic": "test_namespace/a2a/v1/agent/request/SubAgent",
        "payload": child_request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    })

    # Verify database has parent_task_id set
    db_session = db_session_factory()
    try:
        child_task_model = db_session.query(TaskModel).filter(TaskModel.id == child_task_id).first()
        assert child_task_model is not None
        assert child_task_model.parent_task_id == parent_task_id
    finally:
        db_session.close()

    # Act: Get parent task events via API
    response = api_client.get(f"/api/v1/tasks/{parent_task_id}/events")

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert "tasks" in data
    # Should include both parent and child tasks
    assert parent_task_id in data["tasks"]
    assert child_task_id in data["tasks"]

    # Verify parent task data
    parent_data = data["tasks"][parent_task_id]
    assert parent_data["initial_request_text"] == parent_message
    assert len(parent_data["events"]) >= 1

    # Verify child task data
    child_data = data["tasks"][child_task_id]
    assert child_data["initial_request_text"] == child_message
    assert len(child_data["events"]) >= 1


def test_get_task_events_permission_denied(api_client: TestClient, secondary_api_client: TestClient, api_client_factory):
    """
    Test GET /tasks/{task_id}/events returns 403 for tasks owned by other users.
    """
    # Create a task as sam_dev_user
    task_id, _ = _create_task_and_get_ids(api_client, "Test task")

    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
    request_payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_logger_service.log_event({
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    })

    # Act: Try to get task events as different user (secondary_user)
    response = secondary_api_client.get(f"/api/v1/tasks/{task_id}/events")

    # Assert: Should be forbidden
    assert response.status_code == 403


def test_get_task_events_not_found(api_client: TestClient):
    """
    Test GET /tasks/{task_id}/events returns 404 for non-existent task.
    """
    response = api_client.get("/api/v1/tasks/non-existent-task-id/events")
    assert response.status_code == 404


def test_get_task_as_stim_file_with_child_tasks(api_client: TestClient, api_client_factory, db_session_factory):
    """
    Test GET /tasks/{task_id} (stim file download) includes child task events.
    """
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()

    # Create parent task
    parent_message = "Parent task for stim test"
    parent_task_id, _ = _create_task_and_get_ids(api_client, parent_message)

    parent_request_payload = {
        "jsonrpc": "2.0",
        "id": parent_task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": parent_message}],
                "metadata": {"agent_name": "ParentAgent"},
            }
        },
    }
    task_logger_service.log_event({
        "topic": "test_namespace/a2a/v1/agent/request/ParentAgent",
        "payload": parent_request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    })

    # Create child task
    child_task_id = f"child-stim-{uuid.uuid4().hex}"
    child_message = "Child task for stim test"
    child_request_payload = {
        "jsonrpc": "2.0",
        "id": child_task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": child_message}],
                "metadata": {
                    "agent_name": "ChildAgent",
                    "parentTaskId": parent_task_id,
                },
            }
        },
    }
    task_logger_service.log_event({
        "topic": "test_namespace/a2a/v1/agent/request/ChildAgent",
        "payload": child_request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    })

    # Act: Download stim file
    response = api_client.get(f"/api/v1/tasks/{parent_task_id}")

    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/yaml"
    assert "attachment" in response.headers["content-disposition"]

    # Parse YAML content
    stim_data = yaml.safe_load(response.text)

    # Verify structure
    assert "invocation_details" in stim_data
    assert "invocation_flow" in stim_data

    # Verify invocation details
    details = stim_data["invocation_details"]
    assert details["task_id"] == parent_task_id
    assert details["user_id"] == "sam_dev_user"
    assert details["initial_request_text"] == parent_message
    assert details["includes_child_tasks"] is True
    assert details["total_tasks"] == 2

    # Verify invocation flow includes events from both tasks
    flow = stim_data["invocation_flow"]
    assert len(flow) == 2  # One event from parent, one from child

    # Verify both task IDs appear in the flow
    task_ids_in_flow = {event["task_id"] for event in flow}
    assert parent_task_id in task_ids_in_flow
    assert child_task_id in task_ids_in_flow


@pytest.mark.parametrize(
    "config_to_set, file_content, assertion_func",
    [
        (
            {"log_file_parts": False},
            b"some file content",
            assert_file_part_stripped,
        ),
        (
            {"max_file_part_size_bytes": 50},
            b"This is some file content that is definitely longer than fifty bytes.",
            lambda p: assert_file_content_truncated(p, 50),
        ),
    ],
    ids=["log_file_parts_false", "max_file_part_size_exceeded"],
)
def test_file_content_logging_config(
    api_client: TestClient,
    api_client_factory,
    monkeypatch,
    config_to_set: dict,
    file_content: bytes,
    assertion_func: callable,
):
    """
    Tests that file content logging is correctly handled based on config.
    Corresponds to Test Plan 3.3.
    """
    # Arrange: Set the configuration on the task logger service
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
    for key, value in config_to_set.items():
        monkeypatch.setitem(task_logger_service.config, key, value)

    # Create a task to get a valid ID
    task_id, _ = _create_task_and_get_ids(api_client, "Task for file logging test")

    # Act: Log an event with a file part
    event_data = _create_file_part_event_data(task_id, file_content)
    task_logger_service.log_event(event_data)

    # Assert: Check the database to see how the payload was stored
    Session = task_logger_service.session_factory
    db_session = Session()
    try:
        event_model = (
            db_session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .one()
        )
        stored_payload = event_model.payload
        assertion_func(stored_payload)
    finally:
        db_session.close()


def _create_status_update_event_data(task_id: str) -> dict:
    """Helper to create a mock status update event."""
    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "result": {
            "kind": "status-update",
            "taskId": task_id,
            "contextId": "some_session",
            "final": False,
            "status": {
                "state": "working",
                "message": {
                    "role": "agent",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "working..."}],
                },
            },
        },
    }
    return {
        "topic": f"test_namespace/a2a/v1/gateway/status/TestWebUIGateway_01/{task_id}",
        "payload": payload,
        "user_properties": {"userId": "sam_dev_user"},
    }


def _create_artifact_update_event_data(task_id: str) -> dict:
    """Helper to create a mock artifact update event."""
    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "result": {
            "kind": "artifact-update",
            "taskId": task_id,
            "contextId": "some_session",
            "artifact": {
                "id": "art-123",
                "name": "test.txt",
                "kind": "artifact",
                "parts": [{"kind": "text", "text": "artifact content"}],
            },
        },
    }
    return {
        "topic": f"test_namespace/a2a/v1/gateway/status/TestWebUIGateway_01/{task_id}",
        "payload": payload,
        "user_properties": {"userId": "sam_dev_user"},
    }


@pytest.mark.parametrize(
    "config_to_disable, create_skipped_event_func, skipped_event_kind",
    [
        (
            {"log_status_updates": False},
            _create_status_update_event_data,
            "status-update",
        ),
        (
            {"log_artifact_events": False},
            _create_artifact_update_event_data,
            "artifact-update",
        ),
    ],
    ids=["log_status_updates_false", "log_artifact_events_false"],
)
def test_event_type_logging_flags(
    api_client: TestClient,
    api_client_factory,
    db_session_factory,
    monkeypatch,
    config_to_disable: dict,
    create_skipped_event_func: callable,
    skipped_event_kind: str,
):
    """
    Tests that specific event types are not logged when their flags are false.
    Corresponds to Test Plan 3.2.
    """
    # Arrange: Disable specific event logging
    task_logger_service = api_client_factory.mock_component.get_task_logger_service()
    for key, value in config_to_disable.items():
        monkeypatch.setitem(task_logger_service.config, key, value)

    # Create a task to get a valid ID
    task_id, _ = _create_task_and_get_ids(api_client, "Task for event flag test")

    # Log a request event (should always be logged)
    request_payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "hello"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    request_event_data = {
        "topic": "test_namespace/a2a/v1/agent/request/TestAgent",
        "payload": request_payload,
        "user_properties": {"userId": "sam_dev_user"},
    }
    task_logger_service.log_event(request_event_data)

    # Log the event that should be skipped
    skipped_event_data = create_skipped_event_func(task_id)
    task_logger_service.log_event(skipped_event_data)

    # Log a final response event (should always be logged)
    final_response_payload = {
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
                    "parts": [{"kind": "text", "text": "Done."}],
                },
            },
        },
    }
    final_response_event_data = {
        "topic": f"test_namespace/a2a/v1/gateway/response/TestWebUIGateway_01/{task_id}",
        "payload": final_response_payload,
        "user_properties": {"userId": "sam_dev_user"},
    }
    task_logger_service.log_event(final_response_event_data)

    # Assert: Check the database
    # Use the service's own session factory to ensure we are in the same
    # transactional context.
    Session = task_logger_service.session_factory
    db_session = Session()
    try:
        events = (
            db_session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .all()
        )
        # Should have 2 events: the request and the final response.
        # The status/artifact update should be skipped.
        assert len(events) == 2, f"Expected 2 events, but found {len(events)}"

        # Verify that the skipped event kind is not in the logged events
        for event in events:
            payload = event.payload
            if "result" in payload and isinstance(payload["result"], dict):
                assert payload["result"].get("kind") != skipped_event_kind
    finally:
        db_session.close()
