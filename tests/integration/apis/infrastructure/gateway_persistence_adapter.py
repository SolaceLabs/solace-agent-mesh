"""
Gateway Persistence Adapter that wraps TestGatewayComponent with API-like interface.

Provides HTTP-like API methods while using the existing TestGatewayComponent infrastructure
with real database persistence.
"""

import uuid
from typing import Any, NamedTuple

from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent

from .multi_database_manager import MultiDatabaseManager


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


class GatewayPersistenceAdapter:
    """Wraps TestGatewayComponent to provide API-like interface with real persistence"""

    def __init__(
        self,
        test_gateway_component: TestGatewayComponent,
        db_manager: MultiDatabaseManager,
    ):
        self.gateway = test_gateway_component
        self.db_manager = db_manager

    async def create_session(self, user_id: str, agent_name: str) -> SessionResponse:
        """API-like session creation with database persistence"""

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Store session in Gateway database
        gateway_conn = await self.db_manager.get_gateway_connection()
        await gateway_conn.execute(
            "INSERT INTO gateway_sessions (id, user_id, agent_name) VALUES (?, ?, ?)",
            (session_id, user_id, agent_name),
        )
        await gateway_conn.commit()

        return SessionResponse(id=session_id, user_id=user_id, agent_name=agent_name)

    async def send_message(
        self, session_id: str, message: str, user_id: str | None = None
    ) -> MessageResponse:
        """API-like message sending with database persistence"""

        # Get session info if user_id not provided
        if not user_id:
            gateway_conn = await self.db_manager.get_gateway_connection()
            cursor = await gateway_conn.execute(
                "SELECT user_id, agent_name FROM gateway_sessions WHERE id = ?",
                (session_id,),
            )
            session_row = await cursor.fetchone()
            await cursor.close()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            user_id, agent_name = session_row
        else:
            # Get agent name for this session
            gateway_conn = await self.db_manager.get_gateway_connection()
            cursor = await gateway_conn.execute(
                "SELECT agent_name FROM gateway_sessions WHERE id = ?", (session_id,)
            )
            agent_row = await cursor.fetchone()
            await cursor.close()

            if not agent_row:
                raise ValueError(f"Session {session_id} not found")

            agent_name = agent_row[0]

        # Store user message in Gateway database
        gateway_conn = await self.db_manager.get_gateway_connection()
        await gateway_conn.execute(
            "INSERT INTO gateway_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "user", message),
        )
        await gateway_conn.commit()

        # Create gateway input data structure (using existing patterns)
        gateway_input_data = {
            "target_agent_name": agent_name,
            "user_identity": user_id,
            "external_context": {"a2a_session_id": session_id},
            "user_request": {"parts": [{"type": "text", "text": message}]},
        }

        # Send through existing TestGatewayComponent
        task_id = await self.gateway.send_test_input(gateway_input_data)

        # For now, we'll simulate getting the response content
        # In a real implementation, we'd wait for the task completion and extract the response
        # Here we'll check if there are any captured outputs

        # Simulate agent response (in real implementation, this would come from the actual agent)
        agent_response = f"Received: {message}"

        # Store agent response in Gateway database
        await gateway_conn.execute(
            "INSERT INTO gateway_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "assistant", agent_response),
        )
        await gateway_conn.commit()

        return MessageResponse(
            content=agent_response, session_id=session_id, task_id=task_id
        )

    async def switch_session(self, session_id: str) -> SessionResponse:
        """API-like session switching"""

        # Verify session exists
        gateway_conn = await self.db_manager.get_gateway_connection()
        cursor = await gateway_conn.execute(
            "SELECT id, user_id, agent_name FROM gateway_sessions WHERE id = ?",
            (session_id,),
        )
        session_row = await cursor.fetchone()
        await cursor.close()

        if not session_row:
            raise ValueError(f"Session {session_id} not found")

        # Update session timestamp to indicate it was accessed
        await gateway_conn.execute(
            "UPDATE gateway_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,),
        )
        await gateway_conn.commit()

        return SessionResponse(
            id=session_row[0], user_id=session_row[1], agent_name=session_row[2]
        )

    async def list_sessions(self, user_id: str) -> list[SessionResponse]:
        """List all sessions for a user"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        cursor = await gateway_conn.execute(
            "SELECT id, user_id, agent_name FROM gateway_sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        session_rows = await cursor.fetchall()
        await cursor.close()

        return [
            SessionResponse(id=row[0], user_id=row[1], agent_name=row[2])
            for row in session_rows
        ]

    async def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        cursor = await gateway_conn.execute(
            "SELECT role, content, timestamp FROM gateway_messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        message_rows = await cursor.fetchall()
        await cursor.close()

        return [
            {"role": row[0], "content": row[1], "timestamp": row[2]}
            for row in message_rows
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages"""

        gateway_conn = await self.db_manager.get_gateway_connection()

        # Delete messages first (foreign key constraint)
        await gateway_conn.execute(
            "DELETE FROM gateway_messages WHERE session_id = ?", (session_id,)
        )

        # Delete session
        cursor = await gateway_conn.execute(
            "DELETE FROM gateway_sessions WHERE id = ?", (session_id,)
        )

        await gateway_conn.commit()

        # Return True if a session was actually deleted
        return cursor.rowcount > 0
