"""
Unit tests for sessions router batch endpoints.

Tests batch_move_sessions and batch_delete_sessions endpoints.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.dto.requests.session_requests import (
    BatchMoveSessionsRequest,
    BatchDeleteSessionsRequest,
)
from solace_agent_mesh.gateway.http_sse.routers.sessions import (
    batch_move_sessions,
    batch_delete_sessions,
)


class TestBatchMoveSessionsEndpoint:
    """Tests for POST /api/v1/sessions/batch/move endpoint."""

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock session service."""
        service = Mock()
        service.batch_move_sessions_to_project = AsyncMock()
        return service

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        return {"id": "user-123", "email": "test@example.com"}

    @pytest.mark.asyncio
    async def test_batch_move_success(self, mock_session_service, mock_db, mock_user):
        """Test successful batch move returns 200 with results."""
        mock_session_service.batch_move_sessions_to_project.return_value = {
            "success": ["session-1", "session-2"],
            "failed": []
        }

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1", "session-2"],
            projectId="project-123"
        )

        result = await batch_move_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == ["session-1", "session-2"]
        assert result["failed"] == []
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 2
        assert result["totalFailed"] == 0
        mock_session_service.batch_move_sessions_to_project.assert_called_once_with(
            db=mock_db,
            session_ids=["session-1", "session-2"],
            user_id="user-123",
            new_project_id="project-123"
        )

    @pytest.mark.asyncio
    async def test_batch_move_partial_success(self, mock_session_service, mock_db, mock_user):
        """Test batch move with partial success returns 200 with mixed results."""
        mock_session_service.batch_move_sessions_to_project.return_value = {
            "success": ["session-1"],
            "failed": [{"id": "session-2", "reason": "Session not found"}]
        }

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1", "session-2"],
            projectId="project-123"
        )

        result = await batch_move_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == ["session-1"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["id"] == "session-2"
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 1
        assert result["totalFailed"] == 1

    @pytest.mark.asyncio
    async def test_batch_move_invalid_project_returns_422(self, mock_session_service, mock_db, mock_user):
        """Test batch move with invalid project returns 422."""
        mock_session_service.batch_move_sessions_to_project.side_effect = ValueError(
            "Project not found or access denied"
        )

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId="invalid-project"
        )

        with pytest.raises(HTTPException) as exc_info:
            await batch_move_sessions(
                request=request,
                db=mock_db,
                user=mock_user,
                session_service=mock_session_service
            )

        assert exc_info.value.status_code == 422
        assert "Project not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_batch_move_to_no_project(self, mock_session_service, mock_db, mock_user):
        """Test batch move to remove from project (projectId=None)."""
        mock_session_service.batch_move_sessions_to_project.return_value = {
            "success": ["session-1"],
            "failed": []
        }

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId=None
        )

        result = await batch_move_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        mock_session_service.batch_move_sessions_to_project.assert_called_once_with(
            db=mock_db,
            session_ids=["session-1"],
            user_id="user-123",
            new_project_id=None
        )
        assert result["totalSuccess"] == 1

    @pytest.mark.asyncio
    async def test_batch_move_server_error_returns_500(self, mock_session_service, mock_db, mock_user):
        """Test batch move with server error returns 500."""
        mock_session_service.batch_move_sessions_to_project.side_effect = Exception(
            "Database connection failed"
        )

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId="project-123"
        )

        with pytest.raises(HTTPException) as exc_info:
            await batch_move_sessions(
                request=request,
                db=mock_db,
                user=mock_user,
                session_service=mock_session_service
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_batch_move_all_failed(self, mock_session_service, mock_db, mock_user):
        """Test batch move with all failures returns 200 with failed results."""
        mock_session_service.batch_move_sessions_to_project.return_value = {
            "success": [],
            "failed": [
                {"id": "session-1", "reason": "Session not found"},
                {"id": "session-2", "reason": "Session not found"}
            ]
        }

        request = BatchMoveSessionsRequest(
            sessionIds=["session-1", "session-2"],
            projectId="project-123"
        )

        result = await batch_move_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == []
        assert len(result["failed"]) == 2
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 0
        assert result["totalFailed"] == 2


class TestBatchDeleteSessionsEndpoint:
    """Tests for POST /api/v1/sessions/batch/delete endpoint."""

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock session service."""
        service = Mock()
        service.batch_delete_sessions = Mock()
        return service

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        return {"id": "user-123", "email": "test@example.com"}

    @pytest.mark.asyncio
    async def test_batch_delete_success(self, mock_session_service, mock_db, mock_user):
        """Test successful batch delete returns 200 with results."""
        mock_session_service.batch_delete_sessions.return_value = {
            "success": ["session-1", "session-2"],
            "failed": []
        }

        request = BatchDeleteSessionsRequest(sessionIds=["session-1", "session-2"])

        result = await batch_delete_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == ["session-1", "session-2"]
        assert result["failed"] == []
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 2
        assert result["totalFailed"] == 0
        mock_session_service.batch_delete_sessions.assert_called_once_with(
            db=mock_db,
            session_ids=["session-1", "session-2"],
            user_id="user-123"
        )

    @pytest.mark.asyncio
    async def test_batch_delete_partial_success(self, mock_session_service, mock_db, mock_user):
        """Test batch delete with partial success returns 200 with mixed results."""
        mock_session_service.batch_delete_sessions.return_value = {
            "success": ["session-1"],
            "failed": [{"id": "session-2", "reason": "Not authorized to delete"}]
        }

        request = BatchDeleteSessionsRequest(sessionIds=["session-1", "session-2"])

        result = await batch_delete_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == ["session-1"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["id"] == "session-2"
        assert result["failed"][0]["reason"] == "Not authorized to delete"
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 1
        assert result["totalFailed"] == 1

    @pytest.mark.asyncio
    async def test_batch_delete_all_failed(self, mock_session_service, mock_db, mock_user):
        """Test batch delete with all failures returns 200 with failed results."""
        mock_session_service.batch_delete_sessions.return_value = {
            "success": [],
            "failed": [
                {"id": "session-1", "reason": "Session not found"},
                {"id": "session-2", "reason": "Session not found"}
            ]
        }

        request = BatchDeleteSessionsRequest(sessionIds=["session-1", "session-2"])

        result = await batch_delete_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == []
        assert len(result["failed"]) == 2
        assert result["totalRequested"] == 2
        assert result["totalSuccess"] == 0
        assert result["totalFailed"] == 2

    @pytest.mark.asyncio
    async def test_batch_delete_server_error_returns_500(self, mock_session_service, mock_db, mock_user):
        """Test batch delete with server error returns 500."""
        mock_session_service.batch_delete_sessions.side_effect = Exception(
            "Database connection failed"
        )

        request = BatchDeleteSessionsRequest(sessionIds=["session-1"])

        with pytest.raises(HTTPException) as exc_info:
            await batch_delete_sessions(
                request=request,
                db=mock_db,
                user=mock_user,
                session_service=mock_session_service
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_batch_delete_single_session(self, mock_session_service, mock_db, mock_user):
        """Test batch delete with single session."""
        mock_session_service.batch_delete_sessions.return_value = {
            "success": ["session-1"],
            "failed": []
        }

        request = BatchDeleteSessionsRequest(sessionIds=["session-1"])

        result = await batch_delete_sessions(
            request=request,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service
        )

        assert result["success"] == ["session-1"]
        assert result["totalRequested"] == 1
        assert result["totalSuccess"] == 1
        mock_session_service.batch_delete_sessions.assert_called_once_with(
            db=mock_db,
            session_ids=["session-1"],
            user_id="user-123"
        )

    @pytest.mark.asyncio
    async def test_batch_delete_validation_error_returns_422(self, mock_session_service, mock_db, mock_user):
        """Test batch delete with validation error returns 422."""
        mock_session_service.batch_delete_sessions.side_effect = ValueError(
            "Invalid session IDs"
        )

        request = BatchDeleteSessionsRequest(sessionIds=["session-1"])

        with pytest.raises(HTTPException) as exc_info:
            await batch_delete_sessions(
                request=request,
                db=mock_db,
                user=mock_user,
                session_service=mock_session_service
            )

        assert exc_info.value.status_code == 422
        assert "Invalid session IDs" in str(exc_info.value.detail)
