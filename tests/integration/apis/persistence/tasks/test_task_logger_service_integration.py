"""
Integration tests for TaskLoggerService chat message saving.

Tests that _save_chat_messages_for_background_task writes to database correctly.
Companion tests to unit tests which mock DB operations.
"""

import json

import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.repository.entities.task import Task
from solace_agent_mesh.gateway.http_sse.repository.task_repository import TaskRepository
from solace_agent_mesh.gateway.http_sse.services.task_logger_service import (
    TaskLoggerService,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestTaskLoggerServiceIntegration:
    """Integration tests for TaskLoggerService with real database."""

    def test_saves_chat_task_to_database(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that background task events are saved as chat messages in DB."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            task_id = "bg-task-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=task_id,
                    session_id=session.id,
                    user_id="sam_dev_user",
                    initial_request_text="What is AI?",
                    start_time=now,
                    end_time=now + 5000,
                    status="completed",
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-req-{task_id}",
                    task_id=task_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {
                                "contextId": session.id,
                                "parts": [{"kind": "text", "text": "What is AI?"}],
                                "metadata": {"agent_name": "TestAgent"},
                            }
                        }
                    },
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-status-{task_id}",
                    task_id=task_id,
                    user_id="sam_dev_user",
                    created_time=now + 1000,
                    topic="agent/task/status",
                    direction="status",
                    payload={
                        "result": {
                            "kind": "task",
                            "status": {
                                "message": {
                                    "parts": [
                                        {
                                            "kind": "text",
                                            "text": "AI is artificial intelligence.",
                                        }
                                    ]
                                }
                            },
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            service = TaskLoggerService(session_factory=lambda: db_session, config={})
            repo = TaskRepository()
            task_entity = Task(
                id=task_id,
                user_id="sam_dev_user",
                start_time=now,
                end_time=now + 5000,
                status="completed",
                initial_request_text="What is AI?",
            )

            service._save_chat_messages_for_background_task(
                db_session, task_id, task_entity, repo
            )
            db_session.commit()

        # Assert: Chat task was created
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            chat_tasks_table = metadata.tables["chat_tasks"]

            result = conn.execute(
                sa.select(chat_tasks_table).where(chat_tasks_table.c.id == task_id)
            ).first()

            # The save should succeed (the exception is caught and logged)
            assert result is not None
            assert result.session_id == session.id
            assert result.user_message == "What is AI?"

            bubbles = json.loads(result.message_bubbles)
            assert len(bubbles) == 2
            assert bubbles[0]["type"] == "user"
            assert bubbles[1]["type"] == "agent"

    def test_skips_when_session_not_found(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that service skips saving when session doesn't exist in DB."""
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]
            task_events_table = metadata.tables["task_events"]

            task_id = "bg-task-no-session"
            nonexistent_session = "session-999"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=task_id,
                    session_id=nonexistent_session,
                    user_id="sam_dev_user",
                    initial_request_text="Test",
                    start_time=now,
                    status="completed",
                )
            )

            conn.execute(
                sa.insert(task_events_table).values(
                    id=f"evt-{task_id}",
                    task_id=task_id,
                    user_id="sam_dev_user",
                    created_time=now,
                    topic="agent/task/request",
                    direction="request",
                    payload={
                        "params": {
                            "message": {
                                "contextId": nonexistent_session,
                                "parts": [{"kind": "text", "text": "Test"}],
                                "metadata": {},
                            }
                        }
                    },
                )
            )
            conn.commit()

        # Act
        with db_session_factory() as db_session:
            service = TaskLoggerService(session_factory=lambda: db_session, config={})
            repo = TaskRepository()
            task_entity = Task(
                id=task_id,
                user_id="sam_dev_user",
                start_time=now,
                status="completed",
                initial_request_text="Test",
            )

            service._save_chat_messages_for_background_task(
                db_session, task_id, task_entity, repo
            )
            db_session.commit()

        # Assert: No chat task created
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            chat_tasks_table = metadata.tables["chat_tasks"]

            result = conn.execute(
                sa.select(chat_tasks_table).where(chat_tasks_table.c.id == task_id)
            ).first()

            assert result is None
