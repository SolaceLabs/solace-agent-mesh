"""
Custom assertions for persistence testing.

Provides domain-specific assertions for validating database state and persistence behavior.
"""

from ..infrastructure.database_inspector import CrossDatabaseInspector


async def assert_gateway_session_exists(
    inspector: CrossDatabaseInspector, session_id: str, user_id: str, agent_name: str
):
    """Assert that a gateway session exists with expected properties"""

    sessions = await inspector.get_gateway_sessions(user_id)
    matching_sessions = [s for s in sessions if s.id == session_id]

    assert len(matching_sessions) == 1, (
        f"Expected 1 gateway session with ID {session_id}, found {len(matching_sessions)}"
    )

    session = matching_sessions[0]
    assert session.user_id == user_id, (
        f"Session user_id mismatch: expected {user_id}, got {session.user_id}"
    )
    assert session.agent_name == agent_name, (
        f"Session agent_name mismatch: expected {agent_name}, got {session.agent_name}"
    )


async def assert_agent_session_exists(
    inspector: CrossDatabaseInspector,
    agent_name: str,
    gateway_session_id: str,
    user_id: str,
):
    """Assert that an agent session exists with expected properties"""

    sessions = await inspector.get_agent_sessions(agent_name, gateway_session_id)

    assert len(sessions) == 1, (
        f"Expected 1 agent session for {gateway_session_id}, found {len(sessions)}"
    )

    session = sessions[0]
    assert session.gateway_session_id == gateway_session_id, (
        "Gateway session ID mismatch"
    )
    assert session.agent_name == agent_name, "Agent name mismatch"
    assert session.user_id == user_id, "User ID mismatch"


async def assert_session_message_count(
    inspector: CrossDatabaseInspector,
    session_id: str,
    expected_count: int,
    database_type: str = "gateway",
):
    """Assert that a session has the expected number of messages"""

    if database_type == "gateway":
        messages = await inspector.get_session_messages(session_id)
    else:
        # For agent database, we need the agent name
        raise ValueError("Agent message count assertion requires agent_name parameter")

    assert len(messages) == expected_count, (
        f"Expected {expected_count} messages, found {len(messages)}"
    )


async def assert_agent_session_message_count(
    inspector: CrossDatabaseInspector,
    agent_name: str,
    gateway_session_id: str,
    expected_count: int,
):
    """Assert that an agent session has the expected number of messages"""

    messages = await inspector.get_agent_messages(agent_name, gateway_session_id)
    assert len(messages) == expected_count, (
        f"Expected {expected_count} agent messages, found {len(messages)}"
    )


async def assert_message_content_contains(
    inspector: CrossDatabaseInspector,
    session_id: str,
    expected_content: str,
    role: str | None = None,
    database_type: str = "gateway",
    agent_name: str | None = None,
):
    """Assert that messages contain expected content"""

    if database_type == "gateway":
        messages = await inspector.get_session_messages(session_id)
    elif database_type == "agent" and agent_name:
        messages = await inspector.get_agent_messages(agent_name, session_id)
    else:
        raise ValueError("Agent message assertion requires agent_name parameter")

    # Filter by role if specified
    if role:
        messages = [m for m in messages if m.role == role]

    # Check if any message contains the expected content
    matching_messages = [m for m in messages if expected_content in m.content]

    assert len(matching_messages) > 0, (
        f"No messages found containing '{expected_content}'"
    )


async def assert_database_isolation(
    inspector: CrossDatabaseInspector, agent_a: str, agent_b: str
):
    """Assert that two agents have isolated databases"""

    isolation_verified = await inspector.verify_database_isolation(agent_a, agent_b)
    assert isolation_verified, (
        f"Database isolation violated between {agent_a} and {agent_b}"
    )


async def assert_session_linking(
    inspector: CrossDatabaseInspector, gateway_session_id: str, agent_name: str
):
    """Assert that session linking between Gateway and Agent databases is correct"""

    linking_result = await inspector.verify_session_linking(
        gateway_session_id, agent_name
    )

    # The verify_session_linking method raises assertions internally
    # If we reach this point, linking is verified
    assert linking_result is not None, "Session linking verification failed"

    gateway_session = linking_result["gateway_session"]
    agent_session = linking_result["agent_session"]

    assert gateway_session.id == gateway_session_id, "Gateway session ID mismatch"
    assert agent_session.gateway_session_id == gateway_session_id, (
        "Agent session linking mismatch"
    )


async def assert_migration_state(
    inspector: CrossDatabaseInspector, expected_version: str | None = None
):
    """Assert that Gateway database has correct migration state"""

    migration_version = await inspector.verify_gateway_migration_state()

    if expected_version:
        assert migration_version == expected_version, (
            f"Expected migration version {expected_version}, got {migration_version}"
        )

    # Just ensure some version exists
    assert migration_version is not None, "No migration version found"
    assert len(migration_version) > 0, "Migration version is empty"


async def assert_agent_schema_correct(
    inspector: CrossDatabaseInspector,
    agent_name: str,
    expected_tables: list[str] | None = None,
):
    """Assert that Agent database has correct schema (no migrations)"""

    table_names = await inspector.verify_agent_schema_state(agent_name)

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


async def assert_session_context_isolation(
    inspector: CrossDatabaseInspector,
    session_a_id: str,
    session_b_id: str,
    agent_name: str,
):
    """Assert that two sessions for the same agent have isolated contexts"""

    isolation_result = await inspector.verify_session_context_isolation(
        session_a_id, session_b_id, agent_name
    )

    assert isolation_result["content_isolated"], (
        f"Sessions {session_a_id} and {session_b_id} do not have isolated content"
    )
    assert isolation_result["session_x_messages"] > 0, (
        f"Session {session_a_id} has no messages"
    )
    assert isolation_result["session_y_messages"] > 0, (
        f"Session {session_b_id} has no messages"
    )


async def assert_database_stats(
    inspector: CrossDatabaseInspector, expected_stats: dict[str, dict[str, int]]
):
    """Assert database statistics match expectations"""

    actual_stats = await inspector.get_database_stats()

    for db_name, expected_counts in expected_stats.items():
        assert db_name in actual_stats, f"Database {db_name} not found in stats"

        for stat_name, expected_count in expected_counts.items():
            actual_count = actual_stats[db_name].get(stat_name, -1)
            assert actual_count == expected_count, (
                f"{db_name}.{stat_name}: expected {expected_count}, got {actual_count}"
            )


async def assert_no_data_leakage(
    inspector: CrossDatabaseInspector, user_a_sessions: list[str], user_b_id: str
):
    """Assert that user A's sessions don't appear in user B's data"""

    user_b_sessions = await inspector.get_gateway_sessions(user_b_id)
    user_b_session_ids = {s.id for s in user_b_sessions}

    for session_id in user_a_sessions:
        assert session_id not in user_b_session_ids, (
            f"User A session {session_id} found in User B's data"
        )
