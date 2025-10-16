"""
API integration tests for the /api/v1/tasks router.

These tests verify the functionality of the task history and retrieval endpoints.
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
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


def test_create_and_get_basic_task(api_client: TestClient):
    """
    Tests creating a task and retrieving it from the /tasks list.
    Corresponds to Test Plan 1.2.
    """
    # Arrange
    message_text = "This is a basic test task."
    task_id, _ = _create_task_and_get_ids(api_client, message_text)

    # Manually log the task creation event to simulate the logger behavior,
    # as the API test harness does not have a live message broker.
    task_logger_service = dependencies.sac_component_instance.get_task_logger_service()
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


def test_task_logging_disabled(api_client: TestClient, test_db_engine, monkeypatch):
    """
    Tests that no tasks or events are logged when task_logging is disabled.
    Corresponds to Test Plan 3.1.
    """
    # Arrange: Disable task logging via monkeypatching the service's config
    task_logger_service = dependencies.sac_component_instance.get_task_logger_service()
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
    Session = sessionmaker(bind=test_db_engine)
    db_session = Session()
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
    task_logger_service = dependencies.sac_component_instance.get_task_logger_service()
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
    test_db_engine,
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
    task_logger_service = dependencies.sac_component_instance.get_task_logger_service()
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
