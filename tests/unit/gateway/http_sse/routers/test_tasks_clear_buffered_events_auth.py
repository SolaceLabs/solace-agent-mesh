"""Unit tests for DELETE /tasks/{task_id}/events/buffered endpoint authorization."""

import pytest
from unittest.mock import MagicMock, patch


class TestClearBufferedTaskEventsAuthorization:
    """Tests for DELETE /tasks/{task_id}/events/buffered endpoint authorization."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        return MagicMock()

    @pytest.fixture
    def mock_sse_manager(self):
        """Create a mock SSEManager."""
        mock_manager = MagicMock()
        mock_persistent_buffer = MagicMock()
        mock_manager.get_persistent_buffer.return_value = mock_persistent_buffer
        return mock_manager, mock_persistent_buffer

    @pytest.fixture
    def mock_component(self, mock_sse_manager):
        """Create a mock WebUIBackendComponent."""
        mock_comp = MagicMock()
        mock_comp.sse_manager = mock_sse_manager[0]
        return mock_comp

    @pytest.mark.asyncio
    async def test_returns_403_when_task_metadata_belongs_to_different_user(
        self, mock_db, mock_request, mock_sse_manager
    ):
        """Test that endpoint returns 403 when task metadata belongs to different user."""
        from fastapi import HTTPException

        mock_manager, mock_persistent_buffer = mock_sse_manager
        
        # Task metadata shows different owner
        mock_persistent_buffer.get_task_metadata.return_value = {
            "user_id": "owner-user-id"
        }

        requesting_user_id = "different-user-id"
        task_id = "test-task-id"

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                clear_buffered_task_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await clear_buffered_task_events(
                    task_id=task_id,
                    request=mock_request,
                    db=mock_db,
                    user_id=requesting_user_id,
                )

            assert exc_info.value.status_code == 403
            assert "permission" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_403_when_db_task_belongs_to_different_user(
        self, mock_db, mock_request, mock_sse_manager
    ):
        """Test that endpoint returns 403 when DB task belongs to different user."""
        from fastapi import HTTPException

        mock_manager, mock_persistent_buffer = mock_sse_manager
        
        # No task metadata (fall back to DB lookup)
        mock_persistent_buffer.get_task_metadata.return_value = None

        # Create a mock task from DB belonging to different user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"

        mock_task_repo = MagicMock()
        mock_task_repo.find_by_id.return_value = mock_task

        requesting_user_id = "different-user-id"
        task_id = "test-task-id"

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        # Patch at the repository module level to intercept the import inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                clear_buffered_task_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await clear_buffered_task_events(
                    task_id=task_id,
                    request=mock_request,
                    db=mock_db,
                    user_id=requesting_user_id,
                )

            assert exc_info.value.status_code == 403
            assert "permission" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_allows_access_when_task_metadata_belongs_to_same_user(
        self, mock_db, mock_request, mock_sse_manager
    ):
        """Test that endpoint allows access when task metadata belongs to requesting user."""
        mock_manager, mock_persistent_buffer = mock_sse_manager
        
        # Task metadata shows same owner
        mock_persistent_buffer.get_task_metadata.return_value = {
            "user_id": "owner-user-id"
        }
        mock_persistent_buffer.delete_events_for_task.return_value = 5

        requesting_user_id = "owner-user-id"  # Same as owner
        task_id = "test-task-id"

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                clear_buffered_task_events,
            )

            result = await clear_buffered_task_events(
                task_id=task_id,
                request=mock_request,
                db=mock_db,
                user_id=requesting_user_id,
            )

            # Should return successfully with deleted count
            assert result["task_id"] == task_id
            assert result["deleted"] == 5
            mock_persistent_buffer.delete_events_for_task.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_allows_access_when_no_metadata_and_no_db_task(
        self, mock_db, mock_request, mock_sse_manager
    ):
        """Test that endpoint allows access when no metadata and no DB task (orphan buffer)."""
        mock_manager, mock_persistent_buffer = mock_sse_manager
        
        # No task metadata
        mock_persistent_buffer.get_task_metadata.return_value = None
        mock_persistent_buffer.delete_events_for_task.return_value = 0

        # No DB task either
        mock_task_repo = MagicMock()
        mock_task_repo.find_by_id.return_value = None

        requesting_user_id = "some-user-id"
        task_id = "orphan-task-id"

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        # Patch at the repository module level to intercept the import inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                clear_buffered_task_events,
            )

            result = await clear_buffered_task_events(
                task_id=task_id,
                request=mock_request,
                db=mock_db,
                user_id=requesting_user_id,
            )

            # Should return successfully (permissive for orphan data)
            assert result["task_id"] == task_id
            assert "deleted" in result

    @pytest.mark.asyncio
    async def test_returns_503_when_component_not_available(
        self, mock_db, mock_request
    ):
        """Test that endpoint returns 503 when component is not available."""
        from fastapi import HTTPException

        requesting_user_id = "some-user-id"
        task_id = "test-task-id"

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.get_sac_component",
            return_value=None,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                clear_buffered_task_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await clear_buffered_task_events(
                    task_id=task_id,
                    request=mock_request,
                    db=mock_db,
                    user_id=requesting_user_id,
                )

            assert exc_info.value.status_code == 503
            assert "not available" in exc_info.value.detail.lower()
