"""
Gateway Persistence Adapter that wraps TestGatewayComponent with API-like interface.

Provides HTTP-like API methods while using the existing TestGatewayComponent infrastructure
with real database persistence.
"""

import uuid
import sqlalchemy as sa
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

        session_id = str(uuid.uuid4())

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            sessions_table = metadata.tables["gateway_sessions"]

            query = sa.insert(sessions_table).values(
                id=session_id, user_id=user_id, agent_name=agent_name
            )
            await gateway_conn.execute(query)

        return SessionResponse(id=session_id, user_id=user_id, agent_name=agent_name)

    async def send_message(
        self, session_id: str, message: str, user_id: str | None = None
    ) -> MessageResponse:
        """API-like message sending with database persistence"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            sessions_table = metadata.tables["gateway_sessions"]
            messages_table = metadata.tables["gateway_messages"]

            # Get session info
            query = sa.select(sessions_table.c.user_id, sessions_table.c.agent_name).where(
                sessions_table.c.id == session_id
            )
            session_row = (await gateway_conn.execute(query)).first()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")
            
            user_id, agent_name = session_row

            # Store user message
            insert_user_msg = sa.insert(messages_table).values(
                session_id=session_id, role="user", content=message
            )
            await gateway_conn.execute(insert_user_msg)

            # Simulate agent response
            agent_response = f"Received: {message}"
            insert_agent_msg = sa.insert(messages_table).values(
                session_id=session_id, role="assistant", content=agent_response
            )
            await gateway_conn.execute(insert_agent_msg)

        # Create gateway input data structure
        gateway_input_data = {
            "target_agent_name": agent_name,
            "user_identity": user_id,
            "external_context": {"a2a_session_id": session_id},
            "user_request": {"parts": [{"type": "text", "text": message}]},
        }

        task_id = await self.gateway.send_test_input(gateway_input_data)

        return MessageResponse(
            content=agent_response, session_id=session_id, task_id=task_id
        )

    async def switch_session(self, session_id: str) -> SessionResponse:
        """API-like session switching"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            sessions_table = metadata.tables["gateway_sessions"]

            # Verify session exists
            query = sa.select(sessions_table).where(sessions_table.c.id == session_id)
            session_row = (await gateway_conn.execute(query)).first()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            # Update session timestamp
            update_query = (
                sa.update(sessions_table)
                .where(sessions_table.c.id == session_id)
                .values(updated_at=sa.func.current_timestamp())
            )
            await gateway_conn.execute(update_query)

        return SessionResponse(
            id=session_row.id, user_id=session_row.user_id, agent_name=session_row.agent_name
        )

    async def list_sessions(self, user_id: str) -> list[SessionResponse]:
        """List all sessions for a user"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            sessions_table = metadata.tables["gateway_sessions"]

            query = (
                sa.select(sessions_table)
                .where(sessions_table.c.user_id == user_id)
                .order_by(sa.desc(sessions_table.c.updated_at))
            )
            result = await gateway_conn.execute(query)
            session_rows = result.fetchall()

        return [
            SessionResponse(id=row.id, user_id=row.user_id, agent_name=row.agent_name)
            for row in session_rows
        ]

    async def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            messages_table = metadata.tables["gateway_messages"]

            query = (
                sa.select(messages_table.c.role, messages_table.c.content, messages_table.c.timestamp)
                .where(messages_table.c.session_id == session_id)
                .order_by(messages_table.c.timestamp)
            )
            result = await gateway_conn.execute(query)
            message_rows = result.fetchall()

        return [
            {"role": row.role, "content": row.content, "timestamp": row.timestamp}
            for row in message_rows
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages"""

        gateway_conn = await self.db_manager.get_gateway_connection()
        async with gateway_conn.begin():
            metadata = sa.MetaData()
            await gateway_conn.run_sync(metadata.reflect)
            messages_table = metadata.tables["gateway_messages"]
            sessions_table = metadata.tables["gateway_sessions"]

            # Delete messages first
            delete_msgs = sa.delete(messages_table).where(
                messages_table.c.session_id == session_id
            )
            await gateway_conn.execute(delete_msgs)

            # Delete session
            delete_sess = sa.delete(sessions_table).where(
                sessions_table.c.id == session_id
            )
            result = await gateway_conn.execute(delete_sess)

            return result.rowcount > 0
