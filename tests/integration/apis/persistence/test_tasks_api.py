"""
Tasks API tests using FastAPI HTTP endpoints.

Tests task submission and management through actual HTTP API calls to /tasks endpoints.
"""

import io

import pytest
from fastapi.testclient import TestClient


def test_send_non_streaming_task(api_client: TestClient):
    """Test POST /tasks/send for non-streaming task submission"""

    task_data = {
        "agent_name": "TestAgent",
        "message": "Hello, please process this task",
    }

    response = api_client.post("/api/v1/tasks/send", data=task_data)

    assert response.status_code == 200
    response_data = response.json()

    # Verify JSONRPC response format
    assert "result" in response_data
    assert "taskId" in response_data["result"]
    assert response_data["result"]["taskId"] == "test-task-id"

    print("✓ Non-streaming task submitted successfully")


def test_send_streaming_task(api_client: TestClient):
    """Test POST /tasks/subscribe for streaming task submission"""

    task_data = {"agent_name": "TestAgent", "message": "Start streaming conversation"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)

    assert response.status_code == 200
    response_data = response.json()

    # Verify JSONRPC response format
    assert "result" in response_data
    assert "taskId" in response_data["result"]
    assert "sessionId" in response_data["result"]

    task_id = response_data["result"]["taskId"]
    session_id = response_data["result"]["sessionId"]

    assert task_id == "test-task-id"
    assert session_id is not None
    assert len(session_id) > 0

    print(f"✓ Streaming task submitted with session {session_id}")


def test_send_task_with_files(api_client: TestClient):
    """Test POST /tasks/subscribe with file uploads"""

    # Create test files
    test_file_1 = io.BytesIO(b"Test file content 1")
    test_file_2 = io.BytesIO(b"Test file content 2")

    files = [
        ("files", ("test1.txt", test_file_1, "text/plain")),
        ("files", ("test2.txt", test_file_2, "text/plain")),
    ]

    data = {"agent_name": "TestAgent", "message": "Process these files"}

    response = api_client.post("/api/v1/tasks/subscribe", data=data, files=files)

    assert response.status_code == 200
    response_data = response.json()

    assert "result" in response_data
    assert "taskId" in response_data["result"]
    assert "sessionId" in response_data["result"]

    print("✓ Task with file uploads submitted successfully")


def test_send_task_to_existing_session(api_client: TestClient):
    """Test sending task to existing session"""

    # First create a session
    initial_task_data = {"agent_name": "TestAgent", "message": "Initial message"}

    initial_response = api_client.post(
        "/api/v1/tasks/subscribe", data=initial_task_data
    )
    assert initial_response.status_code == 200
    session_id = initial_response.json()["result"]["sessionId"]

    # Send follow-up task to same session
    followup_task_data = {
        "agent_name": "TestAgent",
        "message": "Follow-up message",
        "session_id": session_id,
    }

    followup_response = api_client.post(
        "/api/v1/tasks/subscribe", data=followup_task_data
    )
    assert followup_response.status_code == 200

    # Should return same session ID
    assert followup_response.json()["result"]["sessionId"] == session_id

    print(f"✓ Follow-up task sent to existing session {session_id}")


def test_cancel_task(api_client: TestClient):
    """Test POST /tasks/cancel for task cancellation"""

    # First submit a task
    task_data = {"agent_name": "TestAgent", "message": "Long running task to cancel"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    task_id = response.json()["result"]["taskId"]

    # Cancel the task
    cancel_data = {"task_id": task_id}
    cancel_response = api_client.post("/api/v1/tasks/cancel", data=cancel_data)

    assert cancel_response.status_code == 200
    cancel_result = cancel_response.json()

    assert "result" in cancel_result
    assert "message" in cancel_result["result"]
    assert task_id in cancel_result["result"]["message"]

    print(f"✓ Task {task_id} cancelled successfully")


def test_task_with_different_agents(api_client: TestClient):
    """Test sending tasks to different agents"""

    agents_and_messages = [
        ("TestAgent", "Task for main agent"),
        ("TestPeerAgentA", "Task for peer agent A"),
        ("TestPeerAgentB", "Task for peer agent B"),
    ]

    task_ids = []
    session_ids = []

    for agent_name, message in agents_and_messages:
        task_data = {"agent_name": agent_name, "message": message}

        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200

        result = response.json()["result"]
        task_ids.append(result["taskId"])
        session_ids.append(result["sessionId"])

    # Verify all tasks got unique sessions
    assert len(set(session_ids)) == len(session_ids)

    # Verify all tasks got the same mocked task ID (this is expected with our mock)
    assert all(task_id == "test-task-id" for task_id in task_ids)

    print(f"✓ Tasks sent to {len(agents_and_messages)} different agents")


def test_task_error_handling(api_client: TestClient):
    """Test error handling for invalid task requests"""

    # Test missing agent_name
    response = api_client.post("/api/v1/tasks/send", data={"message": "Test"})
    assert response.status_code in [400, 422]  # Validation error

    # Test missing message
    response = api_client.post("/api/v1/tasks/send", data={"agent_name": "TestAgent"})
    assert response.status_code in [400, 422]  # Validation error

    # Test empty body for cancellation
    response = api_client.post("/api/v1/tasks/cancel", data={})
    assert response.status_code in [400, 422]  # Validation error

    print("✓ Task error handling works correctly")


def test_task_request_validation(api_client: TestClient):
    """Test request validation for task endpoints"""

    # Test empty agent name
    task_data = {"agent_name": "", "message": "Test message"}
    response = api_client.post("/api/v1/tasks/send", data=task_data)
    # Should either work with empty string or return validation error
    assert response.status_code in [200, 422]

    # Test very long message
    long_message = "x" * 10000
    task_data = {"agent_name": "TestAgent", "message": long_message}
    response = api_client.post("/api/v1/tasks/send", data=task_data)
    assert response.status_code == 200  # Should handle long messages

    print("✓ Task request validation working correctly")


def test_concurrent_task_submissions(api_client: TestClient):
    """Test multiple concurrent task submissions"""

    # Submit multiple tasks quickly
    responses = []
    for i in range(5):
        task_data = {"agent_name": "TestAgent", "message": f"Concurrent task {i}"}
        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        responses.append(response)

    # Verify all succeeded
    for i, response in enumerate(responses):
        assert response.status_code == 200
        result = response.json()["result"]
        assert "taskId" in result
        assert "sessionId" in result
        print(f"  ✓ Concurrent task {i} submitted: session {result['sessionId']}")

    # Verify we got unique sessions for each task
    session_ids = [r.json()["result"]["sessionId"] for r in responses]
    assert len(set(session_ids)) == len(session_ids)

    print("✓ Concurrent task submissions handled correctly")


@pytest.mark.parametrize(
    "agent_name", ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]
)
def test_tasks_for_individual_agents(api_client: TestClient, agent_name: str):
    """Test task submission for individual agents (parameterized)"""

    task_data = {"agent_name": agent_name, "message": f"Task for {agent_name}"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200

    result = response.json()["result"]
    assert "taskId" in result
    assert "sessionId" in result

    session_id = result["sessionId"]
    assert session_id is not None

    print(f"✓ Task submitted to {agent_name}: session {session_id}")


def test_task_and_session_integration(api_client: TestClient):
    """Test integration between tasks and sessions APIs"""

    # Submit a task (creates session)
    task_data = {"agent_name": "TestAgent", "message": "Integration test message"}

    task_response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert task_response.status_code == 200
    session_id = task_response.json()["result"]["sessionId"]

    # Verify session appears in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    assert len(sessions_data["sessions"]) >= 1
    session_ids = [s["id"] for s in sessions_data["sessions"]]
    assert session_id in session_ids

    # Verify session details
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["agent_id"] == "TestAgent"

    # Verify message appears in session history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    assert len(history) >= 1
    user_message = history[0]
    assert user_message["message"] == "Integration test message"
    assert user_message["sender_type"] == "user"

    print(f"✓ Task-session integration verified for session {session_id}")
