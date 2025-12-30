"""Unit tests for batch session operations (DTOs, service, and router endpoints)."""

import pytest
from unittest.mock import Mock, AsyncMock
from pydantic import ValidationError
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.dto.requests.session_requests import (
    BatchMoveSessionsRequest,
    BatchDeleteSessionsRequest,
)
from solace_agent_mesh.gateway.http_sse.routers.sessions import (
    batch_move_sessions,
    batch_delete_sessions,
)


class TestBatchSessionDTOs:
    """Tests for batch session request DTOs."""

    def test_batch_move_valid_request(self):
        """Test valid batch move request."""
        request = BatchMoveSessionsRequest(sessionIds=["s1", "s2"], projectId="p1")
        assert request.session_ids == ["s1", "s2"]
        assert request.project_id == "p1"

    def test_batch_move_without_project(self):
        """Test batch move to remove from project."""
        request = BatchMoveSessionsRequest(sessionIds=["s1"], projectId=None)
        assert request.project_id is None

    def test_batch_move_empty_list_raises_error(self):
        """Test empty session IDs raises validation error."""
        with pytest.raises(ValidationError):
            BatchMoveSessionsRequest(sessionIds=[], projectId="p1")

    def test_batch_move_too_many_raises_error(self):
        """Test more than 100 session IDs raises validation error."""
        with pytest.raises(ValidationError):
            BatchMoveSessionsRequest(sessionIds=[f"s{i}" for i in range(101)], projectId="p1")

    def test_batch_delete_valid_request(self):
        """Test valid batch delete request."""
        request = BatchDeleteSessionsRequest(sessionIds=["s1", "s2"])
        assert request.session_ids == ["s1", "s2"]

    def test_batch_delete_empty_list_raises_error(self):
        """Test empty session IDs raises validation error."""
        with pytest.raises(ValidationError):
            BatchDeleteSessionsRequest(sessionIds=[])


class TestBatchMoveEndpoint:
    """Tests for batch move sessions endpoint."""

    @pytest.fixture
    def mock_service(self):
        service = Mock()
        service.batch_move_sessions_to_project = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_batch_move_success(self, mock_service):
        """Test successful batch move."""
        mock_service.batch_move_sessions_to_project.return_value = {"success": ["s1", "s2"], "failed": []}
        request = BatchMoveSessionsRequest(sessionIds=["s1", "s2"], projectId="p1")

        result = await batch_move_sessions(request, Mock(), {"id": "u1"}, mock_service)

        assert result["totalSuccess"] == 2
        assert result["totalFailed"] == 0

    @pytest.mark.asyncio
    async def test_batch_move_partial_success(self, mock_service):
        """Test batch move with partial success."""
        mock_service.batch_move_sessions_to_project.return_value = {
            "success": ["s1"],
            "failed": [{"id": "s2", "reason": "Not found"}]
        }
        request = BatchMoveSessionsRequest(sessionIds=["s1", "s2"], projectId="p1")

        result = await batch_move_sessions(request, Mock(), {"id": "u1"}, mock_service)

        assert result["totalSuccess"] == 1
        assert result["totalFailed"] == 1

    @pytest.mark.asyncio
    async def test_batch_move_invalid_project(self, mock_service):
        """Test batch move with invalid project returns 422."""
        mock_service.batch_move_sessions_to_project.side_effect = ValueError("Project not found")
        request = BatchMoveSessionsRequest(sessionIds=["s1"], projectId="invalid")

        with pytest.raises(HTTPException) as exc_info:
            await batch_move_sessions(request, Mock(), {"id": "u1"}, mock_service)
        assert exc_info.value.status_code == 422


class TestBatchDeleteEndpoint:
    """Tests for batch delete sessions endpoint."""

    @pytest.fixture
    def mock_service(self):
        service = Mock()
        service.batch_delete_sessions = Mock()
        return service

    @pytest.mark.asyncio
    async def test_batch_delete_success(self, mock_service):
        """Test successful batch delete."""
        mock_service.batch_delete_sessions.return_value = {"success": ["s1", "s2"], "failed": []}
        request = BatchDeleteSessionsRequest(sessionIds=["s1", "s2"])

        result = await batch_delete_sessions(request, Mock(), {"id": "u1"}, mock_service)

        assert result["totalSuccess"] == 2
        assert result["totalFailed"] == 0

    @pytest.mark.asyncio
    async def test_batch_delete_partial_success(self, mock_service):
        """Test batch delete with partial success."""
        mock_service.batch_delete_sessions.return_value = {
            "success": ["s1"],
            "failed": [{"id": "s2", "reason": "Unauthorized"}]
        }
        request = BatchDeleteSessionsRequest(sessionIds=["s1", "s2"])

        result = await batch_delete_sessions(request, Mock(), {"id": "u1"}, mock_service)

        assert result["totalSuccess"] == 1
        assert result["totalFailed"] == 1

    @pytest.mark.asyncio
    async def test_batch_delete_server_error(self, mock_service):
        """Test batch delete with server error returns 500."""
        mock_service.batch_delete_sessions.side_effect = Exception("DB error")
        request = BatchDeleteSessionsRequest(sessionIds=["s1"])

        with pytest.raises(HTTPException) as exc_info:
            await batch_delete_sessions(request, Mock(), {"id": "u1"}, mock_service)
        assert exc_info.value.status_code == 500
