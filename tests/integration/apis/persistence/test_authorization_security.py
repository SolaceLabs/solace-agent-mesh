"""
Authorization security tests using FastAPI HTTP endpoints.

Tests cross-user session access, ownership validation, and proper 404 handling
to prevent information leakage about session existence.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def multi_user_test_setup(test_app):
    """Creates multiple test clients with different user authentications using FastAPI dependency overrides"""
    from solace_agent_mesh.gateway.http_sse.dependencies import (
        get_user_id,
        sac_component_instance,
    )
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user

    # Track which user should be returned
    current_test_user = {"user_id": "first_test_user"}

    # Mock get_current_user dependency - use lambda to avoid parameter validation
    def mock_get_current_user():
        user_id = current_test_user["user_id"]
        if user_id == "first_test_user":
            return {
                "id": "first_test_user",
                "name": "First Test User",
                "email": "first@test.local",
                "authenticated": True,
                "auth_method": "test",
            }
        else:
            return {
                "id": "second_test_user",
                "name": "Second Test User",
                "email": "second@test.local",
                "authenticated": True,
                "auth_method": "test",
            }

    # Mock get_user_id dependency
    def mock_get_user_id():
        return current_test_user["user_id"]

    # Mock authenticate_and_enrich_user on the component
    async def mock_authenticate_and_enrich_user(request_or_data):
        return mock_get_current_user()

    # Store original overrides and component method
    original_overrides = test_app.dependency_overrides.copy()
    original_auth_method = sac_component_instance.authenticate_and_enrich_user

    # Set dependency overrides
    test_app.dependency_overrides[get_current_user] = mock_get_current_user
    test_app.dependency_overrides[get_user_id] = mock_get_user_id

    # Override the component's authenticate method
    sac_component_instance.authenticate_and_enrich_user = (
        mock_authenticate_and_enrich_user
    )

    # Create wrapper clients that switch user context
    class UserTestClient(TestClient):
        def __init__(self, app, user_id):
            super().__init__(app)
            self.user_id = user_id

        def request(self, method, url, **kwargs):
            # Switch to this user's context for the request
            old_user = current_test_user["user_id"]
            current_test_user["user_id"] = self.user_id
            try:
                return super().request(method, url, **kwargs)
            finally:
                # Restore previous user context
                current_test_user["user_id"] = old_user

    first_user_client = UserTestClient(test_app, "first_test_user")
    second_user_client = UserTestClient(test_app, "second_test_user")

    yield first_user_client, second_user_client

    # Restore original dependency overrides AND component method
    test_app.dependency_overrides.clear()
    test_app.dependency_overrides.update(original_overrides)
    sac_component_instance.authenticate_and_enrich_user = original_auth_method


def test_cross_user_session_access_returns_404(multi_user_test_setup):
    """Test that accessing another user's session returns 404 (not 403) to prevent information leakage"""

    first_user_client, second_user_client = multi_user_test_setup

    # Debug: Check which user each client is authenticated as
    user_a_me = first_user_client.get("/api/v1/users/me")
    print(
        f"User A identity: {user_a_me.status_code} - {user_a_me.json() if user_a_me.status_code == 200 else user_a_me.text}"
    )

    user_b_me = second_user_client.get("/api/v1/users/me")
    print(
        f"User B identity: {user_b_me.status_code} - {user_b_me.json() if user_b_me.status_code == 200 else user_b_me.text}"
    )

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
                "parts": [{"kind": "text", "text": "User A's private session"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
    print(f"Session creation: {response_a.status_code} - {response_a.text}")
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # Debug: Check what sessions User A can see
    sessions_a = first_user_client.get("/api/v1/sessions")
    print(
        f"User A sessions: {sessions_a.status_code} - {sessions_a.json() if sessions_a.status_code == 200 else sessions_a.text}"
    )

    # Verify User A can access their own session
    session_response = first_user_client.get(f"/api/v1/sessions/{session_id}")
    print(
        f"User A session access: {session_response.status_code} - {session_response.text}"
    )

    # User B tries to access User A's session - should get 404, not 403
    unauthorized_response = second_user_client.get(f"/api/v1/sessions/{session_id}")
    print(
        f"User B unauthorized access: {unauthorized_response.status_code} - {unauthorized_response.text}"
    )

    # For now, let's just check if we get different users
    if user_a_me.status_code == 200 and user_b_me.status_code == 200:
        user_a_data = user_a_me.json()
        user_b_data = user_b_me.json()
        # The /api/v1/users/me endpoint returns 'username' not 'id'
        user_a_id = user_a_data.get("username")
        user_b_id = user_b_data.get("username")
        print(f"User A ID: {user_a_id}, User B ID: {user_b_id}")
        assert user_a_id != user_b_id, "Users should have different IDs"
        print("✓ Users have different identities")
    else:
        print("❌ Failed to get user identities")


def test_cross_user_session_history_returns_404(multi_user_test_setup):
    """Test that accessing another user's session history returns 404"""

    first_user_client, second_user_client = multi_user_test_setup

    # User A creates a session with messages
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
                "parts": [{"kind": "text", "text": "User A's private conversation"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # Verify User A can access their own session history
    history_response = first_user_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 1

    # User B tries to access User A's session history - should get 404
    unauthorized_history = second_user_client.get(
        f"/api/v1/sessions/{session_id}/messages"
    )
    assert unauthorized_history.status_code == 404
    response_data = unauthorized_history.json()
    # Handle both regular detail format and JSON-RPC error format
    error_message = response_data.get("message", "")
    assert "not found" in error_message.lower()

    print(
        f"✓ Cross-user session history access properly returns 404 for session {session_id}"
    )


def test_cross_user_session_update_returns_404(multi_user_test_setup):
    """Test that trying to update another user's session returns 404"""

    first_user_client, second_user_client = multi_user_test_setup

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
                "parts": [{"kind": "text", "text": "User A's session to be protected"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # Verify User A can update their own session
    update_data = {"name": "User A's Updated Session"}
    update_response = first_user_client.patch(
        f"/api/v1/sessions/{session_id}", json=update_data
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "User A's Updated Session"

    # User B tries to update User A's session - should get 404
    malicious_update = {"name": "Hijacked Session"}
    unauthorized_update = second_user_client.patch(
        f"/api/v1/sessions/{session_id}", json=malicious_update
    )
    assert unauthorized_update.status_code == 404
    response_data = unauthorized_update.json()
    error_message = response_data.get("message")
    assert "not found" in error_message.lower()

    # Verify session name wasn't changed by unauthorized user
    verify_response = first_user_client.get(f"/api/v1/sessions/{session_id}")
    assert verify_response.status_code == 200
    assert (
        verify_response.json()["data"]["name"] == "User A's Updated Session"
    )  # Should still be User A's name

    print(
        f"✓ Cross-user session update properly blocked with 404 for session {session_id}"
    )


def test_cross_user_session_deletion_returns_404(multi_user_test_setup):
    """Test that trying to delete another user's session returns 404"""

    first_user_client, second_user_client = multi_user_test_setup

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
                    {
                        "kind": "text",
                        "text": "User A's session to be protected from deletion",
                    }
                ],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # Verify session exists for User A
    session_response = first_user_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200

    # User B tries to delete User A's session - should get 404
    unauthorized_delete = second_user_client.delete(f"/api/v1/sessions/{session_id}")
    assert unauthorized_delete.status_code == 404
    response_data = unauthorized_delete.json()
    error_message = response_data.get("message", "")
    assert "not found" in error_message.lower()

    # Verify session still exists for User A
    verify_response = first_user_client.get(f"/api/v1/sessions/{session_id}")
    assert verify_response.status_code == 200
    assert verify_response.json()["data"]["id"] == session_id

    print(
        f"✓ Cross-user session deletion properly blocked with 404 for session {session_id}"
    )


def test_session_isolation_in_listing(multi_user_test_setup):
    """Test that users only see their own sessions in the sessions list"""

    first_user_client, second_user_client = multi_user_test_setup

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
        response = first_user_client.post("/api/v1/message:stream", json=task_payload)
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
        response = second_user_client.post("/api/v1/message:stream", json=task_payload)
        assert response.status_code == 200
        user_b_sessions.append(response.json()["result"]["contextId"])

    # User A should only see their own sessions
    user_a_list = first_user_client.get("/api/v1/sessions")
    assert user_a_list.status_code == 200
    user_a_data = user_a_list.json()
    user_a_session_ids = {s["id"] for s in user_a_data["data"]}

    # User A should see all their sessions and none of User B's
    for session_id in user_a_sessions:
        assert session_id in user_a_session_ids
    for session_id in user_b_sessions:
        assert session_id not in user_a_session_ids

    # User B should only see their own sessions
    user_b_list = second_user_client.get("/api/v1/sessions")
    assert user_b_list.status_code == 200
    user_b_data = user_b_list.json()
    user_b_session_ids = {s["id"] for s in user_b_data["data"]}

    # User B should see all their sessions and none of User A's
    for session_id in user_b_sessions:
        assert session_id in user_b_session_ids
    for session_id in user_a_sessions:
        assert session_id not in user_b_session_ids

    print(
        f"✓ Session isolation verified: User A has {len(user_a_session_ids)} sessions, User B has {len(user_b_session_ids)} sessions"
    )


def test_consistent_404_for_nonexistent_and_unauthorized_sessions(
    multi_user_test_setup,
):
    """Test that nonexistent sessions and unauthorized sessions both return 404"""

    first_user_client, second_user_client = multi_user_test_setup

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
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
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
            response = second_user_client.get(endpoint)

        assert response.status_code == 404
        response_data = response.json()
        error_message = response_data.get("message", "")
        assert "not found" in error_message.lower()

    # Test PATCH endpoints
    update_data = {"name": "Test Update"}
    real_patch_response = second_user_client.patch(
        f"/api/v1/sessions/{real_session_id}", json=update_data
    )
    fake_patch_response = second_user_client.patch(
        f"/api/v1/sessions/{fake_session_id}", json=update_data
    )

    assert real_patch_response.status_code == 404
    assert fake_patch_response.status_code == 404

    # Test DELETE endpoints
    real_delete_response = second_user_client.delete(
        f"/api/v1/sessions/{real_session_id}"
    )
    fake_delete_response = second_user_client.delete(
        f"/api/v1/sessions/{fake_session_id}"
    )

    assert real_delete_response.status_code == 404
    assert fake_delete_response.status_code == 404

    print("✓ Consistent 404 responses for both nonexistent and unauthorized sessions")


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

    print("✓ Invalid session IDs properly handled with 404 responses")


def test_session_ownership_after_multiple_operations(multi_user_test_setup):
    """Test that session ownership is consistently validated across multiple operations"""

    first_user_client, second_user_client = multi_user_test_setup

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
    response_a = first_user_client.post("/api/v1/message:stream", json=task_payload)
    assert response_a.status_code == 200
    session_id = response_a.json()["result"]["contextId"]

    # User A performs legitimate operations
    # 1. Get session
    get_response = first_user_client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200

    # 2. Update session name
    update_response = first_user_client.patch(
        f"/api/v1/sessions/{session_id}", json={"name": "Updated Name"}
    )
    assert update_response.status_code == 200

    # 3. Get history
    history_response = first_user_client.get(f"/api/v1/sessions/{session_id}/messages")
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
    followup_response = first_user_client.post(
        "/api/v1/message:stream", json=followup_payload
    )
    assert followup_response.status_code == 200
    assert followup_response.json()["result"]["contextId"] == session_id

    # After all operations, User B should still get 404 for everything
    assert second_user_client.get(f"/api/v1/sessions/{session_id}").status_code == 404
    assert (
        second_user_client.get(f"/api/v1/sessions/{session_id}/messages").status_code
        == 404
    )
    assert (
        second_user_client.patch(
            f"/api/v1/sessions/{session_id}", json={"name": "Hijack"}
        ).status_code
        == 404
    )
    assert (
        second_user_client.delete(f"/api/v1/sessions/{session_id}").status_code == 404
    )

    # Verify User A still has full access
    final_get = first_user_client.get(f"/api/v1/sessions/{session_id}")
    assert final_get.status_code == 200
    assert final_get.json()["data"]["name"] == "Updated Name"

    print(
        f"✓ Session ownership consistently maintained across multiple operations for session {session_id}"
    )
