"""
Unit tests for session request DTOs.

Tests BatchMoveSessionsRequest and BatchDeleteSessionsRequest validation.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.gateway.http_sse.routers.dto.requests.session_requests import (
    BatchMoveSessionsRequest,
    BatchDeleteSessionsRequest,
)


class TestBatchMoveSessionsRequest:
    """Tests for BatchMoveSessionsRequest DTO."""

    def test_valid_request_with_project_id(self):
        """Test valid request with session IDs and project ID."""
        request = BatchMoveSessionsRequest(
            sessionIds=["session-1", "session-2"],
            projectId="project-123"
        )
        assert request.session_ids == ["session-1", "session-2"]
        assert request.project_id == "project-123"

    def test_valid_request_without_project_id(self):
        """Test valid request with session IDs and no project ID (remove from project)."""
        request = BatchMoveSessionsRequest(
            sessionIds=["session-1", "session-2"],
            projectId=None
        )
        assert request.session_ids == ["session-1", "session-2"]
        assert request.project_id is None

    def test_valid_request_with_single_session(self):
        """Test valid request with single session ID."""
        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId="project-123"
        )
        assert len(request.session_ids) == 1

    def test_empty_session_ids_raises_error(self):
        """Test that empty session IDs list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BatchMoveSessionsRequest(
                sessionIds=[],
                projectId="project-123"
            )
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value).lower()

    def test_too_many_session_ids_raises_error(self):
        """Test that more than 100 session IDs raises validation error."""
        session_ids = [f"session-{i}" for i in range(101)]
        with pytest.raises(ValidationError) as exc_info:
            BatchMoveSessionsRequest(
                sessionIds=session_ids,
                projectId="project-123"
            )
        assert "max_length" in str(exc_info.value).lower() or "at most 100" in str(exc_info.value).lower()

    def test_max_session_ids_allowed(self):
        """Test that exactly 100 session IDs is allowed."""
        session_ids = [f"session-{i}" for i in range(100)]
        request = BatchMoveSessionsRequest(
            sessionIds=session_ids,
            projectId="project-123"
        )
        assert len(request.session_ids) == 100

    def test_missing_session_ids_raises_error(self):
        """Test that missing session IDs raises validation error."""
        with pytest.raises(ValidationError):
            BatchMoveSessionsRequest(projectId="project-123")

    def test_alias_mapping(self):
        """Test that camelCase aliases are properly mapped."""
        # Using camelCase (as sent from frontend)
        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId="project-123"
        )
        # Accessing via snake_case (Python convention)
        assert request.session_ids == ["session-1"]
        assert request.project_id == "project-123"

    def test_model_dump_uses_aliases(self):
        """Test that model dump uses aliases by default."""
        request = BatchMoveSessionsRequest(
            sessionIds=["session-1"],
            projectId="project-123"
        )
        dumped = request.model_dump(by_alias=True)
        assert "sessionIds" in dumped
        assert "projectId" in dumped


class TestBatchDeleteSessionsRequest:
    """Tests for BatchDeleteSessionsRequest DTO."""

    def test_valid_request(self):
        """Test valid request with session IDs."""
        request = BatchDeleteSessionsRequest(
            sessionIds=["session-1", "session-2"]
        )
        assert request.session_ids == ["session-1", "session-2"]

    def test_valid_request_with_single_session(self):
        """Test valid request with single session ID."""
        request = BatchDeleteSessionsRequest(
            sessionIds=["session-1"]
        )
        assert len(request.session_ids) == 1

    def test_empty_session_ids_raises_error(self):
        """Test that empty session IDs list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteSessionsRequest(sessionIds=[])
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value).lower()

    def test_too_many_session_ids_raises_error(self):
        """Test that more than 100 session IDs raises validation error."""
        session_ids = [f"session-{i}" for i in range(101)]
        with pytest.raises(ValidationError) as exc_info:
            BatchDeleteSessionsRequest(sessionIds=session_ids)
        assert "max_length" in str(exc_info.value).lower() or "at most 100" in str(exc_info.value).lower()

    def test_max_session_ids_allowed(self):
        """Test that exactly 100 session IDs is allowed."""
        session_ids = [f"session-{i}" for i in range(100)]
        request = BatchDeleteSessionsRequest(sessionIds=session_ids)
        assert len(request.session_ids) == 100

    def test_missing_session_ids_raises_error(self):
        """Test that missing session IDs raises validation error."""
        with pytest.raises(ValidationError):
            BatchDeleteSessionsRequest()

    def test_alias_mapping(self):
        """Test that camelCase aliases are properly mapped."""
        # Using camelCase (as sent from frontend)
        request = BatchDeleteSessionsRequest(sessionIds=["session-1"])
        # Accessing via snake_case (Python convention)
        assert request.session_ids == ["session-1"]

    def test_model_dump_uses_aliases(self):
        """Test that model dump uses aliases by default."""
        request = BatchDeleteSessionsRequest(sessionIds=["session-1"])
        dumped = request.model_dump(by_alias=True)
        assert "sessionIds" in dumped
