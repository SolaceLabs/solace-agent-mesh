"""
Session lifecycle tests using FastAPI HTTP endpoints.

Tests session management through actual HTTP API calls to /sessions endpoints.
"""

from fastapi.testclient import TestClient

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter


def test_get_all_sessions_empty(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that GET /sessions returns empty list initially"""
    user_id = "sam_dev_user"
    sessions = database_inspector.get_gateway_sessions(user_id)
    for session in sessions:
        gateway_adapter.delete_session(session.id)

    response = api_client.get("/api/v1/sessions")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("data", []) == []


def test_send_task_creates_session_with_message(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test that creating a session and sending a message works"""
    user_id = "sam_dev_user"
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")
    task_response = gateway_adapter.send_message(
        session.id, "Hello, I need help with a task"
    )

    sessions = database_inspector.get_gateway_sessions(user_id)
    assert len(sessions) == 1
    assert sessions[0].id == session.id

    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) >= 1
    assert "Hello, I need help with a task" in task_response.user_message


def test_multiple_sessions_via_tasks(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test that a user can create multiple sessions with different agents"""
    user_id = "sam_dev_user"
    session1 = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")
    session2 = gateway_adapter.create_session(
        user_id=user_id, agent_name="TestPeerAgentA"
    )

    assert session1.id != session2.id

    sessions = database_inspector.get_gateway_sessions(user_id)
    assert len(sessions) == 2
    session_ids = {s.id for s in sessions}
    assert session1.id in session_ids
    assert session2.id in session_ids


def test_get_specific_session(gateway_adapter: GatewayAdapter, api_client: TestClient):
    """Test GET /sessions/{session_id} retrieves specific session"""
    user_id = "sam_dev_user"
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")

    session_response = api_client.get(f"/api/v1/sessions/{session.id}")
    assert session_response.status_code == 200

    session_data = session_response.json()
    assert session_data.get("data", {}).get("id") == session.id
    assert session_data.get("data", {}).get("agentId") == "TestAgent"


def test_get_session_history(gateway_adapter: GatewayAdapter, api_client: TestClient):
    """Test GET /sessions/{session_id}/messages retrieves message history"""
    user_id = "sam_dev_user"
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")
    gateway_adapter.send_message(session.id, "Test message for history")

    history_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
    assert history_response.status_code == 200

    history = history_response.json()
    assert isinstance(history, list)
    assert len(history) == 2

    user_message = history[0].get("message")
    assert "Test message for history" in user_message


def test_update_session_name(gateway_adapter: GatewayAdapter, api_client: TestClient):
    """Test PATCH /sessions/{session_id} updates session name"""
    user_id = "sam_dev_user"
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")

    update_data = {"name": "Updated Session Name"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session.id}", json=update_data
    )
    assert update_response.status_code == 200

    updated_session = update_response.json()
    assert updated_session["name"] == "Updated Session Name"
    assert updated_session["id"] == session.id


def test_delete_session(
    gateway_adapter: GatewayAdapter,
    api_client: TestClient,
    database_inspector: DatabaseInspector,
):
    """Test DELETE /sessions/{session_id} removes session"""
    user_id = "sam_dev_user"
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")

    # Verify session exists
    sessions = database_inspector.get_gateway_sessions(user_id)
    assert len(sessions) == 1

    # Delete the session
    delete_response = api_client.delete(f"/api/v1/sessions/{session.id}")
    assert delete_response.status_code == 204

    # Verify session no longer exists
    sessions = database_inspector.get_gateway_sessions(user_id)
    assert len(sessions) == 0


def test_session_error_handling(api_client: TestClient):
    """Test error handling for invalid session operations"""
    # Test getting non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session_id")
    assert response.status_code == 404

    # Test getting history for non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session_id/messages")
    assert response.status_code == 404

    # Test updating non-existent session
    update_data = {"name": "New Name"}
    response = api_client.patch(
        "/api/v1/sessions/nonexistent_session_id", json=update_data
    )
    assert response.status_code == 404

    # Test deleting non-existent session
    response = api_client.delete("/api/v1/sessions/nonexistent_session_id")
    assert response.status_code == 404


def test_end_to_end_session_workflow(
    gateway_adapter: GatewayAdapter,
    api_client: TestClient,
    database_inspector: DatabaseInspector,
):
    """Test complete session workflow: create -> send messages -> update -> delete"""
    user_id = "sam_dev_user"
    # 1. Create session
    session = gateway_adapter.create_session(user_id=user_id, agent_name="TestAgent")

    # 2. Verify session appears in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()
    assert len(sessions_data.get("data", [])) >= 1
    assert session.id in [s["id"] for s in sessions_data.get("data", [])]

    # 3. Send additional message to same session
    gateway_adapter.send_message(session.id, "Follow up message")

    # 4. Check session history
    history_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 1

    # 5. Update session name
    update_data = {"name": "My Test Conversation"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session.id}", json=update_data
    )
    assert update_response.status_code == 200
    update_result = update_response.json()
    assert update_result["name"] == "My Test Conversation"

    # 6. Delete session
    delete_response = api_client.delete(f"/api/v1/sessions/{session.id}")
    assert delete_response.status_code == 204

    # 7. Verify session is gone
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    assert session.id not in [s["id"] for s in sessions_response.json().get("data", [])]
