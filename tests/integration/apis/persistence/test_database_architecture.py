"""
Database architecture validation tests.

Tests that verify the correct database setup with Gateway migrations and Agent direct schema.
"""

from ..infrastructure.simple_database_inspector import SimpleDatabaseInspector
from ..infrastructure.simple_database_manager import SimpleDatabaseManager


def test_gateway_database_has_migrations(
    simple_database_inspector: SimpleDatabaseInspector,
):
    """Test that Gateway database has proper Alembic migration state"""

    # Verify Gateway has migration table and version
    migration_version = simple_database_inspector.verify_gateway_migration_state()
    assert migration_version == "test_migration_001"

    # Verify Gateway has expected tables
    with simple_database_inspector.db_manager.get_gateway_connection() as gateway_conn:
        cursor = gateway_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = cursor.fetchall()

    table_names = [t[0] for t in tables]

    # Gateway should have migration table
    assert "alembic_version" in table_names, "Gateway missing alembic_version table"
    assert "gateway_sessions" in table_names, "Gateway missing gateway_sessions table"
    assert "gateway_messages" in table_names, "Gateway missing gateway_messages table"

    print("✓ Gateway database: Alembic migrations applied correctly")


def test_agent_databases_have_direct_schema(
    simple_database_inspector: SimpleDatabaseInspector, test_agents_list: list[str]
):
    """Test that Agent databases have direct schema (no migrations)"""

    for agent_name in test_agents_list:
        # Verify agent has correct schema without migrations
        table_names = simple_database_inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names

    print(
        f"✓ Agent databases ({len(test_agents_list)}): Direct schema creation (no migrations)"
    )


def test_complete_database_architecture(
    simple_database_inspector: SimpleDatabaseInspector, test_agents_list: list[str]
):
    """Test that the complete database architecture is correct"""

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

    print(f"✓ Complete architecture verified: Gateway + {len(test_agents_list)} agents")


def test_database_separation(
    simple_database_manager: SimpleDatabaseManager, test_agents_list: list[str]
):
    """Test that Gateway and Agent databases are properly separated"""

    # Verify we have separate database paths
    assert simple_database_manager.gateway_db_path is not None
    assert len(simple_database_manager.agent_db_paths) == len(test_agents_list)

    # Verify all database paths are different
    all_db_paths = [simple_database_manager.gateway_db_path]
    all_db_paths.extend(simple_database_manager.agent_db_paths.values())

    unique_paths = set(all_db_paths)
    assert len(unique_paths) == len(all_db_paths), "Database paths are not unique"

    # Verify each agent has its own database
    for agent_name in test_agents_list:
        assert agent_name in simple_database_manager.agent_db_paths
        agent_path = simple_database_manager.agent_db_paths[agent_name]
        assert agent_path != simple_database_manager.gateway_db_path

    print(f"✓ Database separation verified: {len(all_db_paths)} separate databases")


def test_initial_database_state(simple_database_inspector: SimpleDatabaseInspector):
    """Test that databases start in clean state"""

    # Get current database statistics
    stats = simple_database_inspector.get_database_stats()

    # Gateway should be empty
    assert stats["gateway"]["sessions"] == 0
    assert stats["gateway"]["messages"] == 0

    # All agent databases should also be empty
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

    print("✓ All databases start in clean state")


def test_database_connections_work(
    simple_database_manager: SimpleDatabaseManager, test_agents_list: list[str]
):
    """Test that we can connect to all databases"""

    # Test Gateway connection
    with simple_database_manager.get_gateway_connection() as gateway_conn:
        cursor = gateway_conn.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1, "Gateway database connection failed"

    # Test all agent connections
    for agent_name in test_agents_list:
        with simple_database_manager.get_agent_connection(agent_name) as agent_conn:
            cursor = agent_conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1, f"Agent {agent_name} database connection failed"

    print(
        f"✓ All database connections working: Gateway + {len(test_agents_list)} agents"
    )
