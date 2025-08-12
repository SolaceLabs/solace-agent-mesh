"""
Cross-database inspector for validation across Gateway and Agent databases.

Provides utilities to verify database state, session linking, and architecture correctness.
"""

from typing import NamedTuple

from sqlalchemy import text

from .multi_database_manager import MultiDatabaseManager


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


class CrossDatabaseInspector:
    """Provides inspection across Gateway (migrated) and Agent (direct schema) databases"""

    def __init__(self, db_manager: MultiDatabaseManager):
        self.db_manager = db_manager

    async def verify_gateway_migration_state(self):
        """Verify Gateway database has proper migration state"""
        gateway_engine = self.db_manager.get_gateway_engine()

        # Check alembic_version table exists (indicates migrations ran)
        with gateway_engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            alembic_version = result.fetchone()

        assert alembic_version is not None, "Gateway database migrations not applied"
        return alembic_version[0]

    async def verify_agent_schema_state(self, agent_name: str):
        """Verify Agent database has proper schema (no migrations)"""
        agent_engine = self.db_manager.get_agent_engine(agent_name)

        # Check expected agent tables exist (but no alembic_version table)
        with agent_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = result.fetchall()

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

    async def verify_database_architecture(self, agent_names: list[str]):
        """Verify the correct database architecture is in place"""

        # Gateway should have migrations
        gateway_version = await self.verify_gateway_migration_state()

        # Agents should have direct schema (no migrations)
        agent_schemas = {}
        for agent_name in agent_names:
            agent_schemas[agent_name] = await self.verify_agent_schema_state(agent_name)

        return {
            "gateway_migration_version": gateway_version,
            "agent_schemas": agent_schemas,
        }

    async def get_gateway_sessions(self, user_id: str) -> list[SessionRecord]:
        """Get all gateway sessions for a user"""
        gateway_engine = self.db_manager.get_gateway_engine()

        with gateway_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT id, user_id, agent_name, created_at FROM gateway_sessions WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
            rows = result.fetchall()

        return [SessionRecord(*row) for row in rows]

    async def get_session_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a gateway session"""
        gateway_conn = await self.db_manager.get_gateway_connection()

        cursor = await gateway_conn.execute(
            "SELECT id, session_id, role, content, timestamp FROM gateway_messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        return [MessageRecord(*row) for row in rows]

    async def get_agent_sessions(
        self, agent_name: str, gateway_session_id: str | None = None
    ) -> list[AgentSessionRecord]:
        """Get agent sessions, optionally filtered by gateway session ID"""
        agent_conn = await self.db_manager.get_agent_connection(agent_name)

        if gateway_session_id:
            query = "SELECT id, gateway_session_id, agent_name, user_id, session_data FROM agent_sessions WHERE gateway_session_id = ?"
            params = (gateway_session_id,)
        else:
            query = "SELECT id, gateway_session_id, agent_name, user_id, session_data FROM agent_sessions"
            params = ()

        cursor = await agent_conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

        return [AgentSessionRecord(*row) for row in rows]

    async def get_agent_messages(
        self, agent_name: str, gateway_session_id: str
    ) -> list[MessageRecord]:
        """Get all messages for an agent session"""
        agent_conn = await self.db_manager.get_agent_connection(agent_name)

        cursor = await agent_conn.execute(
            "SELECT id, gateway_session_id as session_id, role, content, timestamp FROM agent_messages WHERE gateway_session_id = ? ORDER BY timestamp",
            (gateway_session_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        return [MessageRecord(*row) for row in rows]

    async def verify_session_linking(self, gateway_session_id: str, agent_name: str):
        """Verify session exists in both Gateway and Agent databases"""

        # Check Gateway database
        gateway_conn = await self.db_manager.get_gateway_connection()
        cursor = await gateway_conn.execute(
            "SELECT id, user_id, agent_name FROM gateway_sessions WHERE id = ?",
            (gateway_session_id,),
        )
        gateway_session = await cursor.fetchone()
        await cursor.close()

        # Check Agent database
        agent_conn = await self.db_manager.get_agent_connection(agent_name)
        cursor = await agent_conn.execute(
            "SELECT id, gateway_session_id, agent_name, user_id FROM agent_sessions WHERE gateway_session_id = ?",
            (gateway_session_id,),
        )
        agent_session = await cursor.fetchone()
        await cursor.close()

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

    async def verify_database_isolation(self, agent_a: str, agent_b: str):
        """Verify Agent A's data doesn't appear in Agent B's database"""

        agent_a_conn = await self.db_manager.get_agent_connection(agent_a)
        agent_b_conn = await self.db_manager.get_agent_connection(agent_b)

        # Get all sessions from Agent A
        cursor_a = await agent_a_conn.execute(
            "SELECT gateway_session_id FROM agent_sessions"
        )
        agent_a_sessions = await cursor_a.fetchall()
        await cursor_a.close()

        # Verify none appear in Agent B's database
        for session in agent_a_sessions:
            cursor_b = await agent_b_conn.execute(
                "SELECT id FROM agent_sessions WHERE gateway_session_id = ?",
                (session[0],),
            )
            agent_b_session = await cursor_b.fetchone()
            await cursor_b.close()

            assert agent_b_session is None, (
                f"Session leak detected: {session[0]} found in both {agent_a} and {agent_b} databases"
            )

        return True

    async def verify_session_context_isolation(
        self, session_x_id: str, session_y_id: str, agent_name: str
    ):
        """Verify that two sessions for the same agent have isolated contexts"""

        # Get messages for both sessions from agent database
        messages_x = await self.get_agent_messages(agent_name, session_x_id)
        messages_y = await self.get_agent_messages(agent_name, session_y_id)

        # Verify sessions exist and have different content
        assert len(messages_x) > 0, f"No messages found for session {session_x_id}"
        assert len(messages_y) > 0, f"No messages found for session {session_y_id}"

        # Extract content from both sessions
        content_x = " ".join([msg.content for msg in messages_x])
        content_y = " ".join([msg.content for msg in messages_y])

        # Verify they are different (basic check for isolation)
        assert content_x != content_y, (
            f"Session content appears to be identical between {session_x_id} and {session_y_id}"
        )

        return {
            "session_x_messages": len(messages_x),
            "session_y_messages": len(messages_y),
            "content_isolated": True,
        }

    async def get_database_stats(self) -> dict:
        """Get statistics about all databases for debugging"""
        stats = {}

        # Gateway stats
        gateway_conn = await self.db_manager.get_gateway_connection()
        cursor = await gateway_conn.execute("SELECT COUNT(*) FROM gateway_sessions")
        session_count = await cursor.fetchone()
        await cursor.close()

        cursor = await gateway_conn.execute("SELECT COUNT(*) FROM gateway_messages")
        message_count = await cursor.fetchone()
        await cursor.close()

        stats["gateway"] = {"sessions": session_count[0], "messages": message_count[0]}

        # Agent stats
        for agent_name in self.db_manager.agent_db_urls.keys():
            agent_conn = await self.db_manager.get_agent_connection(agent_name)

            cursor = await agent_conn.execute("SELECT COUNT(*) FROM agent_sessions")
            agent_session_count = await cursor.fetchone()
            await cursor.close()

            cursor = await agent_conn.execute("SELECT COUNT(*) FROM agent_messages")
            agent_message_count = await cursor.fetchone()
            await cursor.close()

            stats[f"agent_{agent_name}"] = {
                "sessions": agent_session_count[0],
                "messages": agent_message_count[0],
            }

        return stats
