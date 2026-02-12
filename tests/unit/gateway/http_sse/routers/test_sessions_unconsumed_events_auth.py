"""Unit tests for GET /sessions/{session_id}/events/unconsumed endpoint authorization."""

import pytest
from unittest.mock import MagicMock, patch


class TestGetSessionUnconsumedEventsAuthorization:
    """Tests for GET /sessions/{session_id}/events/unconsumed endpoint authorization."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock SessionService."""
        return MagicMock()

    @pytest.fixture
    def mock_sse_manager(self):
        """Create a mock SSEManager."""
        mock_manager = MagicMock()
        mock_persistent_buffer = MagicMock()
        mock_manager.get_persistent_buffer.return_value = mock_persistent_buffer
        return mock_manager, mock_persistent_buffer

    @pytest.mark.asyncio
    async def test_returns_404_when_session_belongs_to_different_user(
        self, mock_db, mock_session_service
    ):
        """Test that endpoint returns 404 when session belongs to different user."""
        from fastapi import HTTPException

        # Session service returns None (session not found or not owned by user)
        mock_session_service.get_session_details.return_value = None

        requesting_user = {"id": "different-user-id"}
        session_id = "test-session-id"

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_session_unconsumed_events(
                    session_id=session_id,
                    include_events=False,
                    db=mock_db,
                    user=requesting_user,
                    session_service=mock_session_service,
                )

            assert exc_info.value.status_code == 404
            # Session not found means either doesn't exist or user doesn't own it
            assert "not found" in exc_info.value.detail.lower()

        # Verify the service was called with correct user_id
        mock_session_service.get_session_details.assert_called_once_with(
            db=mock_db, session_id=session_id, user_id="different-user-id"
        )

    @pytest.mark.asyncio
    async def test_allows_access_when_session_belongs_to_same_user(
        self, mock_db, mock_session_service, mock_sse_manager
    ):
        """Test that endpoint allows access when session belongs to requesting user."""
        mock_manager, mock_persistent_buffer = mock_sse_manager

        # Session service returns session (user owns it)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session_service.get_session_details.return_value = mock_session

        # Mock persistent buffer returns empty
        mock_persistent_buffer.get_unconsumed_events_for_session.return_value = {}

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        requesting_user = {"id": "owner-user-id"}
        session_id = "test-session-id"

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            result = await get_session_unconsumed_events(
                session_id=session_id,
                include_events=False,
                db=mock_db,
                user=requesting_user,
                session_service=mock_session_service,
            )

            # Should return successfully
            assert result["session_id"] == session_id
            assert result["has_events"] is False
            assert result["task_ids"] == []

    @pytest.mark.asyncio
    async def test_returns_unconsumed_events_for_valid_session(
        self, mock_db, mock_session_service, mock_sse_manager
    ):
        """Test that endpoint returns unconsumed events when include_events=True."""
        mock_manager, mock_persistent_buffer = mock_sse_manager

        # Session service returns session (user owns it)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session_service.get_session_details.return_value = mock_session

        # Mock persistent buffer returns events for two tasks
        mock_persistent_buffer.get_unconsumed_events_for_session.return_value = {
            "task-1": [
                {"event_sequence": 1, "event_type": "message", "event_data": {"text": "hello"}}
            ],
            "task-2": [
                {"event_sequence": 1, "event_type": "artifact", "event_data": {"name": "file.txt"}}
            ],
        }

        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        requesting_user = {"id": "owner-user-id"}
        session_id = "test-session-id"

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            result = await get_session_unconsumed_events(
                session_id=session_id,
                include_events=True,
                db=mock_db,
                user=requesting_user,
                session_service=mock_session_service,
            )

            # Should return events grouped by task_id
            assert result["session_id"] == session_id
            assert result["has_events"] is True
            assert "task-1" in result["task_ids"]
            assert "task-2" in result["task_ids"]
            assert "events_by_task" in result
            assert len(result["events_by_task"]) == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_session_id(
        self, mock_db, mock_session_service
    ):
        """Test that endpoint returns 404 for invalid session IDs."""
        from fastapi import HTTPException

        requesting_user = {"id": "some-user-id"}

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            # Test with "null" string
            with pytest.raises(HTTPException) as exc_info:
                await get_session_unconsumed_events(
                    session_id="null",
                    include_events=False,
                    db=mock_db,
                    user=requesting_user,
                    session_service=mock_session_service,
                )

            assert exc_info.value.status_code == 404

            # Test with "undefined" string
            with pytest.raises(HTTPException) as exc_info:
                await get_session_unconsumed_events(
                    session_id="undefined",
                    include_events=False,
                    db=mock_db,
                    user=requesting_user,
                    session_service=mock_session_service,
                )

            assert exc_info.value.status_code == 404

            # Test with empty string
            with pytest.raises(HTTPException) as exc_info:
                await get_session_unconsumed_events(
                    session_id="",
                    include_events=False,
                    db=mock_db,
                    user=requesting_user,
                    session_service=mock_session_service,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_handles_missing_persistent_buffer(
        self, mock_db, mock_session_service
    ):
        """Test that endpoint handles missing persistent buffer gracefully."""
        # Session service returns session (user owns it)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session_service.get_session_details.return_value = mock_session

        # Mock component with no persistent buffer
        mock_manager = MagicMock()
        mock_manager.get_persistent_buffer.return_value = None
        mock_component = MagicMock()
        mock_component.sse_manager = mock_manager

        requesting_user = {"id": "owner-user-id"}
        session_id = "test-session-id"

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            result = await get_session_unconsumed_events(
                session_id=session_id,
                include_events=False,
                db=mock_db,
                user=requesting_user,
                session_service=mock_session_service,
            )

            # Should return empty result, not error
            assert result["has_events"] is False
            assert result["task_ids"] == []

    @pytest.mark.asyncio
    async def test_handles_missing_component(
        self, mock_db, mock_session_service
    ):
        """Test that endpoint handles missing component gracefully."""
        # Session service returns session (user owns it)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session_service.get_session_details.return_value = mock_session

        requesting_user = {"id": "owner-user-id"}
        session_id = "test-session-id"

        # Patch at the dependencies module level since it's imported inside the function
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=None,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_unconsumed_events,
            )

            result = await get_session_unconsumed_events(
                session_id=session_id,
                include_events=False,
                db=mock_db,
                user=requesting_user,
                session_service=mock_session_service,
            )

            # Should return empty result, not error
            assert result["has_events"] is False
            assert result["task_ids"] == []
