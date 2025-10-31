"""
Unit tests for ProjectUserRepository

Tests the project user access repository layer including:
1. Adding users to projects with different roles
2. Querying user access to projects
3. Updating user roles
4. Removing user access
5. Access validation
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from src.solace_agent_mesh.gateway.http_sse.repository.project_user_repository import ProjectUserRepository
from src.solace_agent_mesh.gateway.http_sse.repository.models import ProjectUserModel
from src.solace_agent_mesh.gateway.http_sse.repository.entities.project_user import ProjectUser


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def project_user_repo(mock_db_session):
    """Create a ProjectUserRepository instance with mock session"""
    return ProjectUserRepository(mock_db_session)


class TestAddUserToProject:
    """Tests for adding users to projects"""

    def test_add_user_creates_record_with_correct_data(self, project_user_repo, mock_db_session):
        """Test that adding a user creates a record with correct data"""
        # Setup
        project_id = "proj-123"
        user_id = "user-456"
        role = "editor"
        added_by = "user-owner"
        
        # Execute
        result = project_user_repo.add_user_to_project(
            project_id=project_id,
            user_id=user_id,
            role=role,
            added_by_user_id=added_by
        )
        
        # Verify
        assert mock_db_session.add.called
        assert mock_db_session.commit.called
        assert mock_db_session.refresh.called
        
        # Check the model that was added
        added_model = mock_db_session.add.call_args[0][0]
        assert isinstance(added_model, ProjectUserModel)
        assert added_model.project_id == project_id
        assert added_model.user_id == user_id
        assert added_model.role == role
        assert added_model.added_by_user_id == added_by
        assert added_model.id is not None
        assert added_model.added_at > 0

    def test_add_user_returns_project_user_entity(self, project_user_repo, mock_db_session):
        """Test that adding a user returns a ProjectUser entity"""
        result = project_user_repo.add_user_to_project(
            project_id="proj-123",
            user_id="user-456",
            role="viewer",
            added_by_user_id="user-owner"
        )
        
        assert isinstance(result, ProjectUser)
        assert result.project_id == "proj-123"
        assert result.user_id == "user-456"
        assert result.role == "viewer"


class TestGetProjectUsers:
    """Tests for getting users with access to a project"""

    def test_get_project_users_returns_all_users(self, project_user_repo, mock_db_session):
        """Test that get_project_users returns all users for a project"""
        # Setup mock data
        mock_models = [
            Mock(
                id="pu-1",
                project_id="proj-123",
                user_id="user-1",
                role="owner",
                added_at=1000,
                added_by_user_id="user-1"
            ),
            Mock(
                id="pu-2",
                project_id="proj-123",
                user_id="user-2",
                role="editor",
                added_at=2000,
                added_by_user_id="user-1"
            ),
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = mock_models
        mock_db_session.query.return_value = mock_query
        
        # Execute
        result = project_user_repo.get_project_users("proj-123")
        
        # Verify
        assert len(result) == 2
        assert all(isinstance(pu, ProjectUser) for pu in result)
        assert result[0].user_id == "user-1"
        assert result[1].user_id == "user-2"

    def test_get_project_users_returns_empty_list_when_no_users(self, project_user_repo, mock_db_session):
        """Test that get_project_users returns empty list when no users have access"""
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.get_project_users("proj-123")
        
        assert result == []


class TestGetUserProjectsAccess:
    """Tests for getting projects a user has access to"""

    def test_get_user_projects_access_returns_all_projects(self, project_user_repo, mock_db_session):
        """Test that get_user_projects_access returns all projects for a user"""
        mock_models = [
            Mock(
                id="pu-1",
                project_id="proj-1",
                user_id="user-123",
                role="owner",
                added_at=1000,
                added_by_user_id="user-123"
            ),
            Mock(
                id="pu-2",
                project_id="proj-2",
                user_id="user-123",
                role="viewer",
                added_at=2000,
                added_by_user_id="user-456"
            ),
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = mock_models
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.get_user_projects_access("user-123")
        
        assert len(result) == 2
        assert result[0].project_id == "proj-1"
        assert result[1].project_id == "proj-2"


class TestGetUserProjectAccess:
    """Tests for getting specific user's access to a project"""

    def test_get_user_project_access_returns_access_when_exists(self, project_user_repo, mock_db_session):
        """Test that get_user_project_access returns access record when it exists"""
        mock_model = Mock(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="editor",
            added_at=1000,
            added_by_user_id="user-owner"
        )
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_model
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.get_user_project_access("proj-123", "user-456")
        
        assert result is not None
        assert isinstance(result, ProjectUser)
        assert result.role == "editor"

    def test_get_user_project_access_returns_none_when_not_exists(self, project_user_repo, mock_db_session):
        """Test that get_user_project_access returns None when access doesn't exist"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.get_user_project_access("proj-123", "user-456")
        
        assert result is None


class TestUpdateUserRole:
    """Tests for updating user roles"""

    def test_update_user_role_updates_and_returns_entity(self, project_user_repo, mock_db_session):
        """Test that update_user_role updates the role and returns updated entity"""
        mock_model = Mock(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="viewer",
            added_at=1000,
            added_by_user_id="user-owner"
        )
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_model
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.update_user_role("proj-123", "user-456", "editor")
        
        assert mock_model.role == "editor"
        assert mock_db_session.commit.called
        assert mock_db_session.refresh.called
        assert isinstance(result, ProjectUser)
        assert result.role == "editor"

    def test_update_user_role_returns_none_when_not_found(self, project_user_repo, mock_db_session):
        """Test that update_user_role returns None when access record not found"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.update_user_role("proj-123", "user-456", "editor")
        
        assert result is None
        assert not mock_db_session.commit.called


class TestRemoveUserFromProject:
    """Tests for removing user access"""

    def test_remove_user_from_project_deletes_and_returns_true(self, project_user_repo, mock_db_session):
        """Test that remove_user_from_project deletes record and returns True"""
        mock_query = MagicMock()
        mock_query.filter.return_value.delete.return_value = 1
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.remove_user_from_project("proj-123", "user-456")
        
        assert result is True
        assert mock_db_session.commit.called

    def test_remove_user_from_project_returns_false_when_not_found(self, project_user_repo, mock_db_session):
        """Test that remove_user_from_project returns False when record not found"""
        mock_query = MagicMock()
        mock_query.filter.return_value.delete.return_value = 0
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.remove_user_from_project("proj-123", "user-456")
        
        assert result is False


class TestUserHasAccess:
    """Tests for checking user access"""

    def test_user_has_access_returns_true_when_access_exists(self, project_user_repo, mock_db_session):
        """Test that user_has_access returns True when user has access"""
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.user_has_access("proj-123", "user-456")
        
        assert result is True

    def test_user_has_access_returns_false_when_no_access(self, project_user_repo, mock_db_session):
        """Test that user_has_access returns False when user has no access"""
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 0
        mock_db_session.query.return_value = mock_query
        
        result = project_user_repo.user_has_access("proj-123", "user-456")
        
        assert result is False


class TestProjectUserEntity:
    """Tests for ProjectUser entity business logic"""

    def test_can_edit_project_returns_true_for_owner(self):
        """Test that owners can edit projects"""
        user = ProjectUser(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="owner",
            added_at=1000,
            added_by_user_id="user-456"
        )
        
        assert user.can_edit_project() is True

    def test_can_edit_project_returns_true_for_editor(self):
        """Test that editors can edit projects"""
        user = ProjectUser(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="editor",
            added_at=1000,
            added_by_user_id="user-owner"
        )
        
        assert user.can_edit_project() is True

    def test_can_edit_project_returns_false_for_viewer(self):
        """Test that viewers cannot edit projects"""
        user = ProjectUser(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="viewer",
            added_at=1000,
            added_by_user_id="user-owner"
        )
        
        assert user.can_edit_project() is False

    def test_can_manage_users_returns_true_only_for_owner(self):
        """Test that only owners can manage users"""
        owner = ProjectUser(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="owner",
            added_at=1000,
            added_by_user_id="user-456"
        )
        
        editor = ProjectUser(
            id="pu-2",
            project_id="proj-123",
            user_id="user-789",
            role="editor",
            added_at=1000,
            added_by_user_id="user-456"
        )
        
        assert owner.can_manage_users() is True
        assert editor.can_manage_users() is False

    def test_can_view_project_returns_true_for_all_roles(self):
        """Test that all roles can view projects"""
        for role in ["owner", "editor", "viewer"]:
            user = ProjectUser(
                id="pu-1",
                project_id="proj-123",
                user_id="user-456",
                role=role,
                added_at=1000,
                added_by_user_id="user-owner"
            )
            assert user.can_view_project() is True

    def test_update_role_validates_role(self):
        """Test that update_role validates the new role"""
        user = ProjectUser(
            id="pu-1",
            project_id="proj-123",
            user_id="user-456",
            role="viewer",
            added_at=1000,
            added_by_user_id="user-owner"
        )
        
        # Valid role should work
        user.update_role("editor")
        assert user.role == "editor"
        
        # Invalid role should raise ValueError
        with pytest.raises(ValueError, match="Invalid role"):
            user.update_role("invalid_role")