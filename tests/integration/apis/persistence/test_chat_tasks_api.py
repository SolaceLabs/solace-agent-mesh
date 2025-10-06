"""
Integration tests for the chat tasks API endpoints.

Tests the new task-centric data model where tasks store complete user-agent
interactions with message_bubbles and task_metadata as opaque JSON strings.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient


class TestBasicCRUDOperations:
    """Test Suite 1: Basic CRUD Operations"""

    def test_create_new_task(self, api_client: TestClient):
        """
        Test 1.1: Create New Task
        
        Purpose: Verify that a new task can be created via POST
        
        Steps:
        1. Create a session via /message:stream
        2. POST a new task to /sessions/{session_id}/chat-tasks
        3. Verify response status is 201 (Created)
        4. Verify response contains all task fields
        5. Verify task_id matches request
        6. Verify created_time is set
        7. Verify updated_time is None (new task)
        """
        # Step 1: Create a session
        session_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Create session for task test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        
        session_response = api_client.post("/api/v1/message:stream", json=session_payload)
        assert session_response.status_code == 200
        session_id = session_response.json()["result"]["contextId"]
        
        # Step 2: POST a new task
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        
        # Create message_bubbles as a JSON string (opaque to backend)
        message_bubbles = json.dumps([
            {"type": "user", "text": "Hello, I need help"},
            {"type": "agent", "text": "Hi there, how can I assist you?"}
        ])
        
        # Create task_metadata as a JSON string (opaque to backend)
        task_metadata = json.dumps({
            "status": "completed",
            "agent_name": "TestAgent"
        })
        
        task_payload = {
            "taskId": task_id,
            "userMessage": "Hello, I need help",
            "messageBubbles": message_bubbles,
            "taskMetadata": task_metadata
        }
        
        task_response = api_client.post(
            f"/api/v1/sessions/{session_id}/chat-tasks",
            json=task_payload
        )
        
        # Step 3: Verify response status is 201 (Created)
        assert task_response.status_code == 201 or task_response.status_code == 200
        
        # Step 4: Verify response contains all task fields
        response_data = task_response.json()
        assert "taskId" in response_data
        assert "sessionId" in response_data
        assert "userMessage" in response_data
        assert "messageBubbles" in response_data
        assert "taskMetadata" in response_data
        assert "createdTime" in response_data
        
        # Step 5: Verify task_id matches request
        assert response_data["taskId"] == task_id
        assert response_data["sessionId"] == session_id
        
        # Step 6: Verify created_time is set
        assert response_data["createdTime"] is not None
        assert isinstance(response_data["createdTime"], int)
        assert response_data["createdTime"] > 0
        
        # Step 7: Verify updated_time is None (new task)
        assert response_data.get("updatedTime") is None
        
        # Verify the data was stored correctly
        assert response_data["userMessage"] == "Hello, I need help"
        assert response_data["messageBubbles"] == message_bubbles
        assert response_data["taskMetadata"] == task_metadata
        
        print(f"✓ Test 1.1 passed: Created new task {task_id} for session {session_id}")
