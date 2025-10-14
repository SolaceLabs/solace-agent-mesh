"""
Simple Gateway Persistence Adapter using SQLAlchemy Core.

A simplified version that uses SQLAlchemy for database-agnostic persistence.
"""

import uuid
import sqlalchemy as sa
from typing import NamedTuple
from sqlalchemy import text

from .simple_database_manager import SimpleDatabaseManager


class SessionResponse(NamedTuple):
    """Response from session creation"""

    id: str
    user_id: str
    agent_name: str


class MessageResponse(NamedTuple):
    """Response from message sending"""

    content: str
    session_id: str
    task_id: str | None = None


class SimpleGatewayAdapter:
    """Simple gateway adapter with SQLite persistence"""

    def __init__(self, db_manager: SimpleDatabaseManager):
        self.db_manager = db_manager

    def create_session(self, user_id: str, agent_name: str) -> SessionResponse:
        """Create a new session with database persistence"""

        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        if not agent_name or not agent_name.strip():
            raise ValueError("agent_name cannot be empty")

        session_id = str(uuid.uuid4())

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["gateway_sessions"]

            query = sa.insert(sessions_table).values(
                id=session_id, user_id=user_id, agent_name=agent_name
            )
            conn.execute(query)
            if conn.in_transaction():
                conn.commit()

        return SessionResponse(id=session_id, user_id=user_id, agent_name=agent_name)

    def send_message(
        self, session_id: str, message: str, user_id: str | None = None
    ) -> MessageResponse:
        """Send a message with database persistence"""

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["gateway_sessions"]
            messages_table = metadata.tables["gateway_messages"]

            # Get session info
            query = sa.select(sessions_table.c.user_id, sessions_table.c.agent_name).where(
                sessions_table.c.id == session_id
            )
            session_row = conn.execute(query).first()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")
            
            # Store user message
            insert_user_msg = sa.insert(messages_table).values(
                session_id=session_id, role="user", content=message
            )
            conn.execute(insert_user_msg)

            # Simulate and store agent response
            agent_response = f"Received: {message}"
            insert_agent_msg = sa.insert(messages_table).values(
                session_id=session_id, role="assistant", content=agent_response
            )
            conn.execute(insert_agent_msg)

            if conn.in_transaction():
                conn.commit()

        return MessageResponse(
            content=agent_response, session_id=session_id, task_id="simulated_task_id"
        )

    def switch_session(self, session_id: str) -> SessionResponse:
        """Switch to an existing session"""

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["gateway_sessions"]

            # Verify session exists
            query = sa.select(sessions_table).where(sessions_table.c.id == session_id)
            session_row = conn.execute(query).first()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            # Update session timestamp
            update_query = (
                sa.update(sessions_table)
                .where(sessions_table.c.id == session_id)
                .values(updated_at=sa.func.current_timestamp())
            )
            conn.execute(update_query)
            if conn.in_transaction():
                conn.commit()

        return SessionResponse(
            id=session_row.id, user_id=session_row.user_id, agent_name=session_row.agent_name
        )

    def list_sessions(self, user_id: str) -> list[SessionResponse]:
        """List all sessions for a user"""

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["gateway_sessions"]

            query = (
                sa.select(sessions_table)
                .where(sessions_table.c.user_id == user_id)
                .order_by(sa.desc(sessions_table.c.updated_at))
            )
            session_rows = conn.execute(query).fetchall()

        return [
            SessionResponse(id=row.id, user_id=row.user_id, agent_name=row.agent_name)
            for row in session_rows
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages"""

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            messages_table = metadata.tables["gateway_messages"]
            sessions_table = metadata.tables["gateway_sessions"]

            # Delete messages first
            delete_msgs = sa.delete(messages_table).where(
                messages_table.c.session_id == session_id
            )
            conn.execute(delete_msgs)

            # Delete session
            delete_sess = sa.delete(sessions_table).where(
                sessions_table.c.id == session_id
            )
            result = conn.execute(delete_sess)

            if conn.in_transaction():
                conn.commit()

            return result.rowcount > 0
