"""Unit tests for SessionService.move_session_to_project method."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService


class TestSessionServiceMoveToProject:
    """Test the move_session_to_project method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_component = Mock()
        self.service = SessionService(component=self.mock_component)
        self.mock_db = Mock()
        self.session_id = "test-session-123"
        self.user_id = "user-123"
        self.project_id = "project-456"

    @pytest.mark.asyncio
    async def test_move_session_validates_project_access_for_owner(self):
        """Test that moving session validates user has access to target project (owner)."""
        # Mock the project service to return a valid project (user is owner)
        with patch('solace_agent_mesh.gateway.http_sse.services.project_service.ProjectService') as MockProjectService:
            mock_project_service = Mock()
            mock_project = Mock()
            mock_project.id = self.project_id
            mock_project_service.get_project.return_value = mock_project
            MockProjectService.return_value = mock_project_service

            # Mock session repository
            mock_repository = Mock()
            mock_updated_session = Mock()
            mock_updated_session.id = self.session_id
            mock_updated_session.project_id = self.project_id
            mock_repository.move_to_project.return_value = mock_updated_session

            with patch.object(self.service, '_get_repositories', return_value=mock_repository):
                # Execute
                result = await self.service.move_session_to_project(
                    db=self.mock_db,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    new_project_id=self.project_id
                )

                # Assert project access was checked
                mock_project_service.get_project.assert_called_once_with(
                    self.mock_db, self.project_id, self.user_id
                )

                # Assert session was moved
                assert result is not None
                assert result.project_id == self.project_id

    @pytest.mark.asyncio
    async def test_move_session_validates_project_access_for_shared_viewer(self):
        """Test that moving session validates user has access to target project (shared viewer)."""
        # Mock the project service to return a valid project (user has viewer access via sharing)
        with patch('solace_agent_mesh.gateway.http_sse.services.project_service.ProjectService') as MockProjectService:
            mock_project_service = Mock()
            mock_project = Mock()
            mock_project.id = self.project_id
            mock_project_service.get_project.return_value = mock_project  # Has access via sharing
            MockProjectService.return_value = mock_project_service

            # Mock session repository
            mock_repository = Mock()
            mock_updated_session = Mock()
            mock_updated_session.id = self.session_id
            mock_updated_session.project_id = self.project_id
            mock_repository.move_to_project.return_value = mock_updated_session

            with patch.object(self.service, '_get_repositories', return_value=mock_repository):
                # Execute
                result = await self.service.move_session_to_project(
                    db=self.mock_db,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    new_project_id=self.project_id
                )

                # Assert project access was checked
                mock_project_service.get_project.assert_called_once()

                # Assert session was moved (user has viewer access)
                assert result is not None
                assert result.project_id == self.project_id

    @pytest.mark.asyncio
    async def test_move_session_rejects_nonexistent_project(self):
        """Test that moving session to non-existent project raises ValueError."""
        # Mock the project service to return None (project doesn't exist or no access)
        with patch('solace_agent_mesh.gateway.http_sse.services.project_service.ProjectService') as MockProjectService:
            mock_project_service = Mock()
            mock_project_service.get_project.return_value = None  # No access or doesn't exist
            MockProjectService.return_value = mock_project_service

            # Execute and expect ValueError
            with pytest.raises(ValueError, match="not found or access denied"):
                await self.service.move_session_to_project(
                    db=self.mock_db,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    new_project_id=self.project_id
                )

            # Assert project access was checked
            mock_project_service.get_project.assert_called_once_with(
                self.mock_db, self.project_id, self.user_id
            )

    @pytest.mark.asyncio
    async def test_move_session_allows_removing_from_project(self):
        """Test that moving session with None project_id removes it from project."""
        # Mock session repository
        mock_repository = Mock()
        mock_updated_session = Mock()
        mock_updated_session.id = self.session_id
        mock_updated_session.project_id = None
        mock_repository.move_to_project.return_value = mock_updated_session

        with patch.object(self.service, '_get_repositories', return_value=mock_repository):
            # Execute with None project_id
            result = await self.service.move_session_to_project(
                db=self.mock_db,
                session_id=self.session_id,
                user_id=self.user_id,
                new_project_id=None  # Remove from project
            )

            # Assert session was moved (project_id = None)
            assert result is not None
            assert result.project_id is None

            # Project access should NOT be checked when removing from project
            mock_repository.move_to_project.assert_called_once_with(
                self.mock_db, self.session_id, self.user_id, None
            )
