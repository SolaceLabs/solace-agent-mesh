"""
Cross-database inspector for validation across Gateway and Agent databases.

Provides utilities to verify database state, session linking, and architecture correctness.
"""

import sqlalchemy as sa
from typing import NamedTuple

from .multi_database_manager import MultiDatabaseManager


class SessionRecord(NamedTuple):
    """Represents a session record from database"""

    id: str
    user_id: str
    agent_name: str
    created_at: str
    updated_at: str


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

    async def verify_gateway_migration_state(self) -> str:
        """Verify Gateway database has proper migration state"""
        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            alembic_table = metadata.tables.get("alembic_version")
            assert alembic_table is not None, "Alembic version table not found"

            query = sa.select(alembic_table.c.version_num)
            result = (await gateway_conn.execute(query)).scalar_one_or_none()

        assert result is not None, "Gateway database migrations not applied"
        return result

    async def verify_agent_schema_state(self, agent_name: str) -> list[str]:
        """Verify Agent database has proper schema (no migrations)"""
        agent_conn = await self.db_manager.get_agent_connection(agent_name)
        async with agent_conn.begin():
            table_names = await agent_conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).get_table_names()
            )

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
        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            sessions_table = metadata.tables["gateway_sessions"]

            query = sa.select(sessions_table).where(sessions_table.c.user_id == user_id)
            result = await gateway_conn.execute(query)
            rows = result.fetchall()

        return [SessionRecord(*row) for row in rows]

    async def get_session_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a gateway session"""
        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            messages_table = metadata.tables["gateway_messages"]

            query = (
                sa.select(messages_table)
                .where(messages_table.c.session_id == session_id)
                .order_by(messages_table.c.timestamp)
            )
            result = await gateway_conn.execute(query)
            rows = result.fetchall()

        return [MessageRecord(*row) for row in rows]

    async def get_agent_sessions(
        self, agent_name: str, gateway_session_id: str | None = None
    ) -> list[AgentSessionRecord]:
        """Get agent sessions, optionally filtered by gateway session ID"""
        agent_conn = await self.db_manager.get_agent_connection(agent_name)
        async with agent_conn.begin():
            metadata = sa.MetaData()
            await agent_conn.run_sync(metadata.reflect)
            agent_sessions_table = metadata.tables["agent_sessions"]

            query = sa.select(agent_sessions_table)
            if gateway_session_id:
                query = query.where(
                    agent_sessions_table.c.gateway_session_id == gateway_session_id
                )

            result = await agent_conn.execute(query)
            rows = result.fetchall()

        return [AgentSessionRecord(*row) for row in rows]

    async def get_agent_messages(
        self, agent_name: str, gateway_session_id: str
    ) -> list[MessageRecord]:
        """Get all messages for an agent session"""
        agent_conn = await self.db_manager.get_agent_connection(agent_name)
        async with agent_conn.begin():
            metadata = sa.MetaData()
            await agent_conn.run_sync(metadata.reflect)
            agent_messages_table = metadata.tables["agent_messages"]

            query = (
                sa.select(
                    agent_messages_table.c.id,
                    agent_messages_table.c.gateway_session_id.label("session_id"),
                    agent_messages_table.c.role,
                    agent_messages_table.c.content,
                    agent_messages_table.c.timestamp,
                )
                .where(agent_messages_table.c.gateway_session_id == gateway_session_id)
                .order_by(agent_messages_table.c.timestamp)
            )
            result = await agent_conn.execute(query)
            rows = result.fetchall()

        return [MessageRecord(*row) for row in rows]

    async def verify_session_linking(self, gateway_session_id: str, agent_name: str):
        """Verify session exists in both Gateway and Agent databases"""

        # Check Gateway database
        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            gateway_sessions = metadata.tables["gateway_sessions"]
            
            query = sa.select(gateway_sessions).where(gateway_sessions.c.id == gateway_session_id)
            gateway_session = (await gateway_conn.execute(query)).first()

        # Check Agent database
        agent_conn = await self.db_manager.get_agent_connection(agent_name)
        async with agent_conn.begin():
            metadata = sa.MetaData()
            await agent_conn.run_sync(metadata.reflect)
            agent_sessions = metadata.tables["agent_sessions"]

            query = sa.select(agent_sessions).where(agent_sessions.c.gateway_session_id == gateway_session_id)
            agent_session = (await agent_conn.execute(query)).first()

        assert gateway_session is not None, (
            f"Gateway session {gateway_session_id} not found"
        )
        assert agent_session is not None, (
            f"Agent session for {gateway_session_id} not found in {agent_name}"
        )
        assert agent_session.gateway_session_id == gateway_session_id, (
            "Session ID mismatch in agent database"
        )
        assert agent_session.agent_name == agent_name, "Agent name mismatch in agent database"
        assert gateway_session.user_id == agent_session.user_id, (
            "User ID mismatch between Gateway and Agent"
        )

        return {
            "gateway_session": SessionRecord(
                gateway_session.id, gateway_session.user_id, gateway_session.agent_name, "", ""
            ),
            "agent_session": AgentSessionRecord(*agent_session),
        }

    async def verify_database_isolation(self, agent_a: str, agent_b: str) -> bool:
        """Verify Agent A's data doesn't appear in Agent B's database"""

        # Get all sessions from Agent A
        agent_a_conn = await self.db_manager.get_agent_connection(agent_a)
        async with agent_a_conn.begin():
            metadata_a = sa.MetaData()
            await agent_a_conn.run_sync(metadata_a.reflect)
            sessions_a = metadata_a.tables["agent_sessions"]
            
            query_a = sa.select(sessions_a.c.gateway_session_id)
            result_a = await agent_a_conn.execute(query_a)
            agent_a_sessions = result_a.fetchall()

        # Verify none appear in Agent B's database
        agent_b_conn = await self.db_manager.get_agent_connection(agent_b)
        async with agent_b_conn.begin():
            metadata_b = sa.MetaData()
            await agent_b_conn.run_sync(metadata_b.reflect)
            sessions_b = metadata_b.tables["agent_sessions"]

            for session_id, in agent_a_sessions:
                query_b = sa.select(sessions_b).where(sessions_b.c.gateway_session_id == session_id)
                result_b = await agent_b_conn.execute(query_b)
                agent_b_session = result_b.first()

                assert agent_b_session is None, (
                    f"Session leak detected: {session_id} found in both {agent_a} and {agent_b} databases"
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
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            
            sessions_table = metadata.tables.get("gateway_sessions")
            messages_table = metadata.tables.get("gateway_messages")

            session_count = (await gateway_conn.execute(sa.select(sa.func.count()).select_from(sessions_table))).scalar() if sessions_table is not None else 0
            message_count = (await gateway_conn.execute(sa.select(sa.func.count()).select_from(messages_table))).scalar() if messages_table is not None else 0

            stats["gateway"] = {"sessions": session_count, "messages": message_count}

        # Agent stats
        for agent_name in self.db_manager.agent_db_urls.keys():
            agent_conn = await self.db_manager.get_agent_connection(agent_name)
            async with agent_conn.begin():
                metadata = sa.MetaData()
                await agent_conn.run_sync(metadata.reflect)

                agent_sessions_table = metadata.tables.get("agent_sessions")
                agent_messages_table = metadata.tables.get("agent_messages")

                agent_session_count = (await agent_conn.execute(sa.select(sa.func.count()).select_from(agent_sessions_table))).scalar() if agent_sessions_table is not None else 0
                agent_message_count = (await agent_conn.execute(sa.select(sa.func.count()).select_from(agent_messages_table))).scalar() if agent_messages_table is not None else 0

                stats[f"agent_{agent_name}"] = {
                    "sessions": agent_session_count,
                    "messages": agent_message_count,
                }

        return stats
