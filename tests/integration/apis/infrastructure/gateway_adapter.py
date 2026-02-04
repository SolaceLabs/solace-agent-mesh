"""
Generic Gateway Adapter for the API testing framework.
"""

import json
import uuid

import sqlalchemy as sa

from src.solace_agent_mesh.gateway.http_sse.routers.dto.responses.session_responses import (
    SessionResponse,
)
from src.solace_agent_mesh.gateway.http_sse.routers.dto.responses.task_responses import (
    TaskResponse,
)
from src.solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

from .database_manager import DatabaseManager


class GatewayAdapter:
    """A generic gateway adapter that uses the new DatabaseManager."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_session(self, user_id: str, agent_name: str) -> SessionResponse:
        """Create a new session using the configured gateway database."""
        session_id = str(uuid.uuid4())
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            now = now_epoch_ms()
            query = sa.insert(sessions_table).values(
                id=session_id,
                user_id=user_id,
                name=agent_name,
                agent_id=agent_name,
                created_time=now,
                updated_time=now,
            )
            conn.execute(query)
            if conn.in_transaction():
                conn.commit()

            select_query = sa.select(sessions_table).where(
                sessions_table.c.id == session_id
            )
            created_session = conn.execute(select_query).first()

        return SessionResponse.model_validate(created_session._asdict())

    def send_message(self, session_id: str, message: str) -> TaskResponse:
        """Send a message and persist it, returning a TaskResponse."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            messages_table = metadata.tables["chat_tasks"]

            # Get user_id from session
            select_user_query = sa.select(sessions_table.c.user_id).where(
                sessions_table.c.id == session_id
            )
            user_id = conn.execute(select_user_query).scalar()

            if not user_id:
                raise ValueError(f"Session {session_id} not found")

            # Store user message
            now = now_epoch_ms()
            user_bubbles = json.dumps([{"role": "user", "text": message}])
            insert_user_msg = sa.insert(messages_table).values(
                id=task_id,
                session_id=session_id,
                user_id=user_id,
                user_message=message,
                message_bubbles=user_bubbles,
                task_metadata=json.dumps({"simulated": True}),
                created_time=now,
                updated_time=now,
            )
            conn.execute(insert_user_msg)

            # Simulate and store agent response
            agent_response_content = f"Received: {message}"
            agent_task_id = f"task-{uuid.uuid4().hex[:8]}"
            # Ensure agent message has a later timestamp than user message for consistent ordering
            now = now_epoch_ms() + 1
            agent_bubbles = json.dumps(
                [{"role": "assistant", "text": agent_response_content}]
            )
            insert_agent_msg = sa.insert(messages_table).values(
                id=agent_task_id,
                session_id=session_id,
                user_id=user_id,
                user_message=agent_response_content,
                message_bubbles=agent_bubbles,
                task_metadata=json.dumps({"simulated": True}),
                created_time=now,
                updated_time=now,
            )
            conn.execute(insert_agent_msg)

            if conn.in_transaction():
                conn.commit()

            # Fetch the created task to return a real response
            select_query = sa.select(messages_table).where(
                messages_table.c.id == task_id
            )
            created_task = conn.execute(select_query).first()

        # Map to the Pydantic model fields
        task_data = {
            "task_id": created_task.id,
            "session_id": created_task.session_id,
            "user_message": created_task.user_message,
            "message_bubbles": created_task.message_bubbles,
            "task_metadata": created_task.task_metadata,
            "created_time": created_task.created_time,
            "updated_time": created_task.updated_time,
        }
        return TaskResponse.model_validate(task_data)

    def list_sessions(self, user_id: str) -> list[SessionResponse]:
        """List all sessions for a user."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            query = sa.select(sessions_table).where(sessions_table.c.user_id == user_id)
            rows = conn.execute(query).fetchall()
        return [SessionResponse.model_validate(row._asdict()) for row in rows]

    def switch_session(self, session_id: str) -> SessionResponse:
        """Switch to an existing session."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            query = sa.select(sessions_table).where(sessions_table.c.id == session_id)
            session_row = conn.execute(query).first()
            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            update_query = (
                sa.update(sessions_table)
                .where(sessions_table.c.id == session_id)
                .values(updated_at=sa.func.current_timestamp())
            )
            conn.execute(update_query)
            if conn.in_transaction():
                conn.commit()

        return SessionResponse.model_validate(session_row._asdict())

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]
            messages_table = metadata.tables["chat_tasks"]

            # The ON DELETE CASCADE foreign key should handle this, but for explicit safety:
            delete_msgs = sa.delete(messages_table).where(
                messages_table.c.session_id == session_id
            )
            conn.execute(delete_msgs)

            delete_sess = sa.delete(sessions_table).where(
                sessions_table.c.id == session_id
            )
            result = conn.execute(delete_sess)

            if conn.in_transaction():
                conn.commit()

            return result.rowcount > 0

    def seed_project(
        self,
        project_id: str,
        name: str,
        user_id: str,
        description: str = None,
        system_prompt: str = None,
        default_agent_id: str = None,
    ) -> dict:
        """Seed a project in the database for testing."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            projects_table = metadata.tables["projects"]

            now = now_epoch_ms()
            query = sa.insert(projects_table).values(
                id=project_id,
                name=name,
                user_id=user_id,
                description=description,
                system_prompt=system_prompt,
                default_agent_id=default_agent_id,
                created_at=now,
                updated_at=now,
            )
            conn.execute(query)

            if conn.in_transaction():
                conn.commit()

            # Fetch the created project
            select_query = sa.select(projects_table).where(
                projects_table.c.id == project_id
            )
            created_project = conn.execute(select_query).first()

        return created_project._asdict() if created_project else None

    def seed_prompt_group(
        self,
        group_id: str,
        name: str,
        user_id: str,
        description: str = None,
        category: str = None,
        command: str = None,
        initial_prompt: str = None,
    ) -> dict:
        """Seed a prompt group with initial prompt in the database for testing."""
        with self.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            prompt_groups_table = metadata.tables["prompt_groups"]
            prompts_table = metadata.tables["prompts"]

            now = now_epoch_ms()
            
            # Create prompt group
            group_query = sa.insert(prompt_groups_table).values(
                id=group_id,
                name=name,
                user_id=user_id,
                description=description,
                category=category,
                command=command,
                author_name=None,
                production_prompt_id=None,
                is_shared=False,
                is_pinned=False,
                created_at=now,
                updated_at=now,
            )
            conn.execute(group_query)

            # Create initial prompt if provided
            prompt_id = None
            if initial_prompt:
                prompt_id = f"{group_id}-prompt-1"
                prompt_query = sa.insert(prompts_table).values(
                    id=prompt_id,
                    prompt_text=initial_prompt,
                    group_id=group_id,
                    user_id=user_id,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                conn.execute(prompt_query)

                # Update group with production prompt reference
                update_query = (
                    sa.update(prompt_groups_table)
                    .where(prompt_groups_table.c.id == group_id)
                    .values(production_prompt_id=prompt_id, updated_at=now_epoch_ms())
                )
                conn.execute(update_query)

            if conn.in_transaction():
                conn.commit()

            # Fetch the created prompt group
            select_query = sa.select(prompt_groups_table).where(
                prompt_groups_table.c.id == group_id
            )
            created_group = conn.execute(select_query).first()

        return created_group._asdict() if created_group else None
