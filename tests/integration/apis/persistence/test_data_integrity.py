"""
Data integrity tests using FastAPI HTTP endpoints.

Tests session deletion cascades, cross-user data isolation, orphaned data prevention,
and database referential integrity through the HTTP API.
"""

import pytest
from fastapi.testclient import TestClient


def test_session_deletion_cascades_to_messages(api_client: TestClient):
    """Test that deleting a session removes all associated messages"""

    # Create a session with multiple messages
    task_data = {"agent_name": "TestAgent", "message": "First message in session"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Add more messages to the session
    additional_messages = [
        "Second message in conversation",
        "Third message with more content",
        "Fourth message to test cascade",
    ]

    for message in additional_messages:
        followup_data = {
            "agent_name": "TestAgent",
            "message": message,
            "session_id": session_id,
        }
        followup_response = api_client.post(
            "/api/v1/tasks/subscribe", data=followup_data
        )
        assert followup_response.status_code == 200
        assert followup_response.json()["result"]["sessionId"] == session_id

    # Verify session has multiple messages
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 4  # Should have at least 4 user messages

    message_contents = [
        msg["message"] for msg in history if msg["sender_type"] == "user"
    ]
    assert "First message in session" in message_contents
    assert "Fourth message to test cascade" in message_contents

    # Delete the session
    delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 204

    # Verify session no longer exists
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 404

    # Verify session history is also gone (should return 404, not empty list)
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 404

    print(f"✓ Session {session_id} and all associated messages successfully deleted")


@pytest.mark.skip(
    reason="Requires multi-user test architecture - both TestClients authenticate as same user due to AuthMiddleware limitations"
)
def test_cross_user_data_isolation_comprehensive(api_client: TestClient, test_app):
    """Test comprehensive data isolation between different users"""

    # Import needed components for second user
    import uuid
    from unittest.mock import AsyncMock, Mock

    # Create second user authentication mock
    def create_second_user_client():
        from fastapi.testclient import TestClient

        from solace_agent_mesh.gateway.http_sse import dependencies

        # Store original component
        original_component = dependencies.sac_component_instance

        # Create second mock component
        second_component = Mock()
        second_component.get_app.return_value = Mock(
            app_config={
                "frontend_use_authorization": False,
                "external_auth_service_url": "http://localhost:8080",
                "external_auth_callback_uri": "http://localhost:8000/api/v1/auth/callback",
                "external_auth_provider": "azure",
                "frontend_redirect_url": "http://localhost:3000",
            }
        )
        second_component.get_cors_origins.return_value = ["*"]

        mock_session_manager = Mock(secret_key="test-secret-key")
        mock_session_manager.get_a2a_client_id.return_value = "test-client-id-2"
        mock_session_manager.start_new_a2a_session.side_effect = (
            lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
        )
        mock_session_manager.ensure_a2a_session.side_effect = (
            lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
        )
        second_component.get_session_manager.return_value = mock_session_manager

        second_component.identity_service = None
        second_component.submit_a2a_task = AsyncMock(return_value="test-task-id")
        second_component.cancel_a2a_task = AsyncMock()
        second_component._translate_external_input = AsyncMock(
            return_value=("TestAgent", [], {})
        )

        # Different user authentication
        second_component.authenticate_and_enrich_user = AsyncMock(
            return_value={
                "id": "isolation_test_user_2",
                "name": "Isolation Test User 2",
                "email": "user2@isolation.test",
                "authenticated": True,
                "auth_method": "development",
            }
        )

        dependencies.set_component_instance(second_component)
        client = TestClient(test_app)

        return client, lambda: dependencies.set_component_instance(original_component)

    second_client, cleanup = create_second_user_client()

    try:
        # User 1 creates multiple sessions with different agents
        user1_sessions = []
        agents = ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]

        for i, agent in enumerate(agents):
            task_data = {
                "agent_name": agent,
                "message": f"User 1's session {i + 1} with {agent}",
            }
            response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
            assert response.status_code == 200
            session_id = response.json()["result"]["sessionId"]
            user1_sessions.append((session_id, agent))

            # Add follow-up message
            followup_data = {
                "agent_name": agent,
                "message": f"User 1's follow-up in session {i + 1}",
                "session_id": session_id,
            }
            followup_response = api_client.post(
                "/api/v1/tasks/subscribe", data=followup_data
            )
            assert followup_response.status_code == 200

        # User 2 creates sessions with same agents
        user2_sessions = []

        for i, agent in enumerate(agents):
            task_data = {
                "agent_name": agent,
                "message": f"User 2's session {i + 1} with {agent}",
            }
            response = second_client.post("/api/v1/tasks/subscribe", data=task_data)
            assert response.status_code == 200
            session_id = response.json()["result"]["sessionId"]
            user2_sessions.append((session_id, agent))

        # Verify User 1 can only see their own sessions
        user1_list = api_client.get("/api/v1/sessions")
        assert user1_list.status_code == 200
        user1_session_ids = {s["id"] for s in user1_list.json()}

        # User 1 should see all their sessions
        for session_id, agent in user1_sessions:
            assert session_id in user1_session_ids

        # User 1 should not see any of User 2's sessions
        for session_id, agent in user2_sessions:
            assert session_id not in user1_session_ids

        # Verify User 2 can only see their own sessions
        user2_list = second_client.get("/api/v1/sessions")
        assert user2_list.status_code == 200
        user2_session_ids = {s["id"] for s in user2_list.json()}

        # User 2 should see all their sessions
        for session_id, agent in user2_sessions:
            assert session_id in user2_session_ids

        # User 2 should not see any of User 1's sessions
        for session_id, agent in user1_sessions:
            assert session_id not in user2_session_ids

        # Test message content isolation
        user1_session_id, _ = user1_sessions[0]
        user1_history = api_client.get(f"/api/v1/sessions/{user1_session_id}/messages")
        assert user1_history.status_code == 200
        user1_messages = [
            msg["message"]
            for msg in user1_history.json()
            if msg["sender_type"] == "user"
        ]

        # User 1's messages should contain their content
        assert any("User 1's session" in msg for msg in user1_messages)
        assert not any("User 2's session" in msg for msg in user1_messages)

        print(
            f"✓ Data isolation verified: User 1 has {len(user1_session_ids)} sessions, User 2 has {len(user2_session_ids)} sessions"
        )

    finally:
        cleanup()


def test_orphaned_data_prevention(api_client: TestClient):
    """Test that messages cannot exist without valid sessions"""

    # Create a session with messages
    task_data = {
        "agent_name": "TestAgent",
        "message": "Message that should not become orphaned",
    }
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Add more messages
    for i in range(3):
        followup_data = {
            "agent_name": "TestAgent",
            "message": f"Additional message {i + 1}",
            "session_id": session_id,
        }
        followup_response = api_client.post(
            "/api/v1/tasks/subscribe", data=followup_data
        )
        assert followup_response.status_code == 200

    # Verify messages exist
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    messages_before = history_response.json()
    assert len(messages_before) >= 4

    # Delete the session (should cascade delete messages)
    delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 204

    # Verify session is gone
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 404

    # Verify messages are gone (not orphaned)
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 404

    # Try to add message to deleted session (should fail)
    orphan_attempt_data = {
        "agent_name": "TestAgent",
        "message": "Attempt to create orphaned message",
        "session_id": session_id,
    }
    orphan_response = api_client.post(
        "/api/v1/tasks/subscribe", data=orphan_attempt_data
    )
    # This should either create a new session or fail gracefully
    # The important thing is it doesn't create orphaned messages
    if orphan_response.status_code == 200:
        # If it succeeds, it should have created a new session
        new_session_id = orphan_response.json()["result"]["sessionId"]
        assert new_session_id != session_id  # Should be a different session

    print(f"✓ Orphaned message prevention verified for session {session_id}")


def test_referential_integrity_with_multiple_deletions(api_client: TestClient):
    """Test database referential integrity with multiple session deletions"""

    # Create multiple sessions with various message counts
    sessions_data = []

    for i in range(5):
        # Create session
        task_data = {
            "agent_name": "TestAgent",
            "message": f"Initial message for session {i + 1}",
        }
        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["sessionId"]

        # Add varying numbers of messages
        message_count = (i + 1) * 2  # 2, 4, 6, 8, 10 messages
        for j in range(message_count - 1):  # -1 because we already have initial message
            followup_data = {
                "agent_name": "TestAgent",
                "message": f"Message {j + 2} in session {i + 1}",
                "session_id": session_id,
            }
            followup_response = api_client.post(
                "/api/v1/tasks/subscribe", data=followup_data
            )
            assert followup_response.status_code == 200

        sessions_data.append((session_id, message_count))

    # Verify all sessions exist with expected message counts
    for session_id, expected_count in sessions_data:
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200
        messages = history_response.json()
        user_messages = [msg for msg in messages if msg["sender_type"] == "user"]
        assert len(user_messages) >= expected_count

    # Delete sessions in random order
    import random

    deletion_order = sessions_data.copy()
    random.shuffle(deletion_order)

    deleted_sessions = []
    remaining_sessions = sessions_data.copy()

    for session_id, expected_count in deletion_order[:3]:  # Delete first 3
        delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
        assert delete_response.status_code == 204
        deleted_sessions.append(session_id)
        remaining_sessions = [
            (sid, count) for sid, count in remaining_sessions if sid != session_id
        ]

        # Verify deleted session is gone
        verify_response = api_client.get(f"/api/v1/sessions/{session_id}")
        assert verify_response.status_code == 404

        # Verify remaining sessions are unaffected
        for remaining_id, remaining_count in remaining_sessions:
            remaining_response = api_client.get(f"/api/v1/sessions/{remaining_id}")
            assert remaining_response.status_code == 200

            remaining_history = api_client.get(
                f"/api/v1/sessions/{remaining_id}/messages"
            )
            assert remaining_history.status_code == 200
            remaining_messages = remaining_history.json()
            user_messages = [
                msg for msg in remaining_messages if msg["sender_type"] == "user"
            ]
            assert len(user_messages) >= remaining_count

    # Verify session list only contains remaining sessions
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()
    current_session_ids = {s["id"] for s in sessions_data["sessions"]}

    for session_id in deleted_sessions:
        assert session_id not in current_session_ids

    for session_id, _ in remaining_sessions:
        assert session_id in current_session_ids

    print(
        f"✓ Referential integrity maintained through {len(deleted_sessions)} deletions"
    )


def test_session_consistency_across_operations(api_client: TestClient):
    """Test that session data remains consistent across multiple operations"""

    # Create a session
    task_data = {
        "agent_name": "TestAgent",
        "message": "Initial consistency test message",
    }
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Perform multiple operations and verify consistency
    operations = []

    # 1. Update session name
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json={"name": "Consistency Test Session"}
    )
    assert update_response.status_code == 200
    operations.append("name_update")

    # 2. Add multiple messages
    for i in range(5):
        msg_data = {
            "agent_name": "TestAgent",
            "message": f"Consistency test message {i + 2}",
            "session_id": session_id,
        }
        msg_response = api_client.post("/api/v1/tasks/subscribe", data=msg_data)
        assert msg_response.status_code == 200
        assert msg_response.json()["result"]["sessionId"] == session_id
        operations.append(f"message_{i + 2}")

    # 3. Verify session integrity after each operation
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["id"] == session_id
    assert session_data["name"] == "Consistency Test Session"
    assert session_data["agent_id"] == "TestAgent"

    # 4. Verify message history consistency
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 6  # Initial + 5 additional messages

    # Verify message ordering and content
    expected_messages = [
        "Initial consistency test message",
        "Consistency test message 2",
        "Consistency test message 3",
        "Consistency test message 4",
        "Consistency test message 5",
        "Consistency test message 6",
    ]

    actual_messages = [msg["message"] for msg in user_messages]
    for expected_msg in expected_messages:
        assert expected_msg in actual_messages

    # 5. Verify session appears in sessions list with correct data
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()

    target_session = next(
        (s for s in sessions_data["sessions"] if s["id"] == session_id), None
    )
    assert target_session is not None
    assert target_session["name"] == "Consistency Test Session"
    assert target_session["agent_id"] == "TestAgent"

    print(f"✓ Session consistency maintained across {len(operations)} operations")


def test_data_integrity_under_concurrent_operations(api_client: TestClient):
    """Test data integrity when performing multiple operations on the same session"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Concurrent operations test"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Perform multiple operations in sequence (simulating concurrent access)
    operations_results = []

    # Add messages
    for i in range(10):
        msg_data = {
            "agent_name": "TestAgent",
            "message": f"Concurrent message {i + 1}",
            "session_id": session_id,
        }
        msg_response = api_client.post("/api/v1/tasks/subscribe", data=msg_data)
        operations_results.append(("message", msg_response.status_code == 200))

    # Update session name multiple times
    for i in range(3):
        update_data = {"name": f"Updated Name {i + 1}"}
        update_response = api_client.patch(
            f"/api/v1/sessions/{session_id}", json=update_data
        )
        operations_results.append(("update", update_response.status_code == 200))

    # Get session and history multiple times
    for i in range(5):
        get_response = api_client.get(f"/api/v1/sessions/{session_id}")
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        operations_results.append(("get", get_response.status_code == 200))
        operations_results.append(("history", history_response.status_code == 200))

    # Verify all operations succeeded
    successful_ops = sum(1 for _, success in operations_results if success)
    total_ops = len(operations_results)
    assert successful_ops == total_ops, (
        f"Only {successful_ops}/{total_ops} operations succeeded"
    )

    # Verify final data integrity
    final_session = api_client.get(f"/api/v1/sessions/{session_id}")
    assert final_session.status_code == 200
    session_data = final_session.json()
    assert session_data["id"] == session_id
    assert session_data["name"] == "Updated Name 3"  # Should have the last update

    final_history = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert final_history.status_code == 200
    history = final_history.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 11  # Initial + 10 concurrent messages

    # Check that all concurrent messages are present
    message_contents = [msg["message"] for msg in user_messages]
    assert "Concurrent operations test" in message_contents
    for i in range(10):
        assert f"Concurrent message {i + 1}" in message_contents

    print(
        f"✓ Data integrity maintained through {total_ops} operations on session {session_id}"
    )


def test_user_data_cleanup_integrity(api_client: TestClient):
    """Test that when all user sessions are deleted, no orphaned data remains"""

    # Create multiple sessions for the user
    session_ids = []

    for i in range(4):
        task_data = {
            "agent_name": "TestAgent" if i % 2 == 0 else "TestPeerAgentA",
            "message": f"Cleanup test session {i + 1}",
        }
        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["sessionId"]
        session_ids.append(session_id)

        # Add messages to each session
        for j in range(3):
            msg_data = {
                "agent_name": task_data["agent_name"],
                "message": f"Message {j + 1} in session {i + 1}",
                "session_id": session_id,
            }
            msg_response = api_client.post("/api/v1/tasks/subscribe", data=msg_data)
            assert msg_response.status_code == 200

    # Verify all sessions exist
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()
    assert len(sessions_data["sessions"]) >= 4

    current_session_ids = {s["id"] for s in sessions_data["sessions"]}
    for session_id in session_ids:
        assert session_id in current_session_ids

    # Delete all sessions one by one
    for session_id in session_ids:
        delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
        assert delete_response.status_code == 204

        # Verify session is gone
        verify_response = api_client.get(f"/api/v1/sessions/{session_id}")
        assert verify_response.status_code == 404

        # Verify history is gone
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 404

    # Verify user has no remaining sessions
    final_sessions_list = api_client.get("/api/v1/sessions")
    assert final_sessions_list.status_code == 200
    final_sessions = final_sessions_list.json()

    # Should be empty or not contain any of our deleted sessions
    final_session_ids = {s["id"] for s in final_sessions["sessions"]}
    for session_id in session_ids:
        assert session_id not in final_session_ids

    print(f"✓ Clean user data cleanup verified for {len(session_ids)} sessions")
