"""
API integration tests for the /api/v1/tasks router.

These tests verify the functionality of the task history and retrieval endpoints.
"""

import uuid
from typing import Tuple

from fastapi.testclient import TestClient


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
