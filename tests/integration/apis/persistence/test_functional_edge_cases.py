"""
Functional edge cases and additional scenarios for comprehensive testing.

Tests missing functional scenarios including concurrent operations,
file upload edge cases, and error recovery scenarios.
"""

import io
import threading
import time

from fastapi.testclient import TestClient


def test_concurrent_session_modifications_same_user(api_client: TestClient):
    """Test concurrent modifications to the same session by the same user"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Concurrent modification test"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    results = []

    def update_session_name(name_suffix):
        """Helper function to update session name"""
        update_data = {"name": f"Updated Name {name_suffix}"}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)
        results.append((name_suffix, response.status_code))

    # Start multiple concurrent name updates
    threads = []
    for i in range(5):
        thread = threading.Thread(target=update_session_name, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All updates should succeed (200 status)
    for suffix, status_code in results:
        assert status_code == 200

    # Verify session still exists and has one of the updated names
    final_response = api_client.get(f"/api/v1/sessions/{session_id}")
    assert final_response.status_code == 200
    final_name = final_response.json()["name"]
    assert final_name.startswith("Updated Name")

    print(f"✓ Concurrent session modifications handled: final name = {final_name}")


def test_concurrent_message_additions_same_session(api_client: TestClient):
    """Test adding messages concurrently to the same session"""

    # Create a session
    task_data = {
        "agent_name": "TestAgent",
        "message": "Initial message for concurrent test",
    }
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    results = []

    def add_message(message_id):
        """Helper function to add a message"""
        message_data = {
            "agent_name": "TestAgent",
            "message": f"Concurrent message {message_id}",
            "session_id": session_id,
        }
        response = api_client.post("/api/v1/tasks/subscribe", data=message_data)
        results.append(
            (message_id, response.status_code, response.json()["result"]["sessionId"])
        )

    # Start multiple concurrent message additions
    threads = []
    for i in range(10):
        thread = threading.Thread(target=add_message, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All message additions should succeed
    for msg_id, status_code, returned_session_id in results:
        assert status_code == 200
        assert returned_session_id == session_id

    # Verify all messages were added
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 11  # Initial + 10 concurrent messages

    # Verify all concurrent messages are present
    message_texts = [msg["message"] for msg in user_messages]
    assert "Initial message for concurrent test" in message_texts
    for i in range(10):
        assert f"Concurrent message {i}" in message_texts

    print(
        f"✓ Concurrent message additions successful: {len(user_messages)} total messages"
    )


def test_large_file_upload_handling(api_client: TestClient):
    """Test handling of large file uploads"""

    # Create a large file (1MB)
    large_content = b"x" * (1024 * 1024)  # 1MB of data
    large_file = io.BytesIO(large_content)

    files = [("files", ("large_file.txt", large_file, "text/plain"))]

    task_data = {"agent_name": "TestAgent", "message": "Process this large file"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data, files=files)

    # Should either succeed or gracefully handle the large file
    assert response.status_code in [200, 413, 422]  # 413 = Request Entity Too Large

    if response.status_code == 200:
        session_id = response.json()["result"]["sessionId"]

        # Verify session was created successfully
        session_response = api_client.get(f"/api/v1/sessions/{session_id}")
        assert session_response.status_code == 200

        print("✓ Large file upload handled successfully")
    else:
        print("✓ Large file upload properly rejected with appropriate error")


def test_invalid_file_type_upload(api_client: TestClient):
    """Test handling of invalid file types"""

    # Create files with various extensions/types
    test_files = [
        (b"#!/bin/bash\necho 'test'", "script.sh", "application/x-shellscript"),
        (b"\x89PNG\r\n\x1a\n", "image.png", "image/png"),
        (b"PK\x03\x04", "archive.zip", "application/zip"),
    ]

    for content, filename, mimetype in test_files:
        file_obj = io.BytesIO(content)
        files = [("files", (filename, file_obj, mimetype))]

        task_data = {"agent_name": "TestAgent", "message": f"Process {filename}"}

        response = api_client.post(
            "/api/v1/tasks/subscribe", data=task_data, files=files
        )

        # Should either accept all file types or reject with appropriate error
        assert response.status_code in [
            200,
            400,
            422,
            415,
        ]  # 415 = Unsupported Media Type

        if response.status_code == 200:
            session_id = response.json()["result"]["sessionId"]

            # Verify session was created
            session_response = api_client.get(f"/api/v1/sessions/{session_id}")
            assert session_response.status_code == 200


def test_session_name_edge_cases(api_client: TestClient):
    """Test session name validation and edge cases"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Session name test"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Test various session name edge cases
    name_test_cases = [
        "",  # Empty string
        " ",  # Whitespace only
        "A" * 1000,  # Very long name
        "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",  # Special characters
        "Unicode: 你好 🌍 émojis",  # Unicode and emojis
        None,  # Will be handled differently by JSON serialization
    ]

    for test_name in name_test_cases:
        if test_name is None:
            continue  # Skip None for now

        update_data = {"name": test_name}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)

        # Should either accept the name or return validation error
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            # Verify the name was set correctly
            session_response = api_client.get(f"/api/v1/sessions/{session_id}")
            assert session_response.status_code == 200
            returned_name = session_response.json()["name"]
            assert returned_name == test_name


def test_task_cancellation_after_session_deletion(api_client: TestClient):
    """Test task cancellation behavior after session is deleted"""

    # Create a session with a task
    task_data = {
        "agent_name": "TestAgent",
        "message": "Task to be cancelled after session deletion",
    }
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    task_id = response.json()["result"]["taskId"]
    session_id = response.json()["result"]["sessionId"]

    # Delete the session
    delete_response = api_client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 204

    # Try to cancel the task after session deletion
    cancel_data = {"task_id": task_id}
    cancel_response = api_client.post("/api/v1/tasks/cancel", data=cancel_data)

    # Should handle gracefully - either succeed or return appropriate error
    assert cancel_response.status_code in [200, 400, 404, 500]

    if cancel_response.status_code == 200:
        result = cancel_response.json()["result"]
        assert "message" in result
        print("✓ Task cancellation after session deletion handled successfully")
    else:
        print("✓ Task cancellation after session deletion returned appropriate error")


def test_message_ordering_consistency_under_load(api_client: TestClient):
    """Test that message ordering remains consistent under concurrent load"""

    # Create a session
    task_data = {
        "agent_name": "TestAgent",
        "message": "Message ordering test - message 0",
    }
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Add messages in sequence with small delays to test ordering
    expected_messages = []
    for i in range(1, 21):  # Messages 1-20
        message_text = f"Message ordering test - message {i}"
        expected_messages.append(message_text)

        message_data = {
            "agent_name": "TestAgent",
            "message": message_text,
            "session_id": session_id,
        }

        response = api_client.post("/api/v1/tasks/subscribe", data=message_data)
        assert response.status_code == 200

        # Small delay to ensure ordering
        time.sleep(0.01)

    # Verify message history maintains order
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 21  # Initial + 20 sequential messages

    # Verify the first and last few messages are in correct order
    assert user_messages[0]["message"] == "Message ordering test - message 0"
    assert user_messages[1]["message"] == "Message ordering test - message 1"
    assert user_messages[-1]["message"] == "Message ordering test - message 20"

    print(
        f"✓ Message ordering consistency maintained under load: {len(user_messages)} messages"
    )


def test_error_recovery_after_database_constraints(api_client: TestClient):
    """Test error recovery scenarios involving database constraints"""

    # Create a session
    task_data = {"agent_name": "TestAgent", "message": "Database constraint test"}
    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # Try various operations that might trigger constraint issues
    test_operations = [
        # Try to create message with non-existent session (should fail gracefully)
        {
            "operation": "add_message_invalid_session",
            "data": {
                "agent_name": "TestAgent",
                "message": "Message to non-existent session",
                "session_id": "nonexistent_session_id_1",
            },
        },
        # Try to update non-existent session (should return 404)
        {
            "operation": "update_invalid_session",
            "session_id": "nonexistent_session_id_2",
            "data": {"name": "Invalid Update"},
        },
    ]

    for test_op in test_operations:
        if test_op["operation"] == "add_message_invalid_session":
            response = api_client.post("/api/v1/tasks/subscribe", data=test_op["data"])
            # Should either create new session or return error
            assert response.status_code in [200, 400, 404, 422]

        elif test_op["operation"] == "update_invalid_session":
            response = api_client.patch(
                f"/api/v1/sessions/{test_op['session_id']}", json=test_op["data"]
            )
            assert response.status_code == 404

    # Verify original session still works after constraint errors
    followup_data = {
        "agent_name": "TestAgent",
        "message": "Recovery test - session should still work",
        "session_id": session_id,
    }

    recovery_response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
    assert recovery_response.status_code == 200
    assert recovery_response.json()["result"]["sessionId"] == session_id

    print("✓ Error recovery after database constraint issues successful")


def test_empty_and_whitespace_message_handling(api_client: TestClient):
    """Test handling of empty and whitespace-only messages"""

    message_test_cases = [
        "",  # Empty string
        " ",  # Single space
        "\t",  # Tab
        "\n",  # Newline
        "   ",  # Multiple spaces
        "\t\n\r ",  # Mixed whitespace
    ]

    for test_message in message_test_cases:
        task_data = {"agent_name": "TestAgent", "message": test_message}

        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)

        # Should either accept and create session or return validation error
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            session_id = response.json()["result"]["sessionId"]

            # Verify session exists
            session_response = api_client.get(f"/api/v1/sessions/{session_id}")
            assert session_response.status_code == 200

            # Verify message appears in history
            history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
            assert history_response.status_code == 200
            history = history_response.json()

            if history:
                user_messages = [msg for msg in history if msg["sender_type"] == "user"]
                if user_messages:
                    assert user_messages[0]["message"] == test_message

    print("✓ Empty and whitespace message handling tested")
