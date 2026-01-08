"""
Tasks API tests using FastAPI HTTP endpoints.

Tests task submission and management through actual HTTP API calls to /tasks endpoints.
"""

import io

import pytest
from fastapi.testclient import TestClient

from ..infrastructure.gateway_adapter import GatewayAdapter


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
    task_id = response_data["result"]["id"]
    assert isinstance(task_id, str) and task_id.startswith("task-")

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

    assert isinstance(session_id, str) and session_id.startswith("test-session-")
    assert isinstance(task_id, str) and task_id.startswith("task-")

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


def test_send_task_with_large_file_via_artifacts(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test POST /message:stream with large file uploaded via artifacts endpoint first (≥ 1MB)"""

    # Step 1: Create a session using gateway_adapter (properly persists to database)
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    session_id = session.id

    # Step 2: Upload large file to artifacts endpoint (matches frontend for files ≥ 1MB)
    large_content = b"x" * (2 * 1024 * 1024)  # 2MB file
    files = {
        "upload_file": (
            "large_test.bin",
            io.BytesIO(large_content),
            "application/octet-stream",
        )
    }
    data = {
        "sessionId": session_id,
        "filename": "large_test.bin"
    }

    upload_response = api_client.post(
        "/api/v1/artifacts/upload",
        files=files,
        data=data
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

    print("✓ Large file uploaded via artifacts and referenced in task successfully")


def test_upload_artifact_with_session_management(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Test POST /artifacts/upload with automatic session creation and management"""

    # Test 1: Upload with null sessionId (should create new session)
    large_content = b"x" * (1024 * 1024)  # 1MB file
    files = {
        "upload_file": (
            "test_file.bin",
            io.BytesIO(large_content),
            "application/octet-stream",
        )
    }
    data = {
        "sessionId": "",  # Empty string triggers session creation
        "filename": "test_file.bin",
        "metadata_json": '{"description": "Test file upload"}',
    }

    upload_response = api_client.post(
        "/api/v1/artifacts/upload",
        files=files,
        data=data,
    )

    assert upload_response.status_code == 201
    upload_result = upload_response.json()

    # Verify response structure (camelCase due to Pydantic model)
    assert "uri" in upload_result
    assert "sessionId" in upload_result
    assert "filename" in upload_result
    assert "size" in upload_result
    assert "mimeType" in upload_result
    assert "metadata" in upload_result
    assert "createdAt" in upload_result

    # Verify values
    assert upload_result["filename"] == "test_file.bin"
    assert upload_result["size"] == len(large_content)
    assert upload_result["mimeType"] == "application/octet-stream"
    assert upload_result["metadata"]["description"] == "Test file upload"

    # Save session ID for next test
    created_session_id = upload_result["sessionId"]
    assert created_session_id is not None
    assert len(created_session_id) > 0

    print(f"✓ Artifact uploaded with auto-created session: {created_session_id}")

    # Test 2: Upload to existing session (use gateway_adapter to create a properly persisted session)
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    existing_session_id = session.id

    second_content = b"y" * (512 * 1024)  # 512KB file
    files2 = {
        "upload_file": (
            "second_file.txt",
            io.BytesIO(second_content),
            "text/plain",
        )
    }
    data2 = {
        "sessionId": existing_session_id,  # Use properly persisted session
        "filename": "second_file.txt",
    }

    upload_response2 = api_client.post(
        "/api/v1/artifacts/upload",
        files=files2,
        data=data2,
    )

    assert upload_response2.status_code == 201
    upload_result2 = upload_response2.json()

    # Verify it used the correct session
    assert upload_result2["sessionId"] == existing_session_id
    assert upload_result2["filename"] == "second_file.txt"
    assert upload_result2["size"] == len(second_content)
    assert upload_result2["mimeType"] == "text/plain"

    print(f"✓ Second artifact uploaded to existing session: {existing_session_id}")

    # Test 3: Upload with invalid filename (should fail)
    files3 = {
        "upload_file": (
            "../invalid.txt",
            io.BytesIO(b"test"),
            "text/plain",
        )
    }
    data3 = {
        "sessionId": existing_session_id,
        "filename": "../invalid.txt",  # Path traversal attempt
    }

    upload_response3 = api_client.post(
        "/api/v1/artifacts/upload",
        files=files3,
        data=data3,
    )

    assert upload_response3.status_code == 400
    error_detail = upload_response3.json()["detail"]
    assert "Invalid filename" in error_detail or "path" in error_detail.lower()

    print("✓ Invalid filename correctly rejected")

    # Test 4: Upload empty file (should fail)
    files4 = {
        "upload_file": (
            "empty.txt",
            io.BytesIO(b""),
            "text/plain",
        )
    }
    data4 = {
        "sessionId": existing_session_id,
        "filename": "empty.txt",
    }

    upload_response4 = api_client.post(
        "/api/v1/artifacts/upload",
        files=files4,
        data=data4,
    )

    assert upload_response4.status_code == 400
    error_detail4 = upload_response4.json()["detail"]
    assert "empty" in error_detail4.lower()

    print("✓ Empty file correctly rejected")
    print("✓ All upload_artifact_with_session tests passed")


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

    for _i, (agent_name, message) in enumerate(agents_and_messages):
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

    # Verify all tasks got unique IDs
    assert len(set(task_ids)) == len(task_ids)

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


@pytest.mark.xfail(reason="This test needs to be reviewed and fixed.")
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
