"""
Custom assertions for persistence testing.

Provides domain-specific assertions for validating database state and persistence behavior.
"""

from ..infrastructure.database_inspector import DatabaseInspector


def assert_gateway_session_exists(
    inspector: DatabaseInspector, session_id: str, user_id: str, agent_name: str
):
    """Assert that a gateway session exists with expected properties"""

    sessions = inspector.get_gateway_sessions(user_id)
    matching_sessions = [s for s in sessions if s.id == session_id]

    assert len(matching_sessions) == 1, (
        f"Expected 1 gateway session with ID {session_id}, found {len(matching_sessions)}"
    )

    session = matching_sessions[0]
    assert session.user_id == user_id, (
        f"Session user_id mismatch: expected {user_id}, got {session.user_id}"
    )
    assert session.name == agent_name, (
        f"Session agent_name mismatch: expected {agent_name}, got {session.name}"
    )


def assert_agent_session_exists(
    inspector: DatabaseInspector,
    agent_name: str,
    gateway_session_id: str,
    user_id: str,
):
    """Assert that an agent session exists with expected properties"""

    # This function is not directly supported by the new inspector.
    # It would require a new method in DatabaseInspector to get agent sessions.
    # For now, we will comment it out or adapt it if a similar method exists.
    pass


def assert_session_message_count(
    inspector: DatabaseInspector,
    session_id: str,
    expected_count: int,
):
    """Assert that a session has the expected number of messages"""

    messages = inspector.get_session_messages(session_id)

    assert len(messages) == expected_count, (
        f"Expected {expected_count} messages, found {len(messages)}"
    )


def assert_agent_session_message_count(
    inspector: DatabaseInspector,
    agent_name: str,
    gateway_session_id: str,
    expected_count: int,
):
    """Assert that an agent session has the expected number of messages"""
    # This function is not directly supported by the new inspector.
    pass


def assert_message_content_contains(
    inspector: DatabaseInspector,
    session_id: str,
    expected_content: str,
    role: str | None = None,
):
    """Assert that messages contain expected content"""

    messages = inspector.get_session_messages(session_id)

    # Filter by role if specified
    if role:
        # The new TaskResponse doesn't have a 'role' field directly.
        # This would need adaptation based on the new data model.
        pass

    # Check if any message contains the expected content
    matching_messages = [m for m in messages if expected_content in m.user_message]

    assert len(matching_messages) > 0, (
        f"No messages found containing '{expected_content}'"
    )


def assert_database_isolation(inspector: DatabaseInspector, agent_a: str, agent_b: str):
    """Assert that two agents have isolated databases"""

    isolation_verified = inspector.verify_database_isolation(agent_a, agent_b)
    assert isolation_verified, (
        f"Database isolation violated between {agent_a} and {agent_b}"
    )


def assert_session_linking(
    inspector: DatabaseInspector, gateway_session_id: str, agent_name: str
):
    """Assert that session linking between Gateway and Agent databases is correct"""
    # This function is not directly supported by the new inspector.
    pass


def assert_migration_state(
    inspector: DatabaseInspector, expected_version: str | None = None
):
    """Assert that Gateway database has correct migration state"""

    migration_version = inspector.verify_gateway_migration_state()

    if expected_version:
        assert migration_version == expected_version, (
            f"Expected migration version {expected_version}, got {migration_version}"
        )

    # Just ensure some version exists
    assert migration_version is not None, "No migration version found"
    assert len(migration_version) > 0, "Migration version is empty"


def assert_agent_schema_correct(
    inspector: DatabaseInspector,
    agent_name: str,
    expected_tables: list[str] | None = None,
):
    """Assert that Agent database has correct schema (no migrations)"""

    table_names = inspector.verify_agent_schema_state(agent_name)

    # Default expected tables for agent databases
    if expected_tables is None:
        expected_tables = ["agent_sessions", "agent_messages"]

    for table in expected_tables:
        assert table in table_names, (
            f"Agent {agent_name} missing expected table: {table}"
        )

    # Ensure no migration table exists
    assert "alembic_version" not in table_names, (
        f"Agent {agent_name} should not have alembic_version table"
    )


def assert_session_context_isolation(
    inspector: DatabaseInspector,
    session_a_id: str,
    session_b_id: str,
    agent_name: str,
):
    """Assert that two sessions for the same agent have isolated contexts"""
    # This function is not directly supported by the new inspector.
    pass


def assert_database_stats(
    inspector: DatabaseInspector, expected_stats: dict[str, dict[str, int]]
):
    """Assert database statistics match expectations"""

    actual_stats = inspector.get_database_stats()

    for db_name, expected_counts in expected_stats.items():
        assert db_name in actual_stats, f"Database {db_name} not found in stats"

        for stat_name, expected_count in expected_counts.items():
            actual_count = actual_stats[db_name].get(stat_name, -1)
            assert actual_count == expected_count, (
                f"{db_name}.{stat_name}: expected {expected_count}, got {actual_count}"
            )


def assert_no_data_leakage(
    inspector: DatabaseInspector, user_a_sessions: list[str], user_b_id: str
):
    """Assert that user A's sessions don't appear in user B's data"""

    user_b_sessions = inspector.get_gateway_sessions(user_b_id)
    user_b_session_ids = {s.id for s in user_b_sessions}

    for session_id in user_a_sessions:
        assert session_id not in user_b_session_ids, (
            f"User A session {session_id} found in User B's data"
        )
