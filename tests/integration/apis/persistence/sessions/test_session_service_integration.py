"""
Integration tests for SessionService.move_session_to_project() method.

Tests actual database updates when moving sessions to/from projects.
Companion tests to unit tests which mock DB operations and focus on validation logic.
"""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestMoveSessionToProjectIntegration:
    """Integration tests for moving sessions to projects with real database."""

    @pytest.mark.asyncio
    async def test_move_session_to_owned_project_updates_database(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that moving session to owned project updates DB."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        project = gateway_adapter.seed_project(
            project_id="proj-owned-1",
            name="My Project",
            user_id="sam_dev_user",
        )

        # Verify initially no project
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]

            before = conn.execute(
                sa.select(sessions_table).where(sessions_table.c.id == session.id)
            ).first()
            assert before.project_id is None

        # Act
        with db_session_factory() as db_session:
            service = SessionService(component=None)
            result = await service.move_session_to_project(
                db=db_session,
                session_id=session.id,
                user_id="sam_dev_user",
                new_project_id=project["id"],
            )
            db_session.commit()

        # Assert
        assert result.project_id == project["id"]

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]

            after = conn.execute(
                sa.select(sessions_table).where(sessions_table.c.id == session.id)
            ).first()
            assert after.project_id == project["id"]

    @pytest.mark.asyncio
    async def test_move_session_to_nonexistent_project_fails(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that moving to non-existent project raises ValueError."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )

        # Act & Assert
        with (
            pytest.raises(ValueError, match="not found or access denied"),
            db_session_factory() as db_session,
        ):
            service = SessionService(component=None)
            await service.move_session_to_project(
                db=db_session,
                session_id=session.id,
                user_id="sam_dev_user",
                new_project_id="nonexistent-proj-999",
            )

    @pytest.mark.asyncio
    async def test_remove_session_from_project_sets_null(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that passing None as project_id removes session from project."""
        session = gateway_adapter.create_session(
            user_id="sam_dev_user", agent_name="TestAgent"
        )
        project = gateway_adapter.seed_project(
            project_id="proj-remove-1",
            name="Project",
            user_id="sam_dev_user",
        )

        # Add to project
        with db_session_factory() as db_session:
            service = SessionService(component=None)
            await service.move_session_to_project(
                db=db_session,
                session_id=session.id,
                user_id="sam_dev_user",
                new_project_id=project["id"],
            )
            db_session.commit()

        # Act: Remove
        with db_session_factory() as db_session:
            service = SessionService(component=None)
            result = await service.move_session_to_project(
                db=db_session,
                session_id=session.id,
                user_id="sam_dev_user",
                new_project_id=None,
            )
            db_session.commit()

        # Assert
        assert result.project_id is None

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sessions_table = metadata.tables["sessions"]

            after = conn.execute(
                sa.select(sessions_table).where(sessions_table.c.id == session.id)
            ).first()
            assert after.project_id is None
