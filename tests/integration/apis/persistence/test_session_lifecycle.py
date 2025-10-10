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
    assert response_data["totalCount"] == 0

    print("✓ GET /sessions returns empty list when no sessions exist")


def test_send_task_creates_session_with_message(api_client: TestClient):
    """Test that POST /message:stream creates session and persists message"""

    import uuid

    # Send a streaming task which creates a session
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Hello, I need help with a task"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)

    # Verify task was submitted successfully
    assert response.status_code == 200
    response_data = response.json()
    assert "result" in response_data
    assert "id" in response_data["result"]
    assert "contextId" in response_data["result"]

    session_id = response_data["result"]["contextId"]
    task_id = response_data["result"]["id"]

    assert session_id is not None
    assert task_id == "test-task-id"  # From our mock

    print(f"✓ Task submitted and session {session_id} created")


def test_multiple_sessions_via_tasks(api_client: TestClient):
    """Test that a user can create multiple sessions with different agents"""

    import uuid

    # Create first session with TestAgent
    task_payload_1 = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Message to TestAgent"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_1 = api_client.post("/api/v1/message:stream", json=task_payload_1)
    assert response_1.status_code == 200
    session_id_1 = response_1.json()["result"]["contextId"]

    # Create second session with TestPeerAgentA
    task_payload_2 = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Message to PeerAgentA"}],
                "metadata": {"agent_name": "TestPeerAgentA"},
            }
        },
    }
    response_2 = api_client.post("/api/v1/message:stream", json=task_payload_2)
    assert response_2.status_code == 200
    session_id_2 = response_2.json()["result"]["contextId"]

    # Verify sessions are different
    assert session_id_1 != session_id_2

    # Verify both sessions show up in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    sessions = sessions_data["data"]
    assert len(sessions) == 2

    # Verify session IDs and agents
    session_ids = {s["id"] for s in sessions}
    assert session_id_1 in session_ids
    assert session_id_2 in session_ids

    session_agents = {s["id"]: s["agentId"] for s in sessions}
    assert session_agents[session_id_1] == "TestAgent"
    assert session_agents[session_id_2] == "TestPeerAgentA"

    print("✓ Multiple sessions created successfully via API")


def test_get_specific_session(api_client: TestClient):
    """Test GET /sessions/{session_id} retrieves specific session"""

    import uuid

    # First create a session
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Help with project X"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    session_id = response.json()["result"]["contextId"]

    # Get the specific session
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200

    session_data = session_response.json()
    assert session_data["id"] == session_id
    assert session_data["agentId"] == "TestAgent"
    assert "userId" in session_data

    print(f"✓ Retrieved specific session {session_id} via API")


def test_get_session_history(api_client: TestClient):
    """Test GET /sessions/{session_id}/messages retrieves message history"""

    import uuid

    # Create session with message
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Test message for history"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    session_id = response.json()["result"]["contextId"]

    # Get session history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200

    history = history_response.json()
    assert isinstance(history, list)  # Direct array format
    assert len(history) >= 1  # At least the user message should be stored

    # Verify the message content
    user_message = history[0]
    assert user_message["message"] == "Test message for history"
    assert user_message["senderType"] == "user"

    print(f"✓ Retrieved session history for {session_id}")


def test_update_session_name(api_client: TestClient):
    """Test PATCH /sessions/{session_id} updates session name"""

    import uuid

    # Create a session
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Original message"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    session_id = response.json()["result"]["contextId"]

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

    import uuid

    # Create a session
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Session to be deleted"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    session_id = response.json()["result"]["contextId"]

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

    import uuid

    # 1. Create session via task submission
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Start new conversation"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    session_id = response.json()["result"]["contextId"]

    # 2. Verify session appears in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    sessions = sessions_data["sessions"]
    assert len(sessions) == 1
    assert sessions_data["totalCount"] == 1
    assert sessions[0]["id"] == session_id

    # 3. Send additional message to same session
    task_payload_2 = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Follow up message"}],
                "metadata": {"agent_name": "TestAgent"},
                "contextId": session_id,
            }
        },
    }
    response_2 = api_client.post("/api/v1/message:stream", json=task_payload_2)
    assert response_2.status_code == 200
    assert response_2.json()["result"]["contextId"] == session_id

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
    assert sessions_data["totalCount"] == 0

    print("✓ Complete end-to-end session workflow successful")
