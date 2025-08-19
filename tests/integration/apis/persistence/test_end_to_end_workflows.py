"""
End-to-end user workflow tests using FastAPI HTTP endpoints.

Tests complete user journeys that span multiple API endpoints and operations.
"""

import io

from fastapi.testclient import TestClient


def test_complete_user_conversation_workflow(api_client: TestClient):
    """Test a complete user conversation workflow from start to finish"""

    # 1. Start a new conversation
    print("1. Starting new conversation...")
    task_data = {
        "agent_name": "TestAgent",
        "message": "Hello, I need help with data analysis",
    }

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # 2. Continue the conversation with follow-up questions
    print("2. Sending follow-up messages...")
    followup_messages = [
        "Can you explain the process step by step?",
        "What tools would you recommend?",
        "How long would this typically take?",
    ]

    for message in followup_messages:
        followup_data = {
            "agent_name": "TestAgent",
            "message": message,
            "session_id": session_id,
        }
        response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
        assert response.status_code == 200
        assert response.json()["result"]["sessionId"] == session_id

    # 3. Check conversation history
    print("3. Checking conversation history...")
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    # Should have original message + 3 follow-ups = 4 user messages minimum
    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 4

    # Verify messages are in order
    expected_messages = [
        "Hello, I need help with data analysis",
        "Can you explain the process step by step?",
        "What tools would you recommend?",
        "How long would this typically take?",
    ]

    for i, expected_msg in enumerate(expected_messages):
        assert user_messages[i]["message"] == expected_msg

    # 4. Rename the conversation
    print("4. Renaming conversation...")
    update_data = {"name": "Data Analysis Help Session"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session_id}", json=update_data
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Data Analysis Help Session"

    # 5. Verify session appears in user's session list with correct name
    print("5. Verifying session list...")
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    target_session = next(s for s in sessions_data["sessions"] if s["id"] == session_id)
    assert target_session["name"] == "Data Analysis Help Session"
    assert target_session["agent_id"] == "TestAgent"

    print(f"✓ Complete conversation workflow successful for session {session_id}")


def test_multi_agent_consultation_workflow(api_client: TestClient):
    """Test workflow where user consults multiple agents for different expertise"""

    # User starts conversations with different agents for different topics
    agent_consultations = [
        ("TestAgent", "I need help with project planning"),
        ("TestPeerAgentA", "Can you help with data analysis?"),
        ("TestPeerAgentB", "I need assistance with reporting"),
    ]

    session_ids = []

    # 1. Start consultations with each agent
    print("1. Starting consultations with multiple agents...")
    for agent_name, initial_message in agent_consultations:
        task_data = {"agent_name": agent_name, "message": initial_message}

        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["sessionId"]
        session_ids.append(session_id)

        print(f"  ✓ Started session {session_id} with {agent_name}")

    # 2. Send follow-up questions to each agent
    print("2. Sending follow-up questions...")
    followup_questions = [
        "What's the first step I should take?",
        "How long will this process take?",
        "What resources do I need?",
    ]

    for session_id, (agent_name, _) in zip(
        session_ids, agent_consultations, strict=False
    ):
        for question in followup_questions:
            followup_data = {
                "agent_name": agent_name,
                "message": question,
                "session_id": session_id,
            }

            response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
            assert response.status_code == 200

    # 3. Verify all sessions are separate and contain correct conversations
    print("3. Verifying session isolation...")
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    # Should have 3 sessions for 3 different agents
    assert len(sessions_data["sessions"]) >= 3

    for session_id, (agent_name, initial_message) in zip(
        session_ids, agent_consultations, strict=False
    ):
        # Verify session metadata
        session = next(s for s in sessions_data["sessions"] if s["id"] == session_id)
        assert session["agent_id"] == agent_name

        # Verify conversation history
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200
        history = history_response.json()

        user_messages = [msg for msg in history if msg["sender_type"] == "user"]
        assert len(user_messages) >= 4  # initial + 3 follow-ups
        assert user_messages[0]["message"] == initial_message

    # 4. Name each session appropriately
    print("4. Naming sessions...")
    session_names = [
        "Project Planning Discussion",
        "Data Analysis Consultation",
        "Reporting Assistance",
    ]

    for session_id, name in zip(session_ids, session_names, strict=False):
        update_data = {"name": name}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)
        assert response.status_code == 200

    print("✓ Multi-agent consultation workflow successful")


def test_document_processing_workflow(api_client: TestClient):
    """Test workflow involving file upload and processing"""

    # 1. Upload documents for processing
    print("1. Uploading documents for processing...")

    # Create mock documents
    doc1_content = b"# Project Requirements\n\nThis document outlines the key requirements for our new project..."
    doc2_content = (
        b"# Data Analysis Report\n\nSummary of findings from recent data analysis..."
    )

    files = [
        ("files", ("requirements.md", io.BytesIO(doc1_content), "text/markdown")),
        ("files", ("analysis.md", io.BytesIO(doc2_content), "text/markdown")),
    ]

    task_data = {
        "agent_name": "TestAgent",
        "message": "Please analyze these documents and provide a summary",
    }

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data, files=files)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # 2. Ask follow-up questions about the documents
    print("2. Asking follow-up questions...")
    followup_questions = [
        "What are the key themes in these documents?",
        "Are there any inconsistencies between the documents?",
        "What actions would you recommend based on these documents?",
    ]

    for question in followup_questions:
        followup_data = {
            "agent_name": "TestAgent",
            "message": question,
            "session_id": session_id,
        }

        response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
        assert response.status_code == 200

    # 3. Verify conversation history includes file-related discussion
    print("3. Verifying conversation history...")
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 4  # initial + 3 follow-ups

    # First message should mention documents
    assert "documents" in user_messages[0]["message"].lower()

    # 4. Name the session appropriately
    print("4. Naming document processing session...")
    update_data = {"name": "Document Analysis Session"}
    response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)
    assert response.status_code == 200

    print(f"✓ Document processing workflow successful for session {session_id}")


def test_session_management_workflow(api_client: TestClient):
    """Test comprehensive session management operations"""

    # 1. Create multiple sessions over time
    print("1. Creating multiple sessions...")
    sessions_created = []

    session_configs = [
        ("TestAgent", "Quick question about APIs", "API Help"),
        ("TestPeerAgentA", "Need data visualization advice", "Data Viz Consultation"),
        ("TestAgent", "Follow-up on previous API discussion", "API Follow-up"),
        ("TestPeerAgentB", "Report generation assistance", "Report Help"),
    ]

    for agent_name, message, intended_name in session_configs:
        task_data = {"agent_name": agent_name, "message": message}

        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["sessionId"]

        sessions_created.append(
            {"id": session_id, "agent": agent_name, "name": intended_name}
        )

    # 2. Name all sessions
    print("2. Naming all sessions...")
    for session in sessions_created:
        update_data = {"name": session["name"]}
        response = api_client.patch(
            f"/api/v1/sessions/{session['id']}", json=update_data
        )
        assert response.status_code == 200

    # 3. Verify all sessions appear in list with correct names
    print("3. Verifying session list...")
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    assert len(sessions_data["sessions"]) >= len(sessions_created)

    for created_session in sessions_created:
        found_session = next(
            s for s in sessions_data["sessions"] if s["id"] == created_session["id"]
        )
        assert found_session["name"] == created_session["name"]
        assert found_session["agent_id"] == created_session["agent"]

    # 4. Delete some sessions (simulate cleanup)
    print("4. Cleaning up old sessions...")
    sessions_to_delete = sessions_created[:2]  # Delete first 2 sessions

    for session in sessions_to_delete:
        response = api_client.delete(f"/api/v1/sessions/{session['id']}")
        assert response.status_code == 204

    # 5. Verify deleted sessions are gone
    print("5. Verifying deleted sessions are gone...")
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    remaining_sessions = sessions_response.json()

    remaining_ids = {s["id"] for s in remaining_sessions["sessions"]}
    for deleted_session in sessions_to_delete:
        assert deleted_session["id"] not in remaining_ids

    # Verify remaining sessions are still there
    for kept_session in sessions_created[2:]:
        assert kept_session["id"] in remaining_ids

    print("✓ Session management workflow successful")


def test_error_recovery_workflow(api_client: TestClient):
    """Test workflow that handles various error conditions gracefully"""

    # 1. Start a normal conversation
    print("1. Starting normal conversation...")
    task_data = {"agent_name": "TestAgent", "message": "Normal conversation start"}

    response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
    assert response.status_code == 200
    session_id = response.json()["result"]["sessionId"]

    # 2. Try various error conditions and verify graceful handling
    print("2. Testing error conditions...")

    # Try to access non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session")
    assert response.status_code == 404

    # Try to send task with invalid data
    response = api_client.post("/api/v1/tasks/send", data={})
    assert response.status_code == 422

    # Try to cancel non-existent task
    response = api_client.post("/api/v1/tasks/cancel", data={"task_id": "nonexistent"})
    assert response.status_code in [
        400,
        422,
        500,
    ]  # Various error responses are acceptable

    # 3. Verify original session still works after errors
    print("3. Verifying original session still works...")
    followup_data = {
        "agent_name": "TestAgent",
        "message": "Follow-up after errors",
        "session_id": session_id,
    }

    response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
    assert response.status_code == 200
    assert response.json()["result"]["sessionId"] == session_id

    # 4. Verify session history is intact
    print("4. Verifying session history is intact...")
    history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()

    user_messages = [msg for msg in history if msg["sender_type"] == "user"]
    assert len(user_messages) >= 2
    assert user_messages[0]["message"] == "Normal conversation start"
    assert user_messages[-1]["message"] == "Follow-up after errors"

    print("✓ Error recovery workflow successful")


def test_high_volume_workflow(api_client: TestClient):
    """Test workflow with high volume of API calls"""

    print("1. Creating multiple concurrent sessions...")

    # Create many sessions quickly
    session_ids = []
    for i in range(10):
        task_data = {
            "agent_name": "TestAgent",
            "message": f"Batch session {i} - testing high volume",
        }

        response = api_client.post("/api/v1/tasks/subscribe", data=task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["sessionId"]
        session_ids.append(session_id)

    print(f"2. Created {len(session_ids)} sessions")

    # Send multiple messages to each session
    print("3. Sending multiple messages to each session...")
    for session_id in session_ids:
        for j in range(3):
            followup_data = {
                "agent_name": "TestAgent",
                "message": f"Message {j} to session",
                "session_id": session_id,
            }

            response = api_client.post("/api/v1/tasks/subscribe", data=followup_data)
            assert response.status_code == 200

    # Verify all sessions exist and have correct message counts
    print("4. Verifying all sessions and messages...")
    sessions_response = api_client.get("/api/v1/sessions")
    assert sessions_response.status_code == 200
    sessions_data = sessions_response.json()

    # Should have at least our created sessions
    assert len(sessions_data["sessions"]) >= len(session_ids)

    # Verify each session has the expected number of messages
    for session_id in session_ids:
        history_response = api_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert history_response.status_code == 200
        history = history_response.json()

        user_messages = [msg for msg in history if msg["sender_type"] == "user"]
        assert len(user_messages) >= 4  # Initial + 3 follow-ups

    print(
        f"✓ High volume workflow successful: {len(session_ids)} sessions with {len(session_ids) * 4} total messages"
    )
