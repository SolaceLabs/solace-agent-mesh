"""
Simple smoke tests for the API persistence testing framework.

Basic tests to verify that the simplified framework works without external dependencies.
"""

import json

import pytest
import sqlalchemy as sa

from .infrastructure.database_inspector import DatabaseInspector
from .infrastructure.database_manager import DatabaseManager
from .infrastructure.gateway_adapter import GatewayAdapter


def test_database_initialization_and_connections(
    database_manager: DatabaseManager, test_agents_list: list[str]
):
    """
    Test that the DatabaseManager initializes correctly and that all databases are created and accessible.
    """
    # 1. Verify the manager and its provider are initialized
    assert database_manager is not None
    assert database_manager.provider is not None

    # 2. Verify that the gateway database is accessible
    try:
        with database_manager.get_gateway_connection() as gateway_conn:
            result = gateway_conn.execute(sa.select(1)).scalar_one()
            assert result == 1
    except Exception as e:
        pytest.fail(f"Failed to connect to gateway database: {e}")

    # 3. Verify that all agent databases are accessible
    for agent_name in test_agents_list:
        try:
            with database_manager.get_agent_connection(agent_name) as agent_conn:
                result = agent_conn.execute(sa.select(1)).scalar_one()
                assert result == 1
        except Exception as e:
            pytest.fail(f"Failed to connect to agent '{agent_name}' database: {e}")


def test_database_inspector_basic(
    database_manager: DatabaseManager, test_agents_list: list[str]
):
    """Test that DatabaseInspector works"""
    inspector = DatabaseInspector(database_manager)
    migration_version = inspector.verify_gateway_migration_state()
    assert migration_version is not None
    assert len(migration_version) > 0

    for agent_name in test_agents_list:
        table_names = inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names


def test_gateway_adapter_basic(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test that GatewayAdapter basic functionality works"""
    session = gateway_adapter.create_session(
        user_id="smoke_test_user", agent_name="TestAgent"
    )
    assert session.id is not None
    assert session.user_id == "smoke_test_user"
    assert session.agent_id == "TestAgent"

    gateway_sessions = database_inspector.get_gateway_sessions("smoke_test_user")
    assert len(gateway_sessions) == 1
    assert gateway_sessions[0].id == session.id

    session_list = gateway_adapter.list_sessions("smoke_test_user")
    assert len(session_list) == 1
    assert session_list[0].id == session.id


def test_message_persistence(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test that messages are persisted correctly"""
    session = gateway_adapter.create_session(
        user_id="message_test_user", agent_name="TestAgent"
    )
    response = gateway_adapter.send_message(session.id, "Hello, test message!")
    assert "Hello, test message!" in response.message_bubbles
    assert response.session_id == session.id

    messages = database_inspector.get_session_messages(session.id)
    assert len(messages) == 2

    # User message
    user_message_task = messages[0]
    assert user_message_task.user_message == "Hello, test message!"
    assert "user" in user_message_task.message_bubbles

    # Agent message
    agent_message_task = messages[1]
    assert "assistant" in agent_message_task.message_bubbles
    assert "Received: Hello, test message!" in agent_message_task.message_bubbles


def test_database_architecture_validation(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that database architecture validation works"""
    # This test is simplified as the new provider model doesn't expose the same architecture details
    migration_version = database_inspector.verify_gateway_migration_state()
    assert migration_version is not None

    for agent_name in test_agents_list:
        table_names = database_inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names


def test_database_cleanup_between_tests(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that database cleanup works between tests"""
    # This test is simplified as cleanup is handled by the provider fixture
    stats = database_inspector.get_database_stats()

    # All databases should start clean
    assert stats["gateway"]["sessions"] == 0
    assert stats["gateway"]["messages"] == 0

    for agent_name in test_agents_list:
        agent_key = f"agent_{agent_name}"
        if agent_key in stats:
            assert stats[agent_key]["sessions"] == 0
            assert stats[agent_key]["messages"] == 0


def test_session_isolation(
    gateway_adapter: GatewayAdapter, database_inspector: DatabaseInspector
):
    """Test that sessions are properly isolated"""
    session_a = gateway_adapter.create_session(user_id="user_a", agent_name="TestAgent")
    session_b = gateway_adapter.create_session(user_id="user_b", agent_name="TestAgent")

    gateway_adapter.send_message(session_a.id, "Message from user A")
    gateway_adapter.send_message(session_b.id, "Message from user B")

    user_a_sessions = database_inspector.get_gateway_sessions("user_a")
    user_b_sessions = database_inspector.get_gateway_sessions("user_b")

    assert len(user_a_sessions) == 1
    assert len(user_b_sessions) == 1
    assert user_a_sessions[0].id == session_a.id
    assert user_b_sessions[0].id == session_b.id

    messages_a = database_inspector.get_session_messages(session_a.id)
    messages_b = database_inspector.get_session_messages(session_b.id)

    assert len(messages_a) == 2
    assert len(messages_b) == 2

    # Check user A's messages
    bubbles_a = json.loads(messages_a[0].message_bubbles)
    assert "Message from user A" in bubbles_a[0]["text"]
    assert "Message from user B" not in bubbles_a[0]["text"]

    # Check user B's messages
    bubbles_b = json.loads(messages_b[0].message_bubbles)
    assert "Message from user B" in bubbles_b[0]["text"]
    assert "Message from user A" not in bubbles_b[0]["text"]


def test_agent_database_isolation(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that agent databases are properly isolated"""
    # Test isolation between different agents
    for i in range(len(test_agents_list) - 1):
        agent_a = test_agents_list[i]
        agent_b = test_agents_list[i + 1]
        isolation_verified = database_inspector.verify_database_isolation(
            agent_a, agent_b
        )
        assert isolation_verified


def test_error_handling(
    gateway_adapter: GatewayAdapter, database_manager: DatabaseManager
):
    """Test that error handling works correctly"""
    with pytest.raises(ValueError, match="Session .* not found"):
        gateway_adapter.send_message("nonexistent_session_id", "This should fail")

    with pytest.raises(
        ValueError, match="Agent database for 'NonExistentAgent' not initialized."
    ):
        database_manager.get_agent_connection("NonExistentAgent")

    with pytest.raises(ValueError, match="Session .* not found"):
        gateway_adapter.switch_session("nonexistent_session_id")


def test_database_stats(
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
    test_agents_list: list[str],
):
    """Test that get_database_stats returns correct counts."""
    # 1. Verify initial state is empty
    initial_stats = database_inspector.get_database_stats()
    assert initial_stats["gateway"]["sessions"] == 0
    assert initial_stats["gateway"]["messages"] == 0
    for agent_name in test_agents_list:
        agent_key = f"agent_{agent_name}"
        if agent_key in initial_stats:
            assert initial_stats[agent_key]["sessions"] == 0
            assert initial_stats[agent_key]["messages"] == 0

    # 2. Create a session and send a message
    session = gateway_adapter.create_session(
        user_id="stats_user", agent_name="TestAgent"
    )
    gateway_adapter.send_message(session.id, "Hello stats!")

    # 3. Verify stats after actions
    final_stats = database_inspector.get_database_stats()
    assert final_stats["gateway"]["sessions"] == 1
    assert (
        final_stats["gateway"]["messages"] == 2
    )  # User message + simulated agent response

    # Note: The generic GatewayAdapter does not interact with agent databases,
    # so their stats should remain 0. This is expected behavior for this test.
    agent_key = "agent_TestAgent"
    if agent_key in final_stats:
        assert final_stats[agent_key]["sessions"] == 0
        assert final_stats[agent_key]["messages"] == 0
