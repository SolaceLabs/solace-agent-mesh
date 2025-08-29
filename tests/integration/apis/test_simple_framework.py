"""
Simple smoke tests for the API persistence testing framework.

Basic tests to verify that the simplified framework works without external dependencies.
"""

import pytest

from .infrastructure.simple_database_inspector import SimpleDatabaseInspector
from .infrastructure.simple_database_manager import SimpleDatabaseManager
from .infrastructure.simple_gateway_adapter import SimpleGatewayAdapter


def test_simple_database_manager_initialization(
    simple_database_manager: SimpleDatabaseManager,
):
    """Test that SimpleDatabaseManager initializes correctly"""

    # Verify Gateway database path exists
    assert simple_database_manager.gateway_db_path is not None
    assert simple_database_manager.gateway_db_path.exists()

    # Verify Agent database paths exist
    expected_agents = [
        "TestAgent",
        "TestPeerAgentA",
        "TestPeerAgentB",
        "TestPeerAgentC",
    ]
    assert len(simple_database_manager.agent_db_paths) == len(expected_agents)

    for agent_name in expected_agents:
        assert agent_name in simple_database_manager.agent_db_paths
        agent_path = simple_database_manager.agent_db_paths[agent_name]
        assert agent_path.exists()
        assert agent_name.lower() in str(agent_path)

    print(
        f"✓ SimpleDatabaseManager initialized: Gateway + {len(expected_agents)} agents"
    )


def test_database_connections(simple_database_manager: SimpleDatabaseManager):
    """Test that database connections work"""

    # Test Gateway connection
    with simple_database_manager.get_gateway_connection() as gateway_conn:
        cursor = gateway_conn.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

    # Test Agent connections
    for agent_name in simple_database_manager.agent_db_paths.keys():
        with simple_database_manager.get_agent_connection(agent_name) as agent_conn:
            cursor = agent_conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    print("✓ All database connections working")


def test_simple_database_inspector_basic(
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that SimpleDatabaseInspector works"""

    # Test Gateway migration verification
    migration_version = simple_database_inspector.verify_gateway_migration_state()
    assert migration_version is not None
    assert len(migration_version) > 0
    assert migration_version == "test_migration_001"

    # Test Agent schema verification
    for agent_name in ["TestAgent", "TestPeerAgentA"]:
        table_names = simple_database_inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names

    print("✓ SimpleDatabaseInspector basic functionality working")


def test_simple_gateway_adapter_basic(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that SimpleGatewayAdapter basic functionality works"""

    # Test session creation
    session = simple_gateway_adapter.create_session(
        user_id="smoke_test_user", agent_name="TestAgent"
    )

    assert session.id is not None
    assert len(session.id) > 0
    assert session.user_id == "smoke_test_user"
    assert session.agent_name == "TestAgent"

    # Verify session was persisted
    gateway_sessions = simple_database_inspector.get_gateway_sessions("smoke_test_user")
    assert len(gateway_sessions) == 1
    assert gateway_sessions[0].id == session.id

    # Test session listing
    session_list = simple_gateway_adapter.list_sessions("smoke_test_user")
    assert len(session_list) == 1
    assert session_list[0].id == session.id

    print(f"✓ SimpleGatewayAdapter basic functionality working: {session.id}")


def test_message_persistence(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that messages are persisted correctly"""

    # Create session and send message
    session = simple_gateway_adapter.create_session(
        user_id="message_test_user", agent_name="TestAgent"
    )

    response = simple_gateway_adapter.send_message(session.id, "Hello, test message!")

    # Verify message response
    assert response.content == "Received: Hello, test message!"
    assert response.session_id == session.id

    # Verify messages were persisted
    messages = simple_database_inspector.get_session_messages(session.id)
    assert len(messages) == 2  # user message + agent response

    # Check user message
    user_message = messages[0]
    assert user_message.role == "user"
    assert user_message.content == "Hello, test message!"

    # Check agent response
    agent_message = messages[1]
    assert agent_message.role == "assistant"
    assert agent_message.content == "Received: Hello, test message!"

    print("✓ Message persistence working correctly")


def test_database_architecture_validation(
    simple_database_inspector: SimpleDatabaseInspector, test_agents_list: list[str]
):
    """Test that database architecture validation works"""

    architecture = simple_database_inspector.verify_database_architecture(
        test_agents_list
    )

    # Verify Gateway migration state
    assert architecture["gateway_migration_version"] == "test_migration_001"

    # Verify all agents have correct schema
    for agent_name in test_agents_list:
        agent_tables = architecture["agent_schemas"][agent_name]
        assert "agent_sessions" in agent_tables
        assert "agent_messages" in agent_tables
        assert "alembic_version" not in agent_tables

    print(
        f"✓ Database architecture validation working for {len(test_agents_list)} agents"
    )


def test_database_cleanup_between_tests(
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that database cleanup works between tests"""

    # This test should start with clean databases
    stats = simple_database_inspector.get_database_stats()

    # All databases should start clean
    assert stats["gateway"]["sessions"] == 0
    assert stats["gateway"]["messages"] == 0

    for agent_name in [
        "TestAgent",
        "TestPeerAgentA",
        "TestPeerAgentB",
        "TestPeerAgentC",
    ]:
        agent_key = f"agent_{agent_name}"
        if agent_key in stats:
            assert stats[agent_key]["sessions"] == 0
            assert stats[agent_key]["messages"] == 0

    print("✓ Database cleanup working correctly between tests")


def test_session_isolation(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that sessions are properly isolated"""

    # Create two sessions for different users
    session_a = simple_gateway_adapter.create_session(
        user_id="user_a", agent_name="TestAgent"
    )

    session_b = simple_gateway_adapter.create_session(
        user_id="user_b", agent_name="TestAgent"
    )

    # Send messages to both sessions
    simple_gateway_adapter.send_message(session_a.id, "Message from user A")
    simple_gateway_adapter.send_message(session_b.id, "Message from user B")

    # Verify each user only sees their own sessions
    user_a_sessions = simple_database_inspector.get_gateway_sessions("user_a")
    user_b_sessions = simple_database_inspector.get_gateway_sessions("user_b")

    assert len(user_a_sessions) == 1
    assert len(user_b_sessions) == 1
    assert user_a_sessions[0].id == session_a.id
    assert user_b_sessions[0].id == session_b.id

    # Verify messages are isolated
    messages_a = simple_database_inspector.get_session_messages(session_a.id)
    messages_b = simple_database_inspector.get_session_messages(session_b.id)

    assert len(messages_a) == 2
    assert len(messages_b) == 2
    assert "user A" in messages_a[0].content
    assert "user B" in messages_b[0].content
    assert "user B" not in messages_a[0].content
    assert "user A" not in messages_b[0].content

    print("✓ Session isolation working correctly")


def test_agent_database_isolation(simple_database_inspector: SimpleDatabaseInspector):
    """Test that agent databases are properly isolated"""

    # Test isolation between different agents
    isolation_verified = simple_database_inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentA"
    )
    assert isolation_verified

    isolation_verified = simple_database_inspector.verify_database_isolation(
        "TestPeerAgentA", "TestPeerAgentB"
    )
    assert isolation_verified

    print("✓ Agent database isolation verified")


def test_error_handling(
    simple_gateway_adapter: SimpleGatewayAdapter,
    simple_database_manager: SimpleDatabaseManager,
):
    """Test that error handling works correctly"""

    # Test invalid session ID
    with pytest.raises(ValueError, match="Session .* not found"):
        simple_gateway_adapter.send_message(
            "nonexistent_session_id", "This should fail"
        )

    # Test invalid agent name for database connection
    with pytest.raises(ValueError, match="Agent database .* not initialized"):
        simple_database_manager.get_agent_connection("NonExistentAgent")

    # Test invalid session for switching
    with pytest.raises(ValueError, match="Session .* not found"):
        simple_gateway_adapter.switch_session("nonexistent_session_id")

    print("✓ Error handling works correctly")
