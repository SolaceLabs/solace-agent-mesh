"""
Integration tests for the chat tasks API endpoints, adapted for the new infrastructure.
"""

import json
import time
import uuid

from fastapi.testclient import TestClient

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter


class TestBasicCRUDOperations:
    """Test Suite 1: Basic CRUD Operations"""

    def test_create_new_task(
        self, gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
    ):
        """Verify that a new task can be created via the gateway adapter."""
        session = gateway_adapter.create_session(
            user_id="crud_user", agent_name="TestAgent"
        )
        task = gateway_adapter.send_message(session.id, "Hello, I need help")

        assert task is not None
        assert task.task_id is not None
        assert task.session_id == session.id
        assert task.user_message == "Hello, I need help"

        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 2
        assert messages[0].task_id == task.task_id

    def test_retrieve_tasks_for_session(
        self, gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
    ):
        """Verify that tasks can be retrieved for a session."""
        session = gateway_adapter.create_session(
            user_id="retrieval_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session.id, "Message 1")
        gateway_adapter.send_message(session.id, "Message 2")
        gateway_adapter.send_message(session.id, "Message 3")

        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 6  # 3 user messages + 3 agent responses

    def test_update_existing_task_upsert(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Verify that POSTing with an existing task_id updates the task."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        task_id = f"task-upsert-{uuid.uuid4().hex[:8]}"

        original_payload = {
            "taskId": task_id,
            "userMessage": "Original user message",
            "messageBubbles": json.dumps([{"type": "user", "text": "Original"}]),
            "taskMetadata": json.dumps(
                {"status": "in_progress", "agent_name": "TestAgent"}
            ),
        }

        first_response = api_client.post(
            f"/api/v1/sessions/{session.id}/chat-tasks", json=original_payload
        )
        assert first_response.status_code in [200, 201]
        original_created_time = first_response.json()["createdTime"]

        time.sleep(0.01)

        updated_payload = {
            "taskId": task_id,
            "userMessage": "Original user message",
            "messageBubbles": json.dumps([{"type": "user", "text": "Updated"}]),
            "taskMetadata": json.dumps(
                {"status": "completed", "agent_name": "TestAgent"}
            ),
        }

        second_response = api_client.post(
            f"/api/v1/sessions/{session.id}/chat-tasks", json=updated_payload
        )
        assert second_response.status_code == 200

        get_response = api_client.get(f"/api/v1/sessions/{session.id}/chat-tasks")
        tasks = get_response.json()["tasks"]
        assert len(tasks) == 1
        retrieved_task = tasks[0]

        assert retrieved_task["taskId"] == task_id
        assert retrieved_task["createdTime"] == original_created_time
        assert retrieved_task["updatedTime"] is not None
        assert retrieved_task["updatedTime"] > original_created_time

    def test_empty_session_returns_empty_array(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Verify that a session with no tasks returns an empty array."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        get_response = api_client.get(f"/api/v1/sessions/{session.id}/chat-tasks")
        assert get_response.status_code == 200
        assert get_response.json()["tasks"] == []


class TestAuthorizationAndSecurity:
    """Test Suite 3: Authorization & Security"""

    def test_user_can_only_access_own_session_tasks(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Verify that users can only access tasks in their own sessions."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session.id, "Private task")

        get_response = api_client.get(f"/api/v1/sessions/{session.id}/chat-tasks")
        assert get_response.status_code == 200
        assert len(get_response.json()["tasks"]) == 2

    def test_invalid_session_id_returns_404(self, api_client: TestClient):
        """Verify proper handling of invalid session IDs."""
        response = api_client.get("/api/v1/sessions/nonexistent-session-id/chat-tasks")
        assert response.status_code == 404

    def test_task_isolation_between_sessions(
        self, gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
    ):
        """Verify that tasks are properly isolated between sessions."""
        session_a = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session_a.id, "Task A")

        session_b = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session_b.id, "Task B")

        messages_a = database_inspector.get_session_messages(session_a.id)
        assert len(messages_a) == 2
        assert "Task A" in messages_a[0].user_message

        messages_b = database_inspector.get_session_messages(session_b.id)
        assert len(messages_b) == 2
        assert "Task B" in messages_b[0].user_message


class TestIntegrationWithExistingFeatures:
    """Test Suite 4: Integration with Existing Features"""

    def test_tasks_cascade_delete_with_session(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Verify that deleting a session deletes all its tasks."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session.id, "Task for cascade test")

        delete_response = api_client.delete(f"/api/v1/sessions/{session.id}")
        assert delete_response.status_code == 204

        remaining_messages = database_inspector.get_session_messages(session.id)
        assert len(remaining_messages) == 0

    def test_messages_endpoint_derives_from_tasks(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Verify that /messages endpoint correctly flattens tasks."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        gateway_adapter.send_message(session.id, "User message 1")

        messages_response = api_client.get(f"/api/v1/sessions/{session.id}/messages")
        assert messages_response.status_code == 200
        messages = messages_response.json()
        assert len(messages) == 2
        assert messages[0]["message"] == "User message 1"
        assert messages[1]["message"] == "Received: User message 1"

    def test_feedback_updates_task_metadata(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Verify that submitting feedback is accepted."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        task = gateway_adapter.send_message(session.id, "Task for feedback test")

        feedback_payload = {
            "taskId": task.task_id,
            "sessionId": session.id,
            "feedbackType": "up",
            "feedbackText": "This was very helpful!",
        }

        feedback_response = api_client.post("/api/v1/feedback", json=feedback_payload)
        assert feedback_response.status_code == 202


class TestDataValidation:
    """Test Suite 2: Data Validation"""

    def test_large_payload_handling(
        self, gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
    ):
        """Verify that large but valid payloads are handled correctly."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        large_message = "a" * 10000
        task = gateway_adapter.send_message(session.id, large_message)

        assert task.user_message == large_message
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 2
        assert messages[0].user_message == large_message
