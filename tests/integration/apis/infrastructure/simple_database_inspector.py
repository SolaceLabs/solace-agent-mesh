"""
Simple database inspector using synchronous SQLite.

A simplified version that uses standard sqlite3 to avoid dependency issues.
"""

from typing import NamedTuple

from .simple_database_manager import SimpleDatabaseManager


class SessionRecord(NamedTuple):
    """Represents a session record from database"""

    id: str
    user_id: str
    agent_name: str
    created_at: str


class MessageRecord(NamedTuple):
    """Represents a message record from database"""

    id: int
    session_id: str
    role: str
    content: str
    timestamp: str


class AgentSessionRecord(NamedTuple):
    """Represents an agent session record from database"""

    id: int
    gateway_session_id: str
    agent_name: str
    user_id: str
    session_data: str | None


class SimpleDatabaseInspector:
    """Provides inspection across Gateway and Agent databases using sqlite3"""

    def __init__(self, db_manager: SimpleDatabaseManager):
        self.db_manager = db_manager

    def verify_gateway_migration_state(self):
        """Verify Gateway database has proper migration state"""
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute("SELECT version_num FROM alembic_version")
            alembic_version = cursor.fetchone()

        assert alembic_version is not None, "Gateway database migrations not applied"
        return alembic_version[0]

    def verify_agent_schema_state(self, agent_name: str):
        """Verify Agent database has proper schema (no migrations)"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

        table_names = [t[0] for t in tables]
        assert "alembic_version" not in table_names, (
            f"Agent {agent_name} should not have migration table"
        )
        assert "agent_sessions" in table_names, (
            f"Agent {agent_name} missing required tables"
        )
        assert "agent_messages" in table_names, (
            f"Agent {agent_name} missing required tables"
        )

        return table_names

    def verify_database_architecture(self, agent_names: list[str]):
        """Verify the correct database architecture is in place"""

        # Gateway should have migrations
        gateway_version = self.verify_gateway_migration_state()

        # Agents should have direct schema (no migrations)
        agent_schemas = {}
        for agent_name in agent_names:
            agent_schemas[agent_name] = self.verify_agent_schema_state(agent_name)

        return {
            "gateway_migration_version": gateway_version,
            "agent_schemas": agent_schemas,
        }

    def get_gateway_sessions(self, user_id: str) -> list[SessionRecord]:
        """Get all gateway sessions for a user"""
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute(
                "SELECT id, user_id, agent_name, created_at FROM gateway_sessions WHERE user_id = ?",
                (user_id,),
            )
            rows = cursor.fetchall()

        return [SessionRecord(*row) for row in rows]

    def get_session_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a gateway session"""
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute(
                "SELECT id, session_id, role, content, timestamp FROM gateway_messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
            rows = cursor.fetchall()

        return [MessageRecord(*row) for row in rows]

    def get_agent_sessions(
        self, agent_name: str, gateway_session_id: str | None = None
    ) -> list[AgentSessionRecord]:
        """Get agent sessions, optionally filtered by gateway session ID"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            if gateway_session_id:
                cursor = conn.execute(
                    "SELECT id, gateway_session_id, agent_name, user_id, session_data FROM agent_sessions WHERE gateway_session_id = ?",
                    (gateway_session_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, gateway_session_id, agent_name, user_id, session_data FROM agent_sessions"
                )
            rows = cursor.fetchall()

        return [AgentSessionRecord(*row) for row in rows]

    def get_agent_messages(
        self, agent_name: str, gateway_session_id: str
    ) -> list[MessageRecord]:
        """Get all messages for an agent session"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            cursor = conn.execute(
                "SELECT id, gateway_session_id as session_id, role, content, timestamp FROM agent_messages WHERE gateway_session_id = ? ORDER BY timestamp",
                (gateway_session_id,),
            )
            rows = cursor.fetchall()

        return [MessageRecord(*row) for row in rows]

    def verify_session_linking(self, gateway_session_id: str, agent_name: str):
        """Verify session exists in both Gateway and Agent databases"""

        # Check Gateway database
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute(
                "SELECT id, user_id, agent_name FROM gateway_sessions WHERE id = ?",
                (gateway_session_id,),
            )
            gateway_session = cursor.fetchone()

        # Check Agent database
        with self.db_manager.get_agent_connection(agent_name) as conn:
            cursor = conn.execute(
                "SELECT id, gateway_session_id, agent_name, user_id FROM agent_sessions WHERE gateway_session_id = ?",
                (gateway_session_id,),
            )
            agent_session = cursor.fetchone()

        assert gateway_session is not None, (
            f"Gateway session {gateway_session_id} not found"
        )
        assert agent_session is not None, (
            f"Agent session for {gateway_session_id} not found in {agent_name}"
        )
        assert agent_session[1] == gateway_session_id, (
            "Session ID mismatch in agent database"
        )
        assert agent_session[2] == agent_name, "Agent name mismatch in agent database"
        assert gateway_session[1] == agent_session[3], (
            "User ID mismatch between Gateway and Agent"
        )

        return {
            "gateway_session": SessionRecord(
                gateway_session[0], gateway_session[1], gateway_session[2], ""
            ),
            "agent_session": AgentSessionRecord(*agent_session, None),
        }

    def verify_database_isolation(self, agent_a: str, agent_b: str):
        """Verify Agent A's data doesn't appear in Agent B's database"""

        # Get all sessions from Agent A
        with self.db_manager.get_agent_connection(agent_a) as conn:
            cursor = conn.execute("SELECT gateway_session_id FROM agent_sessions")
            agent_a_sessions = cursor.fetchall()

        # Verify none appear in Agent B's database
        with self.db_manager.get_agent_connection(agent_b) as conn:
            for session in agent_a_sessions:
                cursor = conn.execute(
                    "SELECT id FROM agent_sessions WHERE gateway_session_id = ?",
                    (session[0],),
                )
                agent_b_session = cursor.fetchone()

                assert agent_b_session is None, (
                    f"Session leak detected: {session[0]} found in both {agent_a} and {agent_b} databases"
                )

        return True

    def get_database_stats(self) -> dict:
        """Get statistics about all databases for debugging"""
        stats = {}

        # Gateway stats
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM gateway_sessions")
            session_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM gateway_messages")
            message_count = cursor.fetchone()[0]

        stats["gateway"] = {"sessions": session_count, "messages": message_count}

        # Agent stats
        for agent_name in self.db_manager.agent_db_paths.keys():
            with self.db_manager.get_agent_connection(agent_name) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM agent_sessions")
                agent_session_count = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM agent_messages")
                agent_message_count = cursor.fetchone()[0]

            stats[f"agent_{agent_name}"] = {
                "sessions": agent_session_count,
                "messages": agent_message_count,
            }

        return stats
