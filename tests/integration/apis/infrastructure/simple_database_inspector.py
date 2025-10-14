"""
Simple database inspector using SQLAlchemy Core.

A simplified version that uses SQLAlchemy for database-agnostic inspection.
"""

import sqlalchemy as sa
from typing import NamedTuple

from .simple_database_manager import SimpleDatabaseManager


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


class SimpleDatabaseInspector:
    """Provides inspection across Gateway and Agent databases using SQLAlchemy"""

    def __init__(self, db_manager: SimpleDatabaseManager):
        self.db_manager = db_manager

    def verify_gateway_migration_state(self) -> str:
        """Verify Gateway database has proper migration state"""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            alembic_table = metadata.tables.get("alembic_version")
            assert alembic_table is not None, "Alembic version table not found"

            query = sa.select(alembic_table.c.version_num)
            result = conn.execute(query).scalar_one_or_none()

        assert result is not None, "Gateway database migrations not applied"
        return result

    def verify_agent_schema_state(self, agent_name: str) -> list[str]:
        """Verify Agent database has proper schema (no migrations)"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            inspector = sa.inspect(conn)
            table_names = inspector.get_table_names()

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
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["gateway_sessions"]

            query = sa.select(sessions_table).where(sessions_table.c.user_id == user_id)
            rows = conn.execute(query).fetchall()

        return [SessionRecord(*row) for row in rows]

    def get_session_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a gateway session"""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            messages_table = metadata.tables["gateway_messages"]

            query = (
                sa.select(messages_table)
                .where(messages_table.c.session_id == session_id)
                .order_by(messages_table.c.timestamp)
            )
            rows = conn.execute(query).fetchall()

        return [MessageRecord(*row) for row in rows]

    def get_agent_sessions(
        self, agent_name: str, gateway_session_id: str | None = None
    ) -> list[AgentSessionRecord]:
        """Get agent sessions, optionally filtered by gateway session ID"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            agent_sessions_table = metadata.tables["agent_sessions"]

            query = sa.select(agent_sessions_table)
            if gateway_session_id:
                query = query.where(
                    agent_sessions_table.c.gateway_session_id == gateway_session_id
                )

            rows = conn.execute(query).fetchall()

        return [AgentSessionRecord(*row) for row in rows]

    def get_agent_messages(
        self, agent_name: str, gateway_session_id: str
    ) -> list[MessageRecord]:
        """Get all messages for an agent session"""
        with self.db_manager.get_agent_connection(agent_name) as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
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
            rows = conn.execute(query).fetchall()

        return [MessageRecord(*row) for row in rows]

    def verify_session_linking(self, gateway_session_id: str, agent_name: str):
        """Verify session exists in both Gateway and Agent databases"""
        
        # Check Gateway database
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            gateway_sessions = metadata.tables["gateway_sessions"]
            
            query = sa.select(gateway_sessions).where(gateway_sessions.c.id == gateway_session_id)
            gateway_session = conn.execute(query).fetchone()

        # Check Agent database
        with self.db_manager.get_agent_connection(agent_name) as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            agent_sessions = metadata.tables["agent_sessions"]

            query = sa.select(agent_sessions).where(agent_sessions.c.gateway_session_id == gateway_session_id)
            agent_session = conn.execute(query).fetchone()

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

    def verify_database_isolation(self, agent_a: str, agent_b: str) -> bool:
        """Verify Agent A's data doesn't appear in Agent B's database"""

        # Get all sessions from Agent A
        with self.db_manager.get_agent_connection(agent_a) as conn_a:
            metadata_a = sa.MetaData()
            metadata_a.reflect(bind=conn_a)
            sessions_a = metadata_a.tables["agent_sessions"]
            
            query_a = sa.select(sessions_a.c.gateway_session_id)
            agent_a_sessions = conn_a.execute(query_a).fetchall()

        # Verify none appear in Agent B's database
        with self.db_manager.get_agent_connection(agent_b) as conn_b:
            metadata_b = sa.MetaData()
            metadata_b.reflect(bind=conn_b)
            sessions_b = metadata_b.tables["agent_sessions"]

            for session_id, in agent_a_sessions:
                query_b = sa.select(sessions_b).where(sessions_b.c.gateway_session_id == session_id)
                result = conn_b.execute(query_b).first()

                assert result is None, (
                    f"Session leak detected: {session_id} found in both {agent_a} and {agent_b} databases"
                )

        return True

    def get_database_stats(self) -> dict:
        """Get statistics about all databases for debugging"""
        stats = {}

        # Gateway stats
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            
            sessions_table = metadata.tables.get("gateway_sessions")
            messages_table = metadata.tables.get("gateway_messages")

            session_count = conn.execute(sa.select(sa.func.count()).select_from(sessions_table)).scalar() if sessions_table is not None else 0
            message_count = conn.execute(sa.select(sa.func.count()).select_from(messages_table)).scalar() if messages_table is not None else 0

            stats["gateway"] = {"sessions": session_count, "messages": message_count}

        # Agent stats
        for agent_name in self.db_manager.agent_db_paths.keys():
            with self.db_manager.get_agent_connection(agent_name) as conn:
                metadata = sa.MetaData()
                metadata.reflect(bind=conn)

                agent_sessions_table = metadata.tables.get("agent_sessions")
                agent_messages_table = metadata.tables.get("agent_messages")

                agent_session_count = conn.execute(sa.select(sa.func.count()).select_from(agent_sessions_table)).scalar() if agent_sessions_table is not None else 0
                agent_message_count = conn.execute(sa.select(sa.func.count()).select_from(agent_messages_table)).scalar() if agent_messages_table is not None else 0

                stats[f"agent_{agent_name}"] = {
                    "sessions": agent_session_count,
                    "messages": agent_message_count,
                }

        return stats
