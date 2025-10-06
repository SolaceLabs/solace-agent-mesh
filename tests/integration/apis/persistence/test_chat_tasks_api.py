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

    def test_retrieve_tasks_for_session(self, api_client: TestClient):
        """
        Test 1.2: Retrieve Tasks for Session
        
        Purpose: Verify that tasks can be retrieved via GET
        
        Steps:
        1. Create a session
        2. Create 3 tasks via POST
        3. GET /sessions/{session_id}/chat-tasks
        4. Verify response status is 200
        5. Verify response contains array of 3 tasks
        6. Verify tasks are in chronological order (by created_time)
        7. Verify each task has all required fields
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
                    "parts": [{"kind": "text", "text": "Create session for multiple tasks"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        
        session_response = api_client.post("/api/v1/message:stream", json=session_payload)
        assert session_response.status_code == 200
        session_id = session_response.json()["result"]["contextId"]
        
        # Step 2: Create 3 tasks via POST
        task_ids = []
        for i in range(3):
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            task_ids.append(task_id)
            
            message_bubbles = json.dumps([
                {"type": "user", "text": f"User message {i+1}"},
                {"type": "agent", "text": f"Agent response {i+1}"}
            ])
            
            task_metadata = json.dumps({
                "status": "completed",
                "agent_name": "TestAgent",
                "task_number": i+1
            })
            
            task_payload = {
                "taskId": task_id,
                "userMessage": f"User message {i+1}",
                "messageBubbles": message_bubbles,
                "taskMetadata": task_metadata
            }
            
            task_response = api_client.post(
                f"/api/v1/sessions/{session_id}/chat-tasks",
                json=task_payload
            )
            assert task_response.status_code in [200, 201]
            
            # Small delay to ensure different created_time values
            import time
            time.sleep(0.01)
        
        # Step 3: GET /sessions/{session_id}/chat-tasks
        get_response = api_client.get(f"/api/v1/sessions/{session_id}/chat-tasks")
        
        # Step 4: Verify response status is 200
        assert get_response.status_code == 200
        
        # Step 5: Verify response contains array of 3 tasks
        response_data = get_response.json()
        assert "tasks" in response_data
        tasks = response_data["tasks"]
        assert len(tasks) == 3
        
        # Step 6: Verify tasks are in chronological order (by created_time)
        created_times = [task["createdTime"] for task in tasks]
        assert created_times == sorted(created_times), "Tasks should be in chronological order"
        
        # Step 7: Verify each task has all required fields
        for i, task in enumerate(tasks):
            assert "taskId" in task
            assert "sessionId" in task
            assert "userMessage" in task
            assert "messageBubbles" in task
            assert "taskMetadata" in task
            assert "createdTime" in task
            
            # Verify task belongs to this session
            assert task["sessionId"] == session_id
            
            # Verify task_id is one we created
            assert task["taskId"] in task_ids
            
            # Verify data integrity
            assert isinstance(task["messageBubbles"], str)
            assert isinstance(task["taskMetadata"], str)
            
            # Verify we can parse the JSON strings
            bubbles = json.loads(task["messageBubbles"])
            assert isinstance(bubbles, list)
            assert len(bubbles) == 2
            
            metadata = json.loads(task["taskMetadata"])
            assert isinstance(metadata, dict)
            assert metadata["status"] == "completed"
        
        print(f"✓ Test 1.2 passed: Retrieved {len(tasks)} tasks for session {session_id}")

    def test_update_existing_task_upsert(self, api_client: TestClient):
        """
        Test 1.3: Update Existing Task (Upsert)
        
        Purpose: Verify that POSTing with existing task_id updates the task
        
        Steps:
        1. Create a session
        2. POST a task with task_id "task-123"
        3. Verify response status is 201
        4. POST again with same task_id but different message_bubbles
        5. Verify response status is 200 (not 201)
        6. Verify updated_time is now set
        7. GET the task and verify message_bubbles was updated
        8. Verify created_time remained unchanged
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
                    "parts": [{"kind": "text", "text": "Create session for upsert test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        
        session_response = api_client.post("/api/v1/message:stream", json=session_payload)
        assert session_response.status_code == 200
        session_id = session_response.json()["result"]["contextId"]
        
        # Step 2: POST a task with task_id "task-123"
        task_id = f"task-upsert-{uuid.uuid4().hex[:8]}"
        
        original_bubbles = json.dumps([
            {"type": "user", "text": "Original user message"},
            {"type": "agent", "text": "Original agent response"}
        ])
        
        original_metadata = json.dumps({
            "status": "in_progress",
            "agent_name": "TestAgent"
        })
        
        original_payload = {
            "taskId": task_id,
            "userMessage": "Original user message",
            "messageBubbles": original_bubbles,
            "taskMetadata": original_metadata
        }
        
        first_response = api_client.post(
            f"/api/v1/sessions/{session_id}/chat-tasks",
            json=original_payload
        )
        
        # Step 3: Verify response status is 201
        assert first_response.status_code == 201
        first_data = first_response.json()
        original_created_time = first_data["createdTime"]
        assert first_data["updatedTime"] is None
        
        # Small delay to ensure different timestamp
        import time
        time.sleep(0.01)
        
        # Step 4: POST again with same task_id but different message_bubbles
        updated_bubbles = json.dumps([
            {"type": "user", "text": "Original user message"},
            {"type": "agent", "text": "Original agent response"},
            {"type": "agent", "text": "Additional agent message"}
        ])
        
        updated_metadata = json.dumps({
            "status": "completed",
            "agent_name": "TestAgent"
        })
        
        updated_payload = {
            "taskId": task_id,
            "userMessage": "Original user message",
            "messageBubbles": updated_bubbles,
            "taskMetadata": updated_metadata
        }
        
        second_response = api_client.post(
            f"/api/v1/sessions/{session_id}/chat-tasks",
            json=updated_payload
        )
        
        # Step 5: Verify response status is 200 (not 201)
        assert second_response.status_code == 200
        second_data = second_response.json()
        
        # Step 6: Verify updated_time is now set
        assert second_data["updatedTime"] is not None
        assert isinstance(second_data["updatedTime"], int)
        assert second_data["updatedTime"] > 0
        assert second_data["updatedTime"] > original_created_time
        
        # Step 7: GET the task and verify message_bubbles was updated
        get_response = api_client.get(f"/api/v1/sessions/{session_id}/chat-tasks")
        assert get_response.status_code == 200
        
        tasks = get_response.json()["tasks"]
        assert len(tasks) == 1
        
        retrieved_task = tasks[0]
        assert retrieved_task["taskId"] == task_id
        assert retrieved_task["messageBubbles"] == updated_bubbles
        assert retrieved_task["taskMetadata"] == updated_metadata
        
        # Verify the updated content
        bubbles = json.loads(retrieved_task["messageBubbles"])
        assert len(bubbles) == 3
        assert bubbles[2]["text"] == "Additional agent message"
        
        metadata = json.loads(retrieved_task["taskMetadata"])
        assert metadata["status"] == "completed"
        
        # Step 8: Verify created_time remained unchanged
        assert retrieved_task["createdTime"] == original_created_time
        assert retrieved_task["updatedTime"] is not None
        
        print(f"✓ Test 1.3 passed: Updated task {task_id} via upsert for session {session_id}")
