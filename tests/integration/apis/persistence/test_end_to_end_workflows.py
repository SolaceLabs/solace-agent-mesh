"""
End-to-end user workflow tests for the persistence framework.
"""

from fastapi.testclient import TestClient

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter


def test_complete_user_conversation_workflow(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test a complete user conversation workflow from start to finish."""
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    gateway_adapter.send_message(session.id, "Hello, I need help with data analysis")
    gateway_adapter.send_message(
        session.id, "Can you explain the process step by step?"
    )
    gateway_adapter.send_message(session.id, "What tools would you recommend?")
    gateway_adapter.send_message(session.id, "How long would this typically take?")

    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) == 8

    update_data = {"name": "Data Analysis Help Session"}
    update_response = api_client.patch(
        f"/api/v1/sessions/{session.id}", json=update_data
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Data Analysis Help Session"

    sessions = gateway_adapter.list_sessions("sam_dev_user")
    assert len(sessions) > 0
    target_session = next((s for s in sessions if s.id == session.id), None)
    assert target_session is not None
    assert target_session.name == "Data Analysis Help Session"


def test_multi_agent_consultation_workflow(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test workflow where user consults multiple agents."""
    consultations = [
        ("TestAgent", "I need help with project planning"),
        ("TestPeerAgentA", "Can you help with data analysis?"),
        ("TestPeerAgentB", "I need assistance with reporting"),
    ]

    sessions = []
    for agent_name, initial_message in consultations:
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name=agent_name
        )
        gateway_adapter.send_message(session.id, initial_message)
        sessions.append(session)

    all_sessions = database_inspector.get_gateway_sessions("sam_dev_user")
    assert len(all_sessions) >= len(consultations)

    for session, (agent_name, initial_message) in zip(
        sessions, consultations, strict=False
    ):
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 2
        assert messages[0].user_message == initial_message


def test_document_processing_workflow(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test workflow involving file upload and processing"""
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(
        session.id, "Please analyze these documents and provide a summary"
    )
    gateway_adapter.send_message(
        session.id, "What are the key themes in these documents?"
    )

    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) == 4
    assert "documents" in messages[0].user_message


def test_session_management_workflow(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test comprehensive session management operations."""
    session_configs = [
        ("TestAgent", "API Help"),
        ("TestPeerAgentA", "Data Viz Consultation"),
        ("TestAgent", "API Follow-up"),
        ("TestPeerAgentB", "Report Help"),
    ]

    created_sessions = []
    for agent_name, name in session_configs:
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name=agent_name
        )
        update_data = {"name": name}
        response = api_client.patch(f"/api/v1/sessions/{session.id}", json=update_data)
        assert response.status_code == 200
        created_sessions.append(response.json())

    all_sessions = gateway_adapter.list_sessions("sam_dev_user")
    assert len(all_sessions) >= len(session_configs)

    sessions_to_delete = all_sessions[:2]
    for session in sessions_to_delete:
        response = api_client.delete(f"/api/v1/sessions/{session.id}")
        assert response.status_code == 204

    remaining_sessions = gateway_adapter.list_sessions("sam_dev_user")
    assert len(remaining_sessions) >= len(session_configs) - 2
    remaining_ids = {s.id for s in remaining_sessions}
    for deleted_session in sessions_to_delete:
        assert deleted_session.id not in remaining_ids


def test_error_recovery_workflow(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test workflow that handles various error conditions gracefully"""
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(session.id, "Normal conversation start")

    # Try to access non-existent session
    response = api_client.get("/api/v1/sessions/nonexistent_session")
    assert response.status_code == 404

    # Verify original session still works
    gateway_adapter.send_message(session.id, "Follow-up after errors")
    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) == 4
    assert "Follow-up after errors" in messages[2].user_message


def test_high_volume_workflow(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test workflow with high volume of API calls"""
    sessions = []
    for _i in range(10):
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        sessions.append(session)

    for session in sessions:
        for j in range(3):
            gateway_adapter.send_message(session.id, f"Message {j} to session")

    all_sessions = database_inspector.get_gateway_sessions("sam_dev_user")
    assert len(all_sessions) >= 10

    for session in sessions:
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 6
