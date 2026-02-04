"""
Generic Database Inspector for the API testing framework.
"""

import sqlalchemy as sa

from src.solace_agent_mesh.gateway.http_sse.routers.dto.responses.session_responses import (
    SessionResponse,
)
from src.solace_agent_mesh.gateway.http_sse.routers.dto.responses.task_responses import (
    TaskResponse,
)

from .database_manager import DatabaseManager


class DatabaseInspector:
    """A generic database inspector that uses the new DatabaseManager."""

    def __init__(self, db_manager: DatabaseManager):
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
        gateway_version = self.verify_gateway_migration_state()
        agent_schemas = {}
        for agent_name in agent_names:
            agent_schemas[agent_name] = self.verify_agent_schema_state(agent_name)

        return {
            "gateway_migration_version": gateway_version,
            "agent_schemas": agent_schemas,
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

            for (session_id,) in agent_a_sessions:
                query_b = sa.select(sessions_b).where(
                    sessions_b.c.gateway_session_id == session_id
                )
                result = conn_b.execute(query_b).first()

                assert result is None, (
                    f"Session leak detected: {session_id} found in both {agent_a} and {agent_b} databases"
                )

        return True

    def get_gateway_sessions(self, user_id: str) -> list[SessionResponse]:
        """Get all gateway sessions for a user."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            query = sa.select(sessions_table).where(sessions_table.c.user_id == user_id)
            rows = conn.execute(query).fetchall()
        return [SessionResponse.model_validate(row._asdict()) for row in rows]

    def get_session_messages(self, session_id: str) -> list[TaskResponse]:
        """Get all messages for a gateway session."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            messages_table = metadata.tables["chat_tasks"]
            query = (
                sa.select(messages_table)
                .where(messages_table.c.session_id == session_id)
                .order_by(messages_table.c.created_time)
            )
            rows = conn.execute(query).fetchall()

        tasks = []
        for row in rows:
            task_data = {
                "task_id": row.id,
                "session_id": row.session_id,
                "user_message": row.user_message,
                "message_bubbles": row.message_bubbles,
                "task_metadata": row.task_metadata,
                "created_time": row.created_time,
                "updated_time": row.updated_time,
            }
            tasks.append(TaskResponse.model_validate(task_data))
        return tasks

    def get_database_stats(self, agent_names: list[str] = None) -> dict:
        """Get statistics about all databases for debugging."""
        stats = {}

        # Gateway stats
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            messages_table = metadata.tables["chat_tasks"]

            session_count = conn.execute(
                sa.select(sa.func.count()).select_from(sessions_table)
            ).scalar_one()
            message_count = conn.execute(
                sa.select(sa.func.count()).select_from(messages_table)
            ).scalar_one()

        stats["gateway"] = {"sessions": session_count, "messages": message_count}

        # Agent stats
        if agent_names is None:
            # Try to get agent names from provider if available
            if hasattr(self.db_manager.provider, "_sync_engines"):
                agent_names = [
                    name
                    for name in self.db_manager.provider._sync_engines
                    if name != "gateway"
                ]
            else:
                # Fallback to empty list if no agent names provided and can't detect
                agent_names = []

        for agent_name in agent_names:
            try:
                with self.db_manager.get_agent_connection(agent_name) as conn:
                    metadata = sa.MetaData()
                    metadata.reflect(bind=conn)
                    sessions_table = metadata.tables["agent_sessions"]
                    messages_table = metadata.tables["agent_messages"]

                    agent_session_count = conn.execute(
                        sa.select(sa.func.count()).select_from(sessions_table)
                    ).scalar_one()
                    agent_message_count = conn.execute(
                        sa.select(sa.func.count()).select_from(messages_table)
                    ).scalar_one()

                    stats[f"agent_{agent_name}"] = {
                        "sessions": agent_session_count,
                        "messages": agent_message_count,
                    }
            except Exception:
                # If agent database doesn't exist or can't be accessed, skip it
                continue

        return stats
