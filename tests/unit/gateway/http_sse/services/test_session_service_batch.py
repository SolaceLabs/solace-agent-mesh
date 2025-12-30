"""
Unit tests for SessionService batch operations.

Tests batch_move_sessions_to_project and batch_delete_sessions methods.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService


class TestBatchMoveSessionsToProject:
    """Tests for batch_move_sessions_to_project method."""

    @pytest.fixture
    def session_service(self):
        """Create a SessionService instance with mocked component."""
        component = Mock()
        component.database_url = "sqlite:///:memory:"
        return SessionService(component=component)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock(return_value=Mock())
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.mark.asyncio
    async def test_batch_move_empty_list_returns_empty_results(self, session_service, mock_db):
        """Test that batch move with empty list returns empty results."""
        result = await session_service.batch_move_sessions_to_project(
            db=mock_db,
            session_ids=[],
            user_id="user-123",
            new_project_id="project-456"
        )

        assert result == {"success": [], "failed": []}

    @pytest.mark.asyncio
    async def test_batch_move_invalid_project_raises_error(self, session_service, mock_db):
        """Test that batch move with invalid project raises ValueError."""
        # Mock project query to return None (project not found)
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(ValueError) as exc_info:
            await session_service.batch_move_sessions_to_project(
                db=mock_db,
                session_ids=["session-1"],
                user_id="user-123",
                new_project_id="invalid-project"
            )

        assert "not found or access denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_batch_move_invalid_session_id_fails(self, session_service, mock_db):
        """Test that invalid session IDs are reported as failed."""
        # Mock project query to return a valid project
        mock_project = Mock()
        mock_project.id = "project-456"
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_project)
        mock_db.query = Mock(return_value=mock_query)

        # Test with invalid session IDs
        result = await session_service.batch_move_sessions_to_project(
            db=mock_db,
            session_ids=["", "null", "undefined"],
            user_id="user-123",
            new_project_id="project-456"
        )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 3
        for failed in result["failed"]:
            assert failed["reason"] == "Invalid session ID"

    @pytest.mark.asyncio
    async def test_batch_move_session_not_found_fails(self, session_service, mock_db):
        """Test that sessions not found are reported as failed."""
        # Mock project query to return a valid project
        mock_project = Mock()
        mock_project.id = "project-456"
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_project)
        mock_db.query = Mock(return_value=mock_query)

        # Mock session repository to return None (session not found)
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_repo.move_to_project = Mock(return_value=None)
            mock_get_repos.return_value = mock_repo

            result = await session_service.batch_move_sessions_to_project(
                db=mock_db,
                session_ids=["session-1", "session-2"],
                user_id="user-123",
                new_project_id="project-456"
            )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 2
        for failed in result["failed"]:
            assert failed["reason"] == "Session not found or access denied"

    @pytest.mark.asyncio
    async def test_batch_move_successful_sessions(self, session_service, mock_db):
        """Test successful batch move of sessions."""
        # Mock project query to return a valid project
        mock_project = Mock()
        mock_project.id = "project-456"
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_project)
        mock_db.query = Mock(return_value=mock_query)

        # Mock session repository to return updated sessions
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            mock_repo.move_to_project = Mock(return_value=mock_session)
            mock_get_repos.return_value = mock_repo

            # Disable artifact copying for this test
            session_service.component = None

            result = await session_service.batch_move_sessions_to_project(
                db=mock_db,
                session_ids=["session-1", "session-2", "session-3"],
                user_id="user-123",
                new_project_id="project-456"
            )

        assert len(result["success"]) == 3
        assert len(result["failed"]) == 0
        assert "session-1" in result["success"]
        assert "session-2" in result["success"]
        assert "session-3" in result["success"]
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_move_to_no_project(self, session_service, mock_db):
        """Test batch move to remove sessions from project (new_project_id=None)."""
        # Mock session repository to return updated sessions
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            mock_repo.move_to_project = Mock(return_value=mock_session)
            mock_get_repos.return_value = mock_repo

            result = await session_service.batch_move_sessions_to_project(
                db=mock_db,
                session_ids=["session-1"],
                user_id="user-123",
                new_project_id=None  # Remove from project
            )

        assert len(result["success"]) == 1
        assert len(result["failed"]) == 0
        # Should not query for project when new_project_id is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_move_partial_success(self, session_service, mock_db):
        """Test batch move with some successes and some failures."""
        # Mock project query to return a valid project
        mock_project = Mock()
        mock_project.id = "project-456"
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_project)
        mock_db.query = Mock(return_value=mock_query)

        # Mock session repository to return success for some, None for others
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            # First call succeeds, second fails, third succeeds
            mock_repo.move_to_project = Mock(side_effect=[mock_session, None, mock_session])
            mock_get_repos.return_value = mock_repo

            # Disable artifact copying for this test
            session_service.component = None

            result = await session_service.batch_move_sessions_to_project(
                db=mock_db,
                session_ids=["session-1", "session-2", "session-3"],
                user_id="user-123",
                new_project_id="project-456"
            )

        assert len(result["success"]) == 2
        assert len(result["failed"]) == 1
        assert "session-1" in result["success"]
        assert "session-3" in result["success"]
        assert result["failed"][0]["id"] == "session-2"


class TestBatchDeleteSessions:
    """Tests for batch_delete_sessions method."""

    @pytest.fixture
    def session_service(self):
        """Create a SessionService instance with mocked component."""
        component = Mock()
        component.database_url = "sqlite:///:memory:"
        return SessionService(component=component)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()

    def test_batch_delete_empty_list_returns_empty_results(self, session_service, mock_db):
        """Test that batch delete with empty list returns empty results."""
        result = session_service.batch_delete_sessions(
            db=mock_db,
            session_ids=[],
            user_id="user-123"
        )

        assert result == {"success": [], "failed": []}

    def test_batch_delete_invalid_session_id_fails(self, session_service, mock_db):
        """Test that invalid session IDs are reported as failed."""
        result = session_service.batch_delete_sessions(
            db=mock_db,
            session_ids=["", "null", "undefined"],
            user_id="user-123"
        )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 3
        for failed in result["failed"]:
            assert failed["reason"] == "Invalid session ID"

    def test_batch_delete_session_not_found_fails(self, session_service, mock_db):
        """Test that sessions not found are reported as failed."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_repo.find_user_session = Mock(return_value=None)
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1", "session-2"],
                user_id="user-123"
            )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 2
        for failed in result["failed"]:
            assert failed["reason"] == "Session not found"

    def test_batch_delete_unauthorized_fails(self, session_service, mock_db):
        """Test that unauthorized deletions are reported as failed."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            mock_session.can_be_deleted_by_user = Mock(return_value=False)
            mock_repo.find_user_session = Mock(return_value=mock_session)
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1"],
                user_id="user-123"
            )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "Not authorized to delete"

    def test_batch_delete_soft_delete_fails(self, session_service, mock_db):
        """Test that failed soft deletes are reported as failed."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            mock_session.can_be_deleted_by_user = Mock(return_value=True)
            mock_session.agent_id = None
            mock_repo.find_user_session = Mock(return_value=mock_session)
            mock_repo.soft_delete = Mock(return_value=False)
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1"],
                user_id="user-123"
            )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "Failed to delete"

    def test_batch_delete_successful_sessions(self, session_service, mock_db):
        """Test successful batch delete of sessions."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_session = Mock()
            mock_session.can_be_deleted_by_user = Mock(return_value=True)
            mock_session.agent_id = None
            mock_repo.find_user_session = Mock(return_value=mock_session)
            mock_repo.soft_delete = Mock(return_value=True)
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1", "session-2", "session-3"],
                user_id="user-123"
            )

        assert len(result["success"]) == 3
        assert len(result["failed"]) == 0
        assert "session-1" in result["success"]
        assert "session-2" in result["success"]
        assert "session-3" in result["success"]

    def test_batch_delete_partial_success(self, session_service, mock_db):
        """Test batch delete with some successes and some failures."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            
            # Create different mock sessions for different behaviors
            mock_session_success = Mock()
            mock_session_success.can_be_deleted_by_user = Mock(return_value=True)
            mock_session_success.agent_id = None
            
            mock_session_unauthorized = Mock()
            mock_session_unauthorized.can_be_deleted_by_user = Mock(return_value=False)
            
            # First succeeds, second unauthorized, third succeeds
            mock_repo.find_user_session = Mock(side_effect=[
                mock_session_success,
                mock_session_unauthorized,
                mock_session_success
            ])
            mock_repo.soft_delete = Mock(return_value=True)
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1", "session-2", "session-3"],
                user_id="user-123"
            )

        assert len(result["success"]) == 2
        assert len(result["failed"]) == 1
        assert "session-1" in result["success"]
        assert "session-3" in result["success"]
        assert result["failed"][0]["id"] == "session-2"
        assert result["failed"][0]["reason"] == "Not authorized to delete"

    def test_batch_delete_notifies_agent(self, session_service, mock_db):
        """Test that agent is notified when session with agent_id is deleted."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            with patch.object(session_service, '_notify_agent_of_session_deletion') as mock_notify:
                mock_repo = Mock()
                mock_session = Mock()
                mock_session.can_be_deleted_by_user = Mock(return_value=True)
                mock_session.agent_id = "agent-123"
                mock_repo.find_user_session = Mock(return_value=mock_session)
                mock_repo.soft_delete = Mock(return_value=True)
                mock_get_repos.return_value = mock_repo

                result = session_service.batch_delete_sessions(
                    db=mock_db,
                    session_ids=["session-1"],
                    user_id="user-123"
                )

        assert len(result["success"]) == 1
        mock_notify.assert_called_once_with("session-1", "user-123", "agent-123")

    def test_batch_delete_exception_handling(self, session_service, mock_db):
        """Test that exceptions during deletion are handled gracefully."""
        with patch.object(session_service, '_get_repositories') as mock_get_repos:
            mock_repo = Mock()
            mock_repo.find_user_session = Mock(side_effect=Exception("Database error"))
            mock_get_repos.return_value = mock_repo

            result = session_service.batch_delete_sessions(
                db=mock_db,
                session_ids=["session-1"],
                user_id="user-123"
            )

        assert len(result["success"]) == 0
        assert len(result["failed"]) == 1
        assert "Database error" in result["failed"][0]["reason"]
