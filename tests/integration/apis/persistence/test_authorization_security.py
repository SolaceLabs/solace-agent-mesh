"""
Authorization security tests using FastAPI HTTP endpoints.

Tests cross-user session access, ownership validation, and proper 404 handling
to prevent information leakage about session existence.
"""

from fastapi.testclient import TestClient

from ..infrastructure.gateway_adapter import GatewayAdapter


def test_cross_user_session_access_returns_404(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Test that accessing another user's session returns 404 (not 403) to prevent information leakage"""

    # User A creates a session (sam_dev_user)
    session_a = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    # Verify User A can access their own session
    session_response = api_client.get(f"/api/v1/sessions/{session_a.id}")
    assert session_response.status_code == 200

    # User B tries to access User A's session - should get 404, not 403
    unauthorized_response = secondary_api_client.get(f"/api/v1/sessions/{session_a.id}")
    assert unauthorized_response.status_code == 404


def test_cross_user_session_history_returns_404(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Test that accessing another user's session history returns 404"""

    # User A creates a session with messages (sam_dev_user)
    session_a = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(session_a.id, "private message")

    # Verify User A can access their own session history
    history_response = api_client.get(f"/api/v1/sessions/{session_a.id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 1

    # User B tries to access User A's session history - should get 404
    unauthorized_history = secondary_api_client.get(
        f"/api/v1/sessions/{session_a.id}/messages"
    )
    assert unauthorized_history.status_code == 404


def test_cross_user_session_update_returns_404(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Test that trying to update another user's session returns 404"""

    # User A creates a session (sam_dev_user)
    session_a = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    # Verify User A can update their own session
    update_data = {"name": "User A's Updated Session"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_a.id}", json=update_data
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "User A's Updated Session"

    # User B tries to update User A's session - should get 404
    malicious_update = {"name": "Hijacked Session"}
    unauthorized_update = secondary_api_client.patch(
        f"/api/v1/sessions/{session_a.id}", json=malicious_update
    )
    assert unauthorized_update.status_code == 404
    response_data = unauthorized_update.json()
    error_message = response_data.get("detail")
    assert "session not found." in error_message.lower()

    # Verify session name wasn't changed by unauthorized user
    verify_response = api_client.get(f"/api/v1/sessions/{session_a.id}")
    assert verify_response.status_code == 200
    assert verify_response.json()["data"]["name"] == "User A's Updated Session"


def test_cross_user_session_deletion_returns_404(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Test that trying to delete another user's session returns 404"""

    # User A creates a session (sam_dev_user)
    session_a = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    # Verify session exists for User A
    session_response = api_client.get(f"/api/v1/sessions/{session_a.id}")
    assert session_response.status_code == 200

    # User B tries to delete User A's session - should get 404
    unauthorized_delete = secondary_api_client.delete(
        f"/api/v1/sessions/{session_a.id}"
    )
    assert unauthorized_delete.status_code == 404
    response_data = unauthorized_delete.json()
    error_message = response_data.get("detail")
    assert "session not found." in error_message.lower()

    # Verify session still exists for User A
    verify_response = api_client.get(f"/api/v1/sessions/{session_a.id}")
    assert verify_response.status_code == 200
    assert verify_response.json()["data"]["id"] == session_a.id


def test_session_isolation_in_listing(
    api_client: TestClient, secondary_api_client: TestClient
):
    """Test that users only see their own sessions in the sessions list"""

    import uuid

    # User A creates multiple sessions
    user_a_sessions = []
    for i in range(3):
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": f"User A's session {i + 1}"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        assert response.status_code == 200
        user_a_sessions.append(response.json()["result"]["contextId"])

    # User B creates multiple sessions
    user_b_sessions = []
    for i in range(2):
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": f"User B's session {i + 1}"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = secondary_api_client.post(
            "/api/v1/message:stream", json=task_payload
        )
        assert response.status_code == 200
        user_b_sessions.append(response.json()["result"]["contextId"])

    # User A should only see their own sessions
    user_a_list = api_client.get("/api/v1/sessions")
    assert user_a_list.status_code == 200
    user_a_data = user_a_list.json()
    user_a_session_ids = {s["id"] for s in user_a_data["data"]}

    # User A should see all their sessions and none of User B's
    for session_id in user_a_sessions:
        assert session_id in user_a_session_ids
    for session_id in user_b_sessions:
        assert session_id not in user_a_session_ids

    # User B should only see their own sessions
    user_b_list = secondary_api_client.get("/api/v1/sessions")
    assert user_b_list.status_code == 200
    user_b_data = user_b_list.json()
    user_b_session_ids = {s["id"] for s in user_b_data["data"]}

    # User B should see all their sessions and none of User A's
    for session_id in user_b_sessions:
        assert session_id in user_b_session_ids
    for session_id in user_a_sessions:
        assert session_id not in user_b_session_ids


def test_consistent_404_for_nonexistent_and_unauthorized_sessions(
    api_client: TestClient,
    secondary_api_client: TestClient,
):
    """Test that nonexistent sessions and unauthorized sessions both return 404"""

    # User A creates a session
    import uuid

    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [
                    {"kind": "text", "text": "Real session for consistency test"}
                ],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    real_session_id = response_a.json()["result"]["contextId"]

    fake_session_id = "completely_fake_session_id"

    endpoints_to_test = [
        ("GET", f"/api/v1/sessions/{real_session_id}"),
        ("GET", f"/api/v1/sessions/{fake_session_id}"),
        ("GET", f"/api/v1/sessions/{real_session_id}/messages"),
        ("GET", f"/api/v1/sessions/{fake_session_id}/messages"),
    ]

    # User B should get 404 for both real (unauthorized) and fake (nonexistent) sessions
    for method, endpoint in endpoints_to_test:
        if method == "GET":
            response = secondary_api_client.get(endpoint)

        assert response.status_code == 404
        response_data = response.json()
        error_message = response_data.get("detail")
        assert "session not found." in error_message.lower()

    # Test PATCH endpoints
    update_data = {"name": "Test Update"}
    real_patch_response = secondary_api_client.patch(
        f"/api/v1/sessions/{real_session_id}", json=update_data
    )
    fake_patch_response = secondary_api_client.patch(
        f"/api/v1/sessions/{fake_session_id}", json=update_data
    )

    assert real_patch_response.status_code == 404
    assert fake_patch_response.status_code == 404

    # Test DELETE endpoints
    real_delete_response = secondary_api_client.delete(
        f"/api/v1/sessions/{real_session_id}"
    )
    fake_delete_response = secondary_api_client.delete(
        f"/api/v1/sessions/{fake_session_id}"
    )

    assert real_delete_response.status_code == 404
    assert fake_delete_response.status_code == 404


def test_authorization_with_empty_session_id(api_client):
    """Test authorization behavior with empty or invalid session IDs"""

    # Skip empty string since it routes to /sessions endpoint instead of /sessions/{id}
    # This is expected FastAPI behavior - empty path parameter routes to different endpoint
    invalid_session_ids = [" ", "null", "undefined", "0"]

    for invalid_id in invalid_session_ids:
        # Test GET session
        response = api_client.get(f"/api/v1/sessions/{invalid_id}")
        print(f"Testing invalid_id='{invalid_id}': status={response.status_code}")
        if response.status_code == 200:
            print(f"  Unexpected 200 response: {response.json()}")
        assert response.status_code == 404

        # Test GET history
        response = api_client.get(f"/api/v1/sessions/{invalid_id}/messages")
        assert response.status_code == 404

        # Test PATCH session
        update_data = {"name": "Invalid Update"}
        response = api_client.patch(f"/api/v1/sessions/{invalid_id}", json=update_data)
        assert response.status_code == 404

        # Test DELETE session
        response = api_client.delete(f"/api/v1/sessions/{invalid_id}")
        assert response.status_code == 404


def test_session_ownership_after_multiple_operations(
    api_client: TestClient, secondary_api_client: TestClient
):
    """Test that session ownership is consistently validated across multiple operations"""

    # User A creates a session and performs multiple operations
    import uuid

    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Multi-operation test session"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # User A performs legitimate operations
    # 1. Get session
    get_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200

    # 2. Update session name
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json={"name": "Updated Name"}
    )
    assert update_response.status_code == 200

    # 3. Get history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200

    # 4. Add another message to the session
    followup_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Follow-up message"}],
                "metadata": {"agent_name": "TestAgent"},
                "contextId": session_id,
            }
        },
    }
    followup_response = api_client.post("/api/v1/message:stream", json=followup_payload)
    assert followup_response.status_code == 200
    assert followup_response.json()["result"]["contextId"] == session_id

    # After all operations, User B should still get 404 for everything
    assert secondary_api_client.get(f"/api/v1/sessions/{session_id}").status_code == 404
    assert (
        secondary_api_client.get(f"/api/v1/sessions/{session_id}/messages").status_code
        == 404
    )
    assert (
        secondary_api_client.patch(
            f"/api/v1/sessions/{session_id}", json={"name": "Hijack"}
        ).status_code
        == 404
    )
    assert (
        secondary_api_client.delete(f"/api/v1/sessions/{session_id}").status_code == 404
    )

    # Verify User A still has full access
    final_get = api_client.get(f"/api/v1/sessions/{session_id}")
    assert final_get.status_code == 200
    assert final_get.json()["data"]["name"] == "Updated Name"
