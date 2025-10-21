"""
Data integrity tests using FastAPI HTTP endpoints.

Tests session deletion cascades, cross-user data isolation, orphaned data prevention,
and database referential integrity through the HTTP API.
"""

import pytest
from fastapi.testclient import TestClient

from src.solace_agent_mesh.gateway.http_sse.routers.dto.responses.task_responses import (
    TaskResponse,
)

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter


def test_session_deletion_cascades_to_messages(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that deleting a session removes all associated messages"""
    # Arrange: Create a session and add messages using the gateway adapter
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(session.id, "First message in session")
    gateway_adapter.send_message(session.id, "Second message")
    gateway_adapter.send_message(session.id, "Third message")

    # Verify session has messages
    messages = database_inspector.get_session_messages(session.id)
    # Each user message results in an agent response, so 3 user messages -> 6 total messages
    assert len(messages) >= 6
    message_contents = []
    for message in messages:
        assert isinstance(message, TaskResponse)
        if message.user_message:
            message_contents.append(message.user_message)

    assert "First message in session" in message_contents
    assert "Third message" in message_contents

    # Act: Delete the session via the API
    delete_response = api_client.delete(f"/api/v1/sessions/{session.id}")
    assert delete_response.status_code == 204

    # Assert: Verify session and its history are gone
    session_response = api_client.get(f"/api/v1/sessions/{session.id}")
    assert session_response.status_code == 404
    history_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
    assert history_response.status_code == 404


def test_cross_user_data_isolation_comprehensive(
    gateway_adapter: GatewayAdapter,
    secondary_gateway_adapter: GatewayAdapter,
    api_client: TestClient,
    secondary_api_client: TestClient,
    database_inspector: DatabaseInspector,
    secondary_database_inspector: DatabaseInspector,
):
    """Test comprehensive data isolation between different users"""
    # Arrange: Create sessions and messages for two different users
    user1_session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(user1_session.id, "Message from user 1")

    user2_session = secondary_gateway_adapter.create_session(
        user_id="secondary_user", agent_name="TestAgent"
    )
    secondary_gateway_adapter.send_message(user2_session.id, "Message from user 2")

    # Act & Assert:
    # User 1 should only see their own session
    user1_sessions = database_inspector.get_gateway_sessions(user_id="sam_dev_user")
    user1_session_ids = {s.id for s in user1_sessions}
    assert user1_session.id in user1_session_ids
    assert user2_session.id not in user1_session_ids

    # User 2 should only see their own session
    user2_sessions = secondary_database_inspector.get_gateway_sessions(
        user_id="secondary_user"
    )
    user2_session_ids = {s.id for s in user2_sessions}
    assert user2_session.id in user2_session_ids
    assert user1_session.id not in user2_session_ids

    # User 2 should get a 404 when trying to access User 1's session directly
    response = secondary_api_client.get(f"/api/v1/sessions/{user1_session.id}")
    assert response.status_code == 404


def test_orphaned_data_prevention(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test that messages cannot exist without valid sessions"""
    # Create a session with messages using the gateway adapter
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    # Add messages using the gateway adapter
    gateway_adapter.send_message(session.id, "Message that should not become orphaned")
    for i in range(3):
        gateway_adapter.send_message(session.id, f"Additional message {i + 1}")

    # Verify messages exist via API
    history_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
    assert history_response.status_code == 200
    messages_before = history_response.json()
    assert len(messages_before) >= 4

    # Delete the session (should cascade delete messages)
    delete_response = api_client.delete(f"/api/v1/sessions/{session.id}")
    assert delete_response.status_code == 204

    # Verify session is gone
    session_response = api_client.get(f"/api/v1/sessions/{session.id}")
    assert session_response.status_code == 404

    # Verify messages are gone (not orphaned)
    history_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
    assert history_response.status_code == 404

    # Try to send message to deleted session using gateway adapter (should fail)
    with pytest.raises(ValueError, match=f"Session {session.id} not found"):
        gateway_adapter.send_message(session.id, "Attempt to create orphaned message")


def test_referential_integrity_with_multiple_deletions(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test database referential integrity with multiple session deletions"""

    # Create multiple sessions with various message counts using gateway adapter
    sessions_data = []

    for i in range(5):
        # Create session using gateway adapter
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        # Add varying numbers of messages
        message_count = (i + 1) * 2  # 2, 4, 6, 8, 10 messages
        for j in range(message_count):
            gateway_adapter.send_message(
                session.id, f"Message {j + 1} in session {i + 1}"
            )

        sessions_data.append((session.id, message_count))

    # Verify all sessions exist with expected message counts
    for session_id, expected_count in sessions_data:
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200
        messages = history_response.json()
        assert len(messages) >= expected_count

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
            assert len(remaining_messages) >= remaining_count

    # Verify session list only contains remaining sessions
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()
    current_session_ids = {s["id"] for s in sessions_data["data"]}

    for session_id in deleted_sessions:
        assert session_id not in current_session_ids

    for session_id, _ in remaining_sessions:
        assert session_id in current_session_ids


def test_session_consistency_across_operations(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test that session data remains consistent across multiple operations"""

    # Create a session using gateway adapter
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    session_id = session.id

    # Add initial message using gateway adapter
    gateway_adapter.send_message(session_id, "Initial consistency test message")

    # Perform multiple operations and verify consistency
    operations = []

    # 1. Update session name
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json={"name": "Consistency Test Session"}
    )
    assert update_response.status_code == 200
    operations.append("name_update")

    # 2. Add multiple messages using gateway adapter
    for i in range(5):
        gateway_adapter.send_message(session_id, f"Consistency test message {i + 2}")
        operations.append(f"message_{i + 2}")

    # 3. Verify session integrity after each operation
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["data"]["id"] == session_id
    assert session_data["data"]["name"] == "Consistency Test Session"
    assert session_data["data"]["agentId"] == "TestAgent"

    # 4. Verify message history consistency
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    # Verify we have messages
    assert len(history) >= 6  # Initial + 5 additional messages

    # Verify message ordering and content by checking all message contents
    expected_messages = [
        "Initial consistency test message",
        "Consistency test message 2",
        "Consistency test message 3",
        "Consistency test message 4",
        "Consistency test message 5",
        "Consistency test message 6",
    ]

    all_message_contents = [msg.get("message", "") for msg in history]
    for expected_msg in expected_messages:
        assert expected_msg in all_message_contents

    # 5. Verify session appears in sessions list with correct data
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()

    target_session = next(
        (s for s in sessions_data["data"] if s["id"] == session_id), None
    )
    assert target_session is not None
    assert target_session["name"] == "Consistency Test Session"
    assert target_session["agentId"] == "TestAgent"


def test_data_integrity_under_concurrent_operations(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test data integrity when performing multiple operations on the same session"""

    # Create a session using gateway adapter
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    session_id = session.id

    # Add initial message using gateway adapter
    gateway_adapter.send_message(session_id, "Concurrent operations test")

    # Perform multiple operations in sequence (simulating concurrent access)
    operations_results = []

    # Add messages using gateway adapter
    for i in range(10):
        try:
            gateway_adapter.send_message(session_id, f"Concurrent message {i + 1}")
            operations_results.append(("message", True))
        except Exception:
            operations_results.append(("message", False))

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
    assert session_data["data"]["id"] == session_id
    assert (
        session_data["data"]["name"] == "Updated Name 3"
    )  # Should have the last update

    final_history = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert final_history.status_code == 200
    history = final_history.json()

    # Verify we have messages
    assert len(history) >= 11  # Initial + 10 concurrent messages

    # Check that all concurrent messages are present by checking all message contents
    all_message_contents = [msg.get("message", "") for msg in history]
    assert "Concurrent operations test" in all_message_contents
    for i in range(10):
        assert f"Concurrent message {i + 1}" in all_message_contents


def test_user_data_cleanup_integrity(api_client: TestClient):
    """Test that when all user sessions are deleted, no orphaned data remains"""

    import uuid

    # Create multiple sessions for the user
    session_ids = []

    for i in range(4):
        agent_name = "TestAgent" if i % 2 == 0 else "TestPeerAgentA"
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
                        {"kind": "text", "text": f"Cleanup test session {i + 1}"}
                    ],
                    "metadata": {"agent_name": agent_name},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        assert response.status_code == 200
        session_id = response.json()["result"]["contextId"]
        session_ids.append(session_id)

        # Add messages to each session
        for j in range(3):
            msg_payload = {
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
                                "text": f"Message {j + 1} in session {i + 1}",
                            }
                        ],
                        "metadata": {"agent_name": agent_name},
                        "contextId": session_id,
                    }
                },
            }
            msg_response = api_client.post("/api/v1/message:stream", json=msg_payload)
            assert msg_response.status_code == 200

    # Verify all sessions exist
    sessions_list = api_client.get("/api/v1/sessions")
    assert sessions_list.status_code == 200
    sessions_data = sessions_list.json()
    assert len(sessions_data["data"]) >= 4

    current_session_ids = {s["id"] for s in sessions_data["data"]}
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
    final_session_ids = {s["id"] for s in final_sessions["data"]}
    for session_id in session_ids:
        assert session_id not in final_session_ids
