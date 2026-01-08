"""
Multi-agent database isolation tests.

Tests that verify each agent has its own isolated database and no data leakage occurs.
"""

import pytest

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.gateway_adapter import GatewayAdapter
from ..utils.persistence_assertions import (
    assert_agent_schema_correct,
    assert_database_isolation,
    assert_gateway_session_exists,
    assert_session_message_count,
)


def test_agent_database_complete_isolation(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that each agent has completely isolated database storage"""

    # Create sessions with different agents
    session_main = gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestAgent"
    )
    session_peer_a = gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestPeerAgentA"
    )
    session_peer_b = gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestPeerAgentB"
    )

    # Send messages to each agent
    gateway_adapter.send_message(session_main.id, "Message for TestAgent")
    gateway_adapter.send_message(session_peer_a.id, "Message for PeerAgentA")
    gateway_adapter.send_message(session_peer_b.id, "Message for PeerAgentB")

    # Verify database isolation between all agent pairs
    assert_database_isolation(database_inspector, "TestAgent", "TestPeerAgentA")
    assert_database_isolation(database_inspector, "TestAgent", "TestPeerAgentB")
    assert_database_isolation(database_inspector, "TestPeerAgentA", "TestPeerAgentB")


def test_gateway_to_agent_session_linking(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that Gateway sessions are properly linked to Agent sessions"""

    # Create session and send message
    session = gateway_adapter.create_session(
        user_id="linking_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(session.id, "Test message for linking")

    # Verify session exists in Gateway database
    assert_gateway_session_exists(
        database_inspector, session.id, "linking_user", "TestAgent"
    )

    # Verify messages were persisted
    assert_session_message_count(database_inspector, session.id, 2)


def test_agent_session_context_isolation(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that agent sessions maintain isolated contexts"""

    # Create two sessions for same agent but different contexts
    session_a = gateway_adapter.create_session(
        user_id="context_user", agent_name="TestAgent"
    )
    session_b = gateway_adapter.create_session(
        user_id="context_user", agent_name="TestAgent"
    )

    # Send different messages to establish different contexts
    gateway_adapter.send_message(session_a.id, "Working on context A task")
    gateway_adapter.send_message(session_b.id, "Working on context B task")

    # Verify session context isolation
    messages_a = database_inspector.get_session_messages(session_a.id)
    messages_b = database_inspector.get_session_messages(session_b.id)

    assert len(messages_a) == 2
    assert len(messages_b) == 2

    # Verify content is isolated
    assert "context A" in messages_a[0].user_message
    assert "context B" in messages_b[0].user_message
    assert "context A" not in messages_b[0].user_message
    assert "context B" not in messages_a[0].user_message


def test_cross_user_data_isolation(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that different users have completely isolated data"""

    # Create sessions for different users
    session_user_a = gateway_adapter.create_session(
        user_id="user_a", agent_name="TestAgent"
    )
    session_user_b = gateway_adapter.create_session(
        user_id="user_b", agent_name="TestAgent"
    )

    # Send messages as each user
    gateway_adapter.send_message(session_user_a.id, "User A private message")
    gateway_adapter.send_message(session_user_b.id, "User B private message")

    # Verify no data leakage between users
    user_a_sessions = database_inspector.get_gateway_sessions("user_a")
    user_b_sessions = database_inspector.get_gateway_sessions("user_b")

    assert len(user_a_sessions) == 1
    assert len(user_b_sessions) == 1
    assert user_a_sessions[0].id == session_user_a.id
    assert user_b_sessions[0].id == session_user_b.id

    # Verify message isolation
    messages_a = database_inspector.get_session_messages(session_user_a.id)
    messages_b = database_inspector.get_session_messages(session_user_b.id)

    assert "User A" in messages_a[0].user_message
    assert "User B" in messages_b[0].user_message
    assert "User B" not in messages_a[0].user_message
    assert "User A" not in messages_b[0].user_message


def test_agent_database_schema_isolation(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that each agent database has the same schema but separate data"""

    for agent_name in test_agents_list:
        assert_agent_schema_correct(database_inspector, agent_name)


@pytest.mark.parametrize(
    "agent_name", ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]
)
def test_individual_agent_isolation(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
    agent_name: str,
):
    """Test isolation for individual agents (parameterized)"""

    user_id = f"user_for_{agent_name.lower()}"
    session = gateway_adapter.create_session(user_id=user_id, agent_name=agent_name)
    gateway_adapter.send_message(session.id, f"Message for {agent_name}")

    # Verify this agent's session exists in Gateway database
    assert_gateway_session_exists(database_inspector, session.id, user_id, agent_name)

    # Verify messages exist
    assert_session_message_count(database_inspector, session.id, 2)
    messages = database_inspector.get_session_messages(session.id)
    assert agent_name in messages[0].user_message


def test_concurrent_agent_operations(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that operations on different agents maintain isolation"""

    # Create sessions for different agents
    session_main = gateway_adapter.create_session("concurrent_user", "TestAgent")
    session_peer_a = gateway_adapter.create_session("concurrent_user", "TestPeerAgentA")
    session_peer_b = gateway_adapter.create_session("concurrent_user", "TestPeerAgentB")

    sessions = [session_main, session_peer_a, session_peer_b]

    # Send messages to each session
    gateway_adapter.send_message(sessions[0].id, "Message to TestAgent")
    gateway_adapter.send_message(sessions[1].id, "Message to PeerAgentA")
    gateway_adapter.send_message(sessions[2].id, "Message to PeerAgentB")

    # Verify all operations completed correctly and maintained isolation
    for _i, session in enumerate(sessions):
        assert_session_message_count(database_inspector, session.id, 2)

    # Verify database isolation is still intact after operations
    assert_database_isolation(database_inspector, "TestAgent", "TestPeerAgentA")
    assert_database_isolation(database_inspector, "TestAgent", "TestPeerAgentB")
    assert_database_isolation(database_inspector, "TestPeerAgentA", "TestPeerAgentB")


def test_agent_message_content_isolation(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """Test that agent-specific message content is isolated"""

    # Create sessions for different agents with specific content
    agents_and_content = [
        ("TestAgent", "TestAgent specific content"),
        ("TestPeerAgentA", "PeerAgentA specific content"),
        ("TestPeerAgentB", "PeerAgentB specific content"),
    ]

    sessions = []
    for agent_name, content in agents_and_content:
        session = gateway_adapter.create_session(
            user_id="content_isolation_user", agent_name=agent_name
        )
        gateway_adapter.send_message(session.id, content)
        sessions.append((session, agent_name, content))

    # Verify each session only contains its own content
    for session, agent_name, expected_content in sessions:
        messages = database_inspector.get_session_messages(session.id)
        assert len(messages) == 2

        user_message = messages[0]
        assert user_message.user_message == expected_content

        # Verify other agents' content doesn't appear in this session
        for _other_session, other_agent, other_content in sessions:
            if other_agent != agent_name:
                assert other_content not in user_message.user_message
