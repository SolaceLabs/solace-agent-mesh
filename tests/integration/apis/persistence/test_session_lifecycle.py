"""
Session lifecycle tests using FastAPI HTTP endpoints.

Tests session management through actual HTTP API calls to /sessions endpoints.
"""

from fastapi.testclient import TestClient


def test_get_all_sessions_empty(api_client: TestClient):
    """Test that GET /sessions returns empty list initially"""

    response = api_client.get("/api/v1/sessions")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["sessions"] == []
    assert response_data["total_count"] == 0

    print("✓ GET /sessions returns empty list when no sessions exist")


def test_send_task_creates_session_with_message(api_client: TestClient):
    """Test that POST /tasks/subscribe creates session and persists message"""

    # Send a streaming task which creates a session
    task_data = {"agent_name": "TestAgent", "message": "Hello, I need help with a task"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)

    # Verify task was submitted successfully
    assert response.status_code == 200
    response_data = response.json()
    assert "result" in response_data
    assert "taskId" in response_data["result"]
    assert "sessionId" in response_data["result"]

    session_id = response_data["result"]["sessionId"]
    task_id = response_data["result"]["taskId"]

    assert session_id is not None
    assert task_id == "test-task-id"  # From our mock

    print(f"✓ Task submitted and session {session_id} created")


def test_multiple_sessions_via_tasks(api_client: TestClient):
    """Test that a user can create multiple sessions with different agents"""

    # Create first session with TestAgent
    task_data_1 = {"agent_name": "TestAgent", "message": "Message to TestAgent"}
    response_1 = api_client.post("/api/v1/tasks/subscribe", data=task_data_1)
    assert response_1.status_code == 200
    session_id_1 = response_1.json()["result"]["sessionId"]

    # Create second session with TestPeerAgentA
    task_data_2 = {"agent_name": "TestPeerAgentA", "message": "Message to PeerAgentA"}
    response_2 = api_client.post("/api/v1/tasks/subscribe", data=task_data_2)
    assert response_2.status_code == 200
    session_id_2 = response_2.json()["result"]["sessionId"]

    # Verify sessions are different
    assert session_id_1 != session_id_2

    # Verify both sessions show up in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    sessions = sessions_data["sessions"]
    assert len(sessions) == 2
    assert sessions_data["total_count"] == 2

    # Verify session IDs and agents
    session_ids = {s["id"] for s in sessions}
    assert session_id_1 in session_ids
    assert session_id_2 in session_ids

    session_agents = {s["id"]: s["agent_id"] for s in sessions}
    assert session_agents[session_id_1] == "TestAgent"
    assert session_agents[session_id_2] == "TestPeerAgentA"

    print("✓ Multiple sessions created successfully via API")


def test_get_specific_session(api_client: TestClient):
    """Test GET /sessions/{session_id} retrieves specific session"""

    # First create a session
    task_data = {"agent_name": "TestAgent", "message": "Help with project X"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Get the specific session
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200

    session_data = session_response.json()
    assert session_data["id"] == session_id
    assert session_data["agent_id"] == "TestAgent"
    assert "user_id" in session_data

    print(f"✓ Retrieved specific session {session_id} via API")


def test_get_session_history(api_client: TestClient):
    """Test GET /sessions/{session_id}/messages retrieves message history"""

    # Create session with message
    task_data = {"agent_name": "TestAgent", "message": "Test message for history"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Get session history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200

    history = history_response.json()
    assert isinstance(history, list)  # Direct array format
    assert len(history) >= 1  # At least the user message should be stored

    # Verify the message content
    user_message = history[0]
    assert user_message["message"] == "Test message for history"
    assert user_message["sender_type"] == "user"

    print(f"✓ Retrieved session history for {session_id}")


def test_update_session_name(api_client: TestClient):
    """Test PATCH /sessions/{session_id} updates session name"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Original message"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Update session name
    update_data = {"name": "Updated Session Name"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json=update_data
    )
    assert update_response.status_code == 200

    updated_session = update_response.json()
    assert updated_session["name"] == "Updated Session Name"
    assert updated_session["id"] == session_id

    print(f"✓ Session {session_id} name updated successfully")


def test_delete_session(api_client: TestClient):
    """Test DELETE /sessions/{session_id} removes session"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Session to be deleted"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Verify session exists
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200

    # Delete the session
    delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 204  # No Content

    # Verify session no longer exists
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 404

    print(f"✓ Session {session_id} deleted successfully")


def test_session_error_handling(api_client: TestClient):
    """Test error handling for invalid session operations"""

    # Test getting non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session_id")
    assert response.status_code == 404

    # Test getting history for non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session_id/messages")
    assert response.status_code == 404  # Not found (don't reveal existence)

    # Test updating non-existent session
    update_data = {"name": "New Name"}
    response = api_client.patch(
        "/api/v1/sessions/nonexistent_session_id", json=update_data
    )
    assert response.status_code == 404  # Not found (don't reveal existence)

    # Test deleting non-existent session
    response = api_client.delete("/api/v1/sessions/nonexistent_session_id")
    assert response.status_code == 404  # Not found (don't reveal existence)

    print("✓ Session error handling works correctly")


def test_end_to_end_session_workflow(api_client: TestClient):
    """Test complete session workflow: create -> send messages -> update -> delete"""

    # 1. Create session via task submission
    task_data = {"agent_name": "TestAgent", "message": "Start new conversation"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # 2. Verify session appears in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    sessions = sessions_data["sessions"]
    assert len(sessions) == 1
    assert sessions_data["total_count"] == 1
    assert sessions[0]["id"] == session_id

    # 3. Send additional message to same session
    task_data_2 = {
        "agent_name": "TestAgent",
        "message": "Follow up message",
        "session_id": session_id,
    }
    response_2 = api_client.post("/api/v1/tasks/subscribe", data=task_data_2)
    assert response_2.status_code == 200
    assert response_2.json()["result"]["sessionId"] == session_id

    # 4. Check session history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 2  # Should have both messages (direct array)

    # 5. Update session name
    update_data = {"name": "My Test Conversation"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json=update_data
    )
    assert update_response.status_code == 200
    update_result = update_response.json()
    assert update_result["name"] == "My Test Conversation"

    # 6. Delete session
    delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 204

    # 7. Verify session is gone
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    assert len(sessions_data["sessions"]) == 0
    assert sessions_data["total_count"] == 0

    print("✓ Complete end-to-end session workflow successful")
