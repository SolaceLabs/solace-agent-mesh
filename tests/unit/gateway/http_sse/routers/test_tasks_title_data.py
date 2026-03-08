"""Unit tests for /tasks/{task_id}/title-data endpoint authorization."""

import pytest
from unittest.mock import MagicMock, patch


class TestGetTaskTitleDataAuthorization:
    """Tests for GET /tasks/{task_id}/title-data endpoint authorization."""

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
    def mock_chat_task_repo(self):
        """Create a mock ChatTaskRepository."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_returns_403_when_task_belongs_to_different_user(
        self, mock_db, mock_task_repo
    ):
        """Test that endpoint returns 403 when task belongs to different user."""
        from fastapi import HTTPException
        
        # Create a mock task belonging to a different user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"
        mock_task.initial_request_text = "test message"
        mock_task.session_id = "test-session-id"
        mock_task_repo.find_by_id.return_value = mock_task

        requesting_user_id = "different-user-id"
        task_id = "test-task-id"

        # Patch at the repository module level since imports are inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_task_title_data,
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_task_title_data(
                    task_id=task_id,
                    db=mock_db,
                    user_id=requesting_user_id,
                )

            assert exc_info.value.status_code == 403
            assert "permission" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_allows_access_when_task_belongs_to_same_user(
        self, mock_db, mock_task_repo, mock_chat_task_repo, mock_buffer_repo
    ):
        """Test that endpoint allows access when task belongs to the requesting user."""
        # Create a mock task belonging to the requesting user
        mock_task = MagicMock()
        mock_task.user_id = "owner-user-id"
        mock_task.initial_request_text = "test user message"
        mock_task.session_id = "test-session-id"
        mock_task_repo.find_by_id.return_value = mock_task

        # Mock chat_task with message bubbles
        mock_chat_task = MagicMock()
        mock_chat_task.user_message = "test user message"
        mock_chat_task.message_bubbles = None  # No bubbles to simplify test
        mock_chat_task_repo.find_by_id.return_value = mock_chat_task

        # Mock empty buffer
        mock_buffer_repo.get_buffered_events.return_value = []

        requesting_user_id = "owner-user-id"  # Same as owner
        task_id = "test-task-id"

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository",
            return_value=mock_buffer_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.chat_task_repository.ChatTaskRepository",
            return_value=mock_chat_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_task_title_data,
            )

            result = await get_task_title_data(
                task_id=task_id,
                db=mock_db,
                user_id=requesting_user_id,
            )

            # Should return successfully with the user message
            assert result["user_message"] == "test user message"
            assert result["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_allows_access_when_task_has_no_user_id(
        self, mock_db, mock_task_repo, mock_chat_task_repo, mock_buffer_repo
    ):
        """Test that endpoint allows access when task has no user_id (legacy data)."""
        # Create a mock task with no user_id
        mock_task = MagicMock()
        mock_task.user_id = None  # No user_id set
        mock_task.initial_request_text = "test user message"
        mock_task.session_id = "test-session-id"
        mock_task_repo.find_by_id.return_value = mock_task

        # Mock no chat_task found
        mock_chat_task_repo.find_by_id.return_value = None

        # Mock empty buffer
        mock_buffer_repo.get_buffered_events.return_value = []

        requesting_user_id = "some-user-id"
        task_id = "test-task-id"

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository",
            return_value=mock_buffer_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.repository.chat_task_repository.ChatTaskRepository",
            return_value=mock_chat_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_task_title_data,
            )

            result = await get_task_title_data(
                task_id=task_id,
                db=mock_db,
                user_id=requesting_user_id,
            )

            # Should return successfully (permissive for legacy data)
            assert result["user_message"] == "test user message"
            assert result["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_returns_error_when_task_not_found(self, mock_db, mock_task_repo):
        """Test that endpoint returns error info when task is not found."""
        mock_task_repo.find_by_id.return_value = None

        requesting_user_id = "some-user-id"
        task_id = "nonexistent-task-id"

        with patch(
            "solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository",
            return_value=mock_task_repo,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.tasks import (
                get_task_title_data,
            )

            result = await get_task_title_data(
                task_id=task_id,
                db=mock_db,
                user_id=requesting_user_id,
            )

            # Should return error info, not raise exception
            assert result["user_message"] is None
            assert result["agent_response"] is None
            assert result["error"] == "Task not found"
