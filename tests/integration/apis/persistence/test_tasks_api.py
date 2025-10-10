"""
Tasks API tests using FastAPI HTTP endpoints.

Tests task submission and management through actual HTTP API calls to /tasks endpoints.
"""

import io

import pytest
from fastapi.testclient import TestClient


def test_send_non_streaming_task(api_client: TestClient):
    """Test POST /message:send for non-streaming task submission"""

    # Use the new A2A-compliant JSON-RPC format
    task_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-001",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-001",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Hello, please process this task"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    response = api_client.post("/api/v1/message:send", json=task_payload)

    assert response.status_code == 200
    response_data = response.json()

    # Verify JSONRPC response format
    assert "result" in response_data
    assert "id" in response_data["result"]
    assert response_data["result"]["id"] == "test-task-id"

    print("✓ Non-streaming task submitted successfully")


def test_send_streaming_task(api_client: TestClient):
    """Test POST /message:stream for streaming task submission"""

    # Use the new A2A-compliant JSON-RPC format
    task_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-002",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-002",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Start streaming conversation"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)

    assert response.status_code == 200
    response_data = response.json()

    # Verify JSONRPC response format
    assert "result" in response_data
    assert "id" in response_data["result"]
    assert "contextId" in response_data["result"]

    task_id = response_data["result"]["id"]
    session_id = response_data["result"]["contextId"]

    assert task_id == "test-task-id"
    assert session_id is not None
    assert len(session_id) > 0

    print(f"✓ Streaming task submitted with session {session_id}")


def test_send_task_with_small_file_inline(api_client: TestClient):
    """Test POST /message:stream with small file inline as base64 (< 1MB)"""
    import base64

    # Create a small test file (matches frontend behavior for files < 1MB)
    small_content = b"This is a small test file content that will be sent inline."
    base64_content = base64.b64encode(small_content).decode("utf-8")

    task_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-small-file",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-small-file",
                "kind": "message",
                "parts": [
                    {"kind": "text", "text": "Please process this small file"},
                    {
                        "kind": "file",
                        "file": {
                            "bytes": base64_content,
                            "name": "small_test.txt",
                            "mimeType": "text/plain",
                        },
                    },
                ],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)

    assert response.status_code == 200
    response_data = response.json()

    assert "result" in response_data
    assert "id" in response_data["result"]
    assert "contextId" in response_data["result"]

    print("✓ Small file sent inline successfully")


@pytest.mark.skip(reason="Session management changes in progress for artifact uploads")
def test_send_task_with_large_file_via_artifacts(api_client: TestClient):
    """Test POST /message:stream with large file uploaded via artifacts endpoint first (≥ 1MB)"""

    # Step 1: Create a session first (frontend creates session on-demand)
    initial_task_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-create-session",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-create-session",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Creating session for file upload"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    session_response = api_client.post(
        "/api/v1/message:stream", json=initial_task_payload
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["result"]["contextId"]

    # Step 2: Upload large file to artifacts endpoint (matches frontend for files ≥ 1MB)
    large_content = b"x" * (2 * 1024 * 1024)  # 2MB file
    files = {
        "upload_file": (
            "large_test.bin",
            io.BytesIO(large_content),
            "application/octet-stream",
        )
    }

    upload_response = api_client.post(
        f"/api/v1/artifacts/{session_id}/large_test.bin", files=files
    )
    assert upload_response.status_code == 201
    upload_result = upload_response.json()
    artifact_uri = upload_result["uri"]
    assert artifact_uri is not None

    # Step 3: Submit task with artifact URI reference
    task_with_artifact_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-large-file",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-large-file",
                "kind": "message",
                "parts": [
                    {"kind": "text", "text": "Please process this large file"},
                    {
                        "kind": "file",
                        "file": {
                            "uri": artifact_uri,
                            "name": "large_test.bin",
                            "mimeType": "application/octet-stream",
                        },
                    },
                ],
                "metadata": {"agent_name": "TestAgent"},
                "contextId": session_id,
            }
        },
    }

    response = api_client.post(
        "/api/v1/message:stream", json=task_with_artifact_payload
    )

    assert response.status_code == 200
    response_data = response.json()

    assert "result" in response_data
    assert "id" in response_data["result"]
    assert response_data["result"]["contextId"] == session_id

    print(f"✓ Large file uploaded via artifacts and referenced in task successfully")


def test_send_task_to_existing_session(api_client: TestClient):
    """Test sending task to existing session"""

    import uuid

    # First create a session
    initial_task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Initial message"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    initial_response = api_client.post(
        "/api/v1/message:stream", json=initial_task_payload
    )
    assert initial_response.status_code == 200
    session_id = initial_response.json()["result"]["contextId"]

    # Send follow-up task to same session
    followup_task_payload = {
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
                "contextId": session_id,  # Include session ID in message
            }
        },
    }

    followup_response = api_client.post(
        "/api/v1/message:stream", json=followup_task_payload
    )
    assert followup_response.status_code == 200

    # Should return same session ID
    assert followup_response.json()["result"]["contextId"] == session_id

    print(f"✓ Follow-up task sent to existing session {session_id}")


def test_cancel_task(api_client: TestClient):
    """Test POST /tasks/{taskId}:cancel for task cancellation"""

    # First submit a task
    task_payload = {
        "jsonrpc": "2.0",
        "id": "test-req-cancel",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-cancel",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Long running task to cancel"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200
    task_id = response.json()["result"]["id"]

    # Cancel the task using new endpoint format
    cancel_payload = {
        "jsonrpc": "2.0",
        "id": "test-cancel-req",
        "method": "tasks/cancel",
        "params": {
            "id": task_id,
        },
    }
    cancel_response = api_client.post(
        f"/api/v1/tasks/{task_id}:cancel", json=cancel_payload
    )

    assert cancel_response.status_code == 202  # Accepted
    cancel_result = cancel_response.json()

    assert "message" in cancel_result
    assert (
        "sent" in cancel_result["message"].lower()
        or "request" in cancel_result["message"].lower()
    )

    print(f"✓ Task {task_id} cancellation requested successfully")


def test_task_with_different_agents(api_client: TestClient):
    """Test sending tasks to different agents"""

    import uuid

    agents_and_messages = [
        ("TestAgent", "Task for main agent"),
        ("TestPeerAgentA", "Task for peer agent A"),
        ("TestPeerAgentB", "Task for peer agent B"),
    ]

    task_ids = []
    session_ids = []

    for i, (agent_name, message) in enumerate(agents_and_messages):
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": message}],
                    "metadata": {"agent_name": agent_name},
                }
            },
        }

        response = api_client.post("/api/v1/message:stream", json=task_payload)
        assert response.status_code == 200

        result = response.json()["result"]
        task_ids.append(result["id"])
        session_ids.append(result["contextId"])

    # Verify all tasks got unique sessions
    assert len(set(session_ids)) == len(session_ids)

    # Verify all tasks got the same mocked task ID (this is expected with our mock)
    assert all(task_id == "test-task-id" for task_id in task_ids)

    print(f"✓ Tasks sent to {len(agents_and_messages)} different agents")


def test_task_error_handling(api_client: TestClient):
    """Test error handling for invalid task requests"""

    # Test missing agent_name in metadata
    invalid_payload_1 = {
        "jsonrpc": "2.0",
        "id": "test-invalid-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-invalid-1",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Test"}],
                "metadata": {},  # Missing agent_name
            }
        },
    }
    response = api_client.post("/api/v1/message:send", json=invalid_payload_1)
    assert response.status_code in [400, 422]  # Validation error

    # Test missing message parts
    invalid_payload_2 = {
        "jsonrpc": "2.0",
        "id": "test-invalid-2",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-invalid-2",
                "kind": "message",
                "parts": [],  # Empty parts
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:send", json=invalid_payload_2)
    assert response.status_code in [200, 400, 422]  # May accept empty parts

    # Test empty body for cancellation
    import uuid

    cancel_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tasks/cancel",
        "params": {},  # Empty params
    }
    response = api_client.post("/api/v1/tasks/test-task-id:cancel", json=cancel_payload)
    assert response.status_code in [400, 422]  # Validation error

    print("✓ Task error handling works correctly")


def test_task_request_validation(api_client: TestClient):
    """Test request validation for task endpoints"""

    # Test empty agent name
    task_payload_1 = {
        "jsonrpc": "2.0",
        "id": "test-validation-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-validation-1",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Test message"}],
                "metadata": {"agent_name": ""},  # Empty agent name
            }
        },
    }
    response = api_client.post("/api/v1/message:send", json=task_payload_1)
    # Should either work with empty string or return validation error
    assert response.status_code in [200, 400, 422]

    # Test very long message
    long_message = "x" * 10000
    task_payload_2 = {
        "jsonrpc": "2.0",
        "id": "test-validation-2",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-validation-2",
                "kind": "message",
                "parts": [{"kind": "text", "text": long_message}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:send", json=task_payload_2)
    assert response.status_code == 200  # Should handle long messages

    print("✓ Task request validation working correctly")


def test_concurrent_task_submissions(api_client: TestClient):
    """Test multiple concurrent task submissions"""

    # Submit multiple tasks quickly
    responses = []
    for i in range(5):
        task_payload = {
            "jsonrpc": "2.0",
            "id": f"test-concurrent-{i}",
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": f"test-msg-concurrent-{i}",
                    "kind": "message",
                    "parts": [{"kind": "text", "text": f"Concurrent task {i}"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        responses.append(response)

    # Verify all succeeded
    for i, response in enumerate(responses):
        assert response.status_code == 200
        result = response.json()["result"]
        assert "id" in result
        assert "contextId" in result
        print(f"  ✓ Concurrent task {i} submitted: session {result['contextId']}")

    # Verify we got unique sessions for each task
    session_ids = [r.json()["result"]["contextId"] for r in responses]
    assert len(set(session_ids)) == len(session_ids)

    print("✓ Concurrent task submissions handled correctly")


@pytest.mark.parametrize(
    "agent_name", ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]
)
def test_tasks_for_individual_agents(api_client: TestClient, agent_name: str):
    """Test task submission for individual agents (parameterized)"""

    task_payload = {
        "jsonrpc": "2.0",
        "id": f"test-param-{agent_name}",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": f"test-msg-param-{agent_name}",
                "kind": "message",
                "parts": [{"kind": "text", "text": f"Task for {agent_name}"}],
                "metadata": {"agent_name": agent_name},
            }
        },
    }

    response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert response.status_code == 200

    result = response.json()["result"]
    assert "id" in result
    assert "contextId" in result

    session_id = result["contextId"]
    assert session_id is not None

    print(f"✓ Task submitted to {agent_name}: session {session_id}")


def test_task_and_session_integration(api_client: TestClient):
    """Test integration between tasks and sessions APIs"""

    # Submit a task (creates session)
    task_payload = {
        "jsonrpc": "2.0",
        "id": "test-integration",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": "test-msg-integration",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Integration test message"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }

    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    session_id = task_response.json()["result"]["contextId"]

    # Verify session appears in sessions list
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    assert len(sessions_data["data"]) >= 1
    session_ids = [s["id"] for s in sessions_data["data"]]
    assert session_id in session_ids

    # Verify session details
    session_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert session_response.status_code == 200

    # Verify message appears in session history
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    assert len(history) >= 1
    user_message = history[0]
    assert user_message["message"] == "Integration test message"

    print(f"✓ Task-session integration verified for session {session_id}")
