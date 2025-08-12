#!/usr/bin/env python3
"""
Simple test runner to verify the API persistence framework works.

This runs basic tests without requiring pytest or other external dependencies.
"""

import sys
import traceback
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.integration.apis.infrastructure.simple_database_inspector import (
    SimpleDatabaseInspector,
)
from tests.integration.apis.infrastructure.simple_database_manager import (
    SimpleDatabaseManager,
)
from tests.integration.apis.infrastructure.simple_gateway_adapter import (
    SimpleGatewayAdapter,
)


def run_test(test_name, test_func):
    """Run a single test and report results"""
    try:
        print(f"\n🧪 Running {test_name}...")
        test_func()
        print(f"✅ {test_name} PASSED")
        return True
    except Exception as e:
        print(f"❌ {test_name} FAILED: {e}")
        traceback.print_exc()
        return False


def test_database_manager_initialization():
    """Test that SimpleDatabaseManager initializes correctly"""
    manager = SimpleDatabaseManager()

    # Set up databases for test agents
    test_agents = ["TestAgent", "TestPeerAgentA", "TestPeerAgentB"]
    manager.setup_test_databases(test_agents)

    # Verify Gateway database path exists
    assert manager.gateway_db_path is not None
    assert manager.gateway_db_path.exists()

    # Verify Agent database paths exist
    assert len(manager.agent_db_paths) == len(test_agents)

    for agent_name in test_agents:
        assert agent_name in manager.agent_db_paths
        agent_path = manager.agent_db_paths[agent_name]
        assert agent_path.exists()
        assert agent_name.lower() in str(agent_path)

    # Test database connections
    with manager.get_gateway_connection() as gateway_conn:
        cursor = gateway_conn.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

    for agent_name in manager.agent_db_paths.keys():
        with manager.get_agent_connection(agent_name) as agent_conn:
            cursor = agent_conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    # Clean up
    manager.cleanup_all_databases()

    print("  ✓ Database manager initialized and connections verified")


def test_database_inspector():
    """Test database inspector functionality"""
    manager = SimpleDatabaseManager()
    test_agents = ["TestAgent", "TestPeerAgentA"]
    manager.setup_test_databases(test_agents)

    inspector = SimpleDatabaseInspector(manager)

    # Test Gateway migration verification
    migration_version = inspector.verify_gateway_migration_state()
    assert migration_version == "test_migration_001"

    # Test Agent schema verification
    for agent_name in test_agents:
        table_names = inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names

    # Test database architecture validation
    architecture = inspector.verify_database_architecture(test_agents)
    assert architecture["gateway_migration_version"] == "test_migration_001"

    for agent_name in test_agents:
        agent_tables = architecture["agent_schemas"][agent_name]
        assert "agent_sessions" in agent_tables
        assert "agent_messages" in agent_tables
        assert "alembic_version" not in agent_tables

    # Test database isolation
    isolation_verified = inspector.verify_database_isolation(
        "TestAgent", "TestPeerAgentA"
    )
    assert isolation_verified

    # Clean up
    manager.cleanup_all_databases()

    print("  ✓ Database inspector functionality verified")


def test_gateway_adapter():
    """Test gateway adapter functionality"""
    manager = SimpleDatabaseManager()
    test_agents = ["TestAgent"]
    manager.setup_test_databases(test_agents)

    adapter = SimpleGatewayAdapter(manager)
    inspector = SimpleDatabaseInspector(manager)

    # Test session creation
    session = adapter.create_session(user_id="test_user", agent_name="TestAgent")

    assert session.id is not None
    assert len(session.id) > 0
    assert session.user_id == "test_user"
    assert session.agent_name == "TestAgent"

    # Verify session was persisted
    gateway_sessions = inspector.get_gateway_sessions("test_user")
    assert len(gateway_sessions) == 1
    assert gateway_sessions[0].id == session.id

    # Test message sending
    response = adapter.send_message(session.id, "Hello, test message!")
    assert response.content == "Received: Hello, test message!"
    assert response.session_id == session.id

    # Verify messages were persisted
    messages = inspector.get_session_messages(session.id)
    assert len(messages) == 2  # user message + agent response

    user_message = messages[0]
    assert user_message.role == "user"
    assert user_message.content == "Hello, test message!"

    agent_message = messages[1]
    assert agent_message.role == "assistant"
    assert agent_message.content == "Received: Hello, test message!"

    # Test session listing
    session_list = adapter.list_sessions("test_user")
    assert len(session_list) == 1
    assert session_list[0].id == session.id

    # Test session switching
    switched_session = adapter.switch_session(session.id)
    assert switched_session.id == session.id

    # Test session deletion
    deleted = adapter.delete_session(session.id)
    assert deleted

    # Verify session is gone
    remaining_sessions = inspector.get_gateway_sessions("test_user")
    assert len(remaining_sessions) == 0

    # Clean up
    manager.cleanup_all_databases()

    print("  ✓ Gateway adapter functionality verified")


def test_session_isolation():
    """Test that sessions are properly isolated"""
    manager = SimpleDatabaseManager()
    test_agents = ["TestAgent"]
    manager.setup_test_databases(test_agents)

    adapter = SimpleGatewayAdapter(manager)
    inspector = SimpleDatabaseInspector(manager)

    # Create sessions for different users
    session_a = adapter.create_session(user_id="user_a", agent_name="TestAgent")
    session_b = adapter.create_session(user_id="user_b", agent_name="TestAgent")

    # Send messages to both sessions
    adapter.send_message(session_a.id, "Message from user A")
    adapter.send_message(session_b.id, "Message from user B")

    # Verify each user only sees their own sessions
    user_a_sessions = inspector.get_gateway_sessions("user_a")
    user_b_sessions = inspector.get_gateway_sessions("user_b")

    assert len(user_a_sessions) == 1
    assert len(user_b_sessions) == 1
    assert user_a_sessions[0].id == session_a.id
    assert user_b_sessions[0].id == session_b.id

    # Verify messages are isolated
    messages_a = inspector.get_session_messages(session_a.id)
    messages_b = inspector.get_session_messages(session_b.id)

    assert len(messages_a) == 2
    assert len(messages_b) == 2
    assert "user A" in messages_a[0].content
    assert "user B" in messages_b[0].content

    # Clean up
    manager.cleanup_all_databases()

    print("  ✓ Session isolation verified")


def test_error_handling():
    """Test error handling"""
    manager = SimpleDatabaseManager()
    test_agents = ["TestAgent"]
    manager.setup_test_databases(test_agents)

    adapter = SimpleGatewayAdapter(manager)

    # Test invalid session ID
    try:
        adapter.send_message("nonexistent_session_id", "This should fail")
        assert False, "Expected ValueError for invalid session ID"
    except ValueError as e:
        assert "not found" in str(e)

    # Test invalid agent name
    try:
        manager.get_agent_connection("NonExistentAgent")
        assert False, "Expected ValueError for invalid agent name"
    except ValueError as e:
        assert "not initialized" in str(e)

    # Test invalid session for switching
    try:
        adapter.switch_session("nonexistent_session_id")
        assert False, "Expected ValueError for invalid session switching"
    except ValueError as e:
        assert "not found" in str(e)

    # Clean up
    manager.cleanup_all_databases()

    print("  ✓ Error handling verified")


def main():
    """Run all tests and report results"""
    print("🚀 Starting API Persistence Framework Tests")
    print("=" * 50)

    tests = [
        ("Database Manager Initialization", test_database_manager_initialization),
        ("Database Inspector", test_database_inspector),
        ("Gateway Adapter", test_gateway_adapter),
        ("Session Isolation", test_session_isolation),
        ("Error Handling", test_error_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print(
            "🎉 All tests passed! The API persistence framework is working correctly."
        )
        return 0
    else:
        print(f"💥 {total - passed} tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
