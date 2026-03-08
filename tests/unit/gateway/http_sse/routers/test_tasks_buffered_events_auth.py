"""Unit tests for /tasks/{task_id}/events/buffered endpoint authorization."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestGetBufferedTaskEventsAuthorization:
    """Tests for GET /tasks/{task_id}/events/buffered endpoint authorization."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_task_repo(self):
        """Create a mock TaskRepository."""
        return MagicMock()

    @pytest.fixture
    def mock_buffer_repo(self):
        """Create a mock SSEEventBufferRepository."""
        return MagicMock()

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_403_when_task_belongs_to_different_user(
        self, mock_db, mock_task_repo, mock_request
    ):
        """Test that endpoint returns 403 when task belongs to different user."""
        from fastapi import HTTPException

        # Create a mock task belonging to a different user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"
        mock_task.events_consumed = False
        mock_task_repo.find_by_id_with_events.return_value = (mock_task, [])

        requesting_user_id = "different-user-id"
        task_id = "test-task-id"
        
        # User config without read:all scope
        user_config = {"scopes": {"tasks:read:all": False}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_buffered_task_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_buffered_task_events(
                    task_id=task_id,
                    request=mock_request,
                    db=mock_db,
                    user_id=requesting_user_id,
                    user_config=user_config,
                    repo=mock_task_repo,
                    mark_consumed=True,
                )

            assert exc_info.value.status_code == 403
            assert "permission" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_allows_access_when_task_belongs_to_same_user(
        self, mock_db, mock_task_repo, mock_buffer_repo, mock_request
    ):
        """Test that endpoint allows access when task belongs to the requesting user."""
        # Create a mock task belonging to the requesting user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"
        mock_task.events_consumed = False
        mock_task_repo.find_by_id_with_events.return_value = (mock_task, [])

        # Mock buffer repo
        mock_buffer_repo.has_unconsumed_events.return_value = True
        mock_buffer_repo.get_buffered_events.return_value = [
            {"type": "message", "data": {"text": "test"}, "sequence": 1}
        ]

        requesting_user_id = "owner-user-id"  # Same as owner
        task_id = "test-task-id"
        user_config = {"scopes": {"tasks:read:all": False}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.TaskRepository",
            return_value=mock_task_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository",
            return_value=mock_buffer_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_buffered_task_events,
            )

            result = await get_buffered_task_events(
                task_id=task_id,
                request=mock_request,
                db=mock_db,
                user_id=requesting_user_id,
                user_config=user_config,
                repo=mock_task_repo,
                mark_consumed=True,
            )

            # Should return successfully with events
            assert result["task_id"] == task_id
            assert "events" in result

    @pytest.mark.asyncio
    async def test_allows_access_with_read_all_scope(
        self, mock_db, mock_task_repo, mock_buffer_repo, mock_request
    ):
        """Test that endpoint allows access when user has tasks:read:all scope."""
        # Create a mock task belonging to a different user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"
        mock_task.events_consumed = False
        mock_task_repo.find_by_id_with_events.return_value = (mock_task, [])

        # Mock buffer repo
        mock_buffer_repo.has_unconsumed_events.return_value = False
        mock_buffer_repo.get_event_count.return_value = 0

        requesting_user_id = "admin-user-id"  # Different from owner
        task_id = "test-task-id"
        # User has read:all scope
        user_config = {"scopes": {"tasks:read:all": True}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.TaskRepository",
            return_value=mock_task_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository",
            return_value=mock_buffer_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_buffered_task_events,
            )

            result = await get_buffered_task_events(
                task_id=task_id,
                request=mock_request,
                db=mock_db,
                user_id=requesting_user_id,
                user_config=user_config,
                repo=mock_task_repo,
                mark_consumed=True,
            )

            # Should return successfully (empty events)
            assert result["task_id"] == task_id
            assert result["events_buffered"] is False

    @pytest.mark.asyncio
    async def test_returns_404_when_task_not_found(
        self, mock_db, mock_task_repo, mock_request
    ):
        """Test that endpoint returns 404 when task is not found."""
        from fastapi import HTTPException

        mock_task_repo.find_by_id_with_events.return_value = None

        requesting_user_id = "some-user-id"
        task_id = "nonexistent-task-id"
        user_config = {"scopes": {"tasks:read:all": False}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.tasks.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_buffered_task_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_buffered_task_events(
                    task_id=task_id,
                    request=mock_request,
                    db=mock_db,
                    user_id=requesting_user_id,
                    user_config=user_config,
                    repo=mock_task_repo,
                    mark_consumed=True,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()
