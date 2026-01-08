"""
Database architecture validation tests for the generic, provider-based infrastructure.

Tests that verify the correct database setup with Gateway migrations and Agent direct schema.
"""

import pytest
import sqlalchemy as sa

from ..infrastructure.database_inspector import DatabaseInspector
from ..infrastructure.database_manager import DatabaseManager


def test_gateway_database_has_migrations(database_inspector: DatabaseInspector):
    """Test that Gateway database has proper Alembic migration state"""
    migration_version = database_inspector.verify_gateway_migration_state()
    assert migration_version is not None


def test_agent_databases_have_direct_schema(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that Agent databases have direct schema (no migrations)"""
    for agent_name in test_agents_list:
        table_names = database_inspector.verify_agent_schema_state(agent_name)
        assert "agent_sessions" in table_names
        assert "agent_messages" in table_names
        assert "alembic_version" not in table_names


def test_complete_database_architecture(
    database_inspector: DatabaseInspector, test_agents_list: list[str]
):
    """Test that the complete database architecture is correct"""
    architecture = database_inspector.verify_database_architecture(test_agents_list)
    assert architecture["gateway_migration_version"] is not None
    for agent_name in test_agents_list:
        agent_tables = architecture["agent_schemas"][agent_name]
        assert "agent_sessions" in agent_tables
        assert "agent_messages" in agent_tables


def test_database_connections_work(
    database_manager: DatabaseManager, test_agents_list: list[str]
):
    """Test that we can connect to all databases"""
    # Test Gateway connection
    with database_manager.get_gateway_connection() as gateway_conn:
        result = gateway_conn.execute(sa.select(1)).scalar_one()
        assert result == 1, "Gateway database connection failed"

    # Test all agent connections
    for agent_name in test_agents_list:
        with database_manager.get_agent_connection(agent_name) as agent_conn:
            result = agent_conn.execute(sa.select(1)).scalar_one()
            assert result == 1, f"Agent {agent_name} database connection failed"


def test_database_separation(
    database_manager: DatabaseManager, test_agents_list: list[str]
):
    """Test that Gateway and Agent databases are properly separated"""
    # This test is specific to the SqliteProvider
    if not hasattr(database_manager.provider, "_sync_engines"):
        pytest.skip("This test is only for providers with _sync_engines")

    gateway_url = database_manager.provider.get_sync_gateway_engine().url
    agent_urls = [
        database_manager.provider.get_sync_agent_engine(name).url
        for name in test_agents_list
    ]

    all_urls = [gateway_url] + agent_urls
    assert len(set(all_urls)) == len(all_urls), "Database URLs are not unique"


def test_initial_database_state(database_inspector: DatabaseInspector):
    """Test that databases start in clean state"""
    stats = database_inspector.get_database_stats()

    # Gateway should be empty
    assert stats["gateway"]["sessions"] == 0
    assert stats["gateway"]["messages"] == 0

    # All agent databases should also be empty
    agent_keys = [key for key in stats if key.startswith("agent_")]
    for agent_key in agent_keys:
        assert stats[agent_key]["sessions"] == 0
        assert stats[agent_key]["messages"] == 0
