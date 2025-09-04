"""
Multi-agent database isolation tests.

Tests that verify each agent has its own isolated database and no data leakage occurs.
"""

import pytest

from ..infrastructure.simple_database_inspector import SimpleDatabaseInspector
from ..infrastructure.simple_gateway_adapter import SimpleGatewayAdapter


def test_agent_database_complete_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that each agent has completely isolated database storage"""

    # Create sessions with different agents
    session_main = simple_gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestAgent"
    )

    session_peer_a = simple_gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestPeerAgentA"
    )

    session_peer_b = simple_gateway_adapter.create_session(
        user_id="isolation_user", agent_name="TestPeerAgentB"
    )

    # Send messages to each agent
    simple_gateway_adapter.send_message(session_main.id, "Message for TestAgent")

    simple_gateway_adapter.send_message(session_peer_a.id, "Message for PeerAgentA")

    simple_gateway_adapter.send_message(session_peer_b.id, "Message for PeerAgentB")

    # Verify database isolation between all agent pairs
    assert simple_database_inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentA"
    )
    assert simple_database_inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentB"
    )
    assert simple_database_inspector.verify_database_isolation(
        "TestPeerAgentA", "TestPeerAgentB"
    )

    print("✓ Complete database isolation verified between all agents")


def test_gateway_to_agent_session_linking(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that Gateway sessions are properly linked to Agent sessions"""

    # Create session and send message
    session = simple_gateway_adapter.create_session(
        user_id="linking_user", agent_name="TestAgent"
    )

    simple_gateway_adapter.send_message(session.id, "Test message for linking")

    # Verify session exists in Gateway database
    gateway_sessions = simple_database_inspector.get_gateway_sessions("linking_user")
    assert len(gateway_sessions) == 1
    assert gateway_sessions[0].id == session.id
    assert gateway_sessions[0].agent_name == "TestAgent"

    # Verify messages were persisted
    messages = simple_database_inspector.get_session_messages(session.id)
    assert len(messages) == 2  # user message + agent response

    print(f"✓ Session linking verified: Gateway session for {session.id}")


def test_agent_session_context_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that agent sessions maintain isolated contexts"""

    # Create two sessions for same agent but different contexts
    session_a = simple_gateway_adapter.create_session(
        user_id="context_user", agent_name="TestAgent"
    )

    session_b = simple_gateway_adapter.create_session(
        user_id="context_user", agent_name="TestAgent"
    )

    # Send different messages to establish different contexts
    simple_gateway_adapter.send_message(session_a.id, "Working on context A task")

    simple_gateway_adapter.send_message(session_b.id, "Working on context B task")

    # Verify session context isolation
    messages_a = simple_database_inspector.get_session_messages(session_a.id)
    messages_b = simple_database_inspector.get_session_messages(session_b.id)

    # Both sessions should have 2 messages each
    assert len(messages_a) == 2
    assert len(messages_b) == 2

    # Verify content is isolated
    assert "context A" in messages_a[0].content
    assert "context B" in messages_b[0].content
    assert "context A" not in messages_b[0].content
    assert "context B" not in messages_a[0].content

    print(
        f"✓ Agent session context isolation verified: {session_a.id} ≠ {session_b.id}"
    )


def test_cross_user_data_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that different users have completely isolated data"""

    # Create sessions for different users
    session_user_a = simple_gateway_adapter.create_session(
        user_id="user_a", agent_name="TestAgent"
    )

    session_user_b = simple_gateway_adapter.create_session(
        user_id="user_b", agent_name="TestAgent"
    )

    # Send messages as each user
    simple_gateway_adapter.send_message(session_user_a.id, "User A private message")

    simple_gateway_adapter.send_message(session_user_b.id, "User B private message")

    # Verify no data leakage between users
    user_a_sessions = simple_database_inspector.get_gateway_sessions("user_a")
    user_b_sessions = simple_database_inspector.get_gateway_sessions("user_b")

    # Each user should only see their own sessions
    assert len(user_a_sessions) == 1
    assert len(user_b_sessions) == 1
    assert user_a_sessions[0].id == session_user_a.id
    assert user_b_sessions[0].id == session_user_b.id

    # Verify message isolation
    messages_a = simple_database_inspector.get_session_messages(session_user_a.id)
    messages_b = simple_database_inspector.get_session_messages(session_user_b.id)

    assert "User A" in messages_a[0].content
    assert "User B" in messages_b[0].content
    assert "User B" not in messages_a[0].content
    assert "User A" not in messages_b[0].content

    print("✓ Cross-user data isolation verified")


def test_agent_database_schema_isolation(
    simple_database_inspector: SimpleDatabaseInspector, test_agents_list: list[str]
):
    """Test that each agent database has the same schema but separate data"""

    # Verify each agent has the expected schema
    expected_tables = ["agent_sessions", "agent_messages"]

    for agent_name in test_agents_list:
        table_names = simple_database_inspector.verify_agent_schema_state(agent_name)

        for expected_table in expected_tables:
            assert expected_table in table_names, (
                f"Agent {agent_name} missing table {expected_table}"
            )

        # Verify no migration table (direct schema)
        assert "alembic_version" not in table_names, (
            f"Agent {agent_name} should not have migration table"
        )

    print(
        f"✓ Schema isolation verified: {len(test_agents_list)} agents have identical schemas"
    )


@pytest.mark.parametrize(
    "agent_name", ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]
)
def test_individual_agent_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
    agent_name: str,
):
    """Test isolation for individual agents (parameterized)"""

    # Create session for this specific agent
    session = simple_gateway_adapter.create_session(
        user_id=f"user_for_{agent_name.lower()}", agent_name=agent_name
    )

    simple_gateway_adapter.send_message(session.id, f"Message for {agent_name}")

    # Verify this agent's session exists in Gateway database
    user_sessions = simple_database_inspector.get_gateway_sessions(
        f"user_for_{agent_name.lower()}"
    )
    assert len(user_sessions) == 1, f"Expected 1 session for {agent_name}"
    assert user_sessions[0].agent_name == agent_name

    # Verify messages exist
    messages = simple_database_inspector.get_session_messages(session.id)
    assert len(messages) == 2  # user message + agent response
    assert agent_name in messages[0].content

    print(f"✓ Individual agent isolation verified: {agent_name}")


def test_concurrent_agent_operations(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that operations on different agents maintain isolation"""

    # Create sessions for different agents
    session_main = simple_gateway_adapter.create_session("concurrent_user", "TestAgent")
    session_peer_a = simple_gateway_adapter.create_session(
        "concurrent_user", "TestPeerAgentA"
    )
    session_peer_b = simple_gateway_adapter.create_session(
        "concurrent_user", "TestPeerAgentB"
    )

    sessions = [session_main, session_peer_a, session_peer_b]

    # Send messages to each session
    simple_gateway_adapter.send_message(sessions[0].id, "Message to TestAgent")
    simple_gateway_adapter.send_message(sessions[1].id, "Message to PeerAgentA")
    simple_gateway_adapter.send_message(sessions[2].id, "Message to PeerAgentB")

    # Verify all operations completed correctly and maintained isolation
    for i, session in enumerate(sessions):
        # Each session should have 2 messages (user + agent)
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 2, f"Session {i} should have 2 messages"

    # Verify database isolation is still intact after operations
    assert simple_database_inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentA"
    )
    assert simple_database_inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentB"
    )
    assert simple_database_inspector.verify_database_isolation(
        "TestPeerAgentA", "TestPeerAgentB"
    )

    print("✓ Concurrent agent operations maintain isolation")


def test_agent_message_content_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
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
        session = simple_gateway_adapter.create_session(
            user_id="content_isolation_user", agent_name=agent_name
        )
        simple_gateway_adapter.send_message(session.id, content)
        sessions.append((session, agent_name, content))

    # Verify each session only contains its own content
    for session, agent_name, expected_content in sessions:
        messages = simple_database_inspector.get_session_messages(session.id)
        assert len(messages) == 2  # user + agent message

        user_message = messages[0]
        assert user_message.content == expected_content

        # Verify other agents' content doesn't appear in this session
        for other_session, other_agent, other_content in sessions:
            if other_agent != agent_name:
                assert other_content not in user_message.content

    print("✓ Agent message content isolation verified")
