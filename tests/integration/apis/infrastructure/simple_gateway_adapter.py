"""
Simple Gateway Persistence Adapter using synchronous SQLite.

A simplified version that uses standard sqlite3 to avoid dependency issues.
"""

import uuid
from typing import NamedTuple

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

        # Validate input parameters
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        if not agent_name or not agent_name.strip():
            raise ValueError("agent_name cannot be empty")

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Store session in Gateway database
        with self.db_manager.get_gateway_connection() as conn:
            conn.execute(
                "INSERT INTO gateway_sessions (id, user_id, agent_name) VALUES (?, ?, ?)",
                (session_id, user_id, agent_name),
            )
            conn.commit()

        return SessionResponse(id=session_id, user_id=user_id, agent_name=agent_name)

    def send_message(
        self, session_id: str, message: str, user_id: str | None = None
    ) -> MessageResponse:
        """Send a message with database persistence"""

        # Get session info if user_id not provided
        if not user_id:
            with self.db_manager.get_gateway_connection() as conn:
                cursor = conn.execute(
                    "SELECT user_id, agent_name FROM gateway_sessions WHERE id = ?",
                    (session_id,),
                )
                session_row = cursor.fetchone()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            user_id, agent_name = session_row
        else:
            # Get agent name for this session
            with self.db_manager.get_gateway_connection() as conn:
                cursor = conn.execute(
                    "SELECT agent_name FROM gateway_sessions WHERE id = ?",
                    (session_id,),
                )
                agent_row = cursor.fetchone()

            if not agent_row:
                raise ValueError(f"Session {session_id} not found")

            agent_name = agent_row[0]

        # Store user message in Gateway database
        with self.db_manager.get_gateway_connection() as conn:
            conn.execute(
                "INSERT INTO gateway_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "user", message),
            )
            conn.commit()

        # Simulate agent response (in real implementation, this would come from the actual agent)
        agent_response = f"Received: {message}"

        # Store agent response in Gateway database
        with self.db_manager.get_gateway_connection() as conn:
            conn.execute(
                "INSERT INTO gateway_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "assistant", agent_response),
            )
            conn.commit()

        return MessageResponse(
            content=agent_response, session_id=session_id, task_id="simulated_task_id"
        )

    def switch_session(self, session_id: str) -> SessionResponse:
        """Switch to an existing session"""

        # Verify session exists
        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute(
                "SELECT id, user_id, agent_name FROM gateway_sessions WHERE id = ?",
                (session_id,),
            )
            session_row = cursor.fetchone()

        if not session_row:
            raise ValueError(f"Session {session_id} not found")

        # Update session timestamp to indicate it was accessed
        with self.db_manager.get_gateway_connection() as conn:
            conn.execute(
                "UPDATE gateway_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()

        return SessionResponse(
            id=session_row[0], user_id=session_row[1], agent_name=session_row[2]
        )

    def list_sessions(self, user_id: str) -> list[SessionResponse]:
        """List all sessions for a user"""

        with self.db_manager.get_gateway_connection() as conn:
            cursor = conn.execute(
                "SELECT id, user_id, agent_name FROM gateway_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
            session_rows = cursor.fetchall()

        return [
            SessionResponse(id=row[0], user_id=row[1], agent_name=row[2])
            for row in session_rows
        ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages"""

        with self.db_manager.get_gateway_connection() as conn:
            # Delete messages first (foreign key constraint)
            conn.execute(
                "DELETE FROM gateway_messages WHERE session_id = ?", (session_id,)
            )

            # Delete session
            cursor = conn.execute(
                "DELETE FROM gateway_sessions WHERE id = ?", (session_id,)
            )

            conn.commit()

            # Return True if a session was actually deleted
            return cursor.rowcount > 0
