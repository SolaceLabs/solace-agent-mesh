"""
API integration tests for the /api/v1/tasks router.

These tests verify the functionality of the task history and retrieval endpoints.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse import dependencies


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
) -> Tuple[str, str]:
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
        "topic": f"test_namespace/a2a/v1/agent/request/TestAgent",
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
