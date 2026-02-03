"""Tests for ProjectRepository.get_accessible_projects() method."""
import pytest
from unittest.mock import Mock, MagicMock
from solace_agent_mesh.gateway.http_sse.repository.project_repository import (
    ProjectRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.models import ProjectModel


class TestProjectRepositoryAccessibleProjects:
    """Test get_accessible_projects method in ProjectRepository."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.repo = ProjectRepository(self.mock_db)

    def _create_mock_project(self, project_id, name, user_id):
        """Helper to create a mock project with all required fields."""
        project = Mock(spec=ProjectModel)
        project.id = project_id
        project.name = name
        project.user_id = user_id
        project.description = f"Description for {name}"
        project.system_prompt = f"Prompt for {name}"
        project.default_agent_id = None
        project.created_at = 1234567890000
        project.updated_at = 1234567890000
        project.deleted_at = None
        project.deleted_by = None
        return project

    def test_get_accessible_projects_returns_only_owned_when_no_shared_ids(self):
        """Test that get_accessible_projects returns only owned projects when shared_project_ids is None."""
        user_email = "user@example.com"

        # Mock owned projects
        owned_project1 = self._create_mock_project("owned-1", "Owned Project 1", user_email)
        owned_project2 = self._create_mock_project("owned-2", "Owned Project 2", user_email)

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [owned_project1, owned_project2]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(user_email, shared_project_ids=None)

        # Assert
        assert len(result) == 2
        assert result[0].id == "owned-1"
        assert result[1].id == "owned-2"

    def test_get_accessible_projects_returns_only_owned_when_empty_shared_list(self):
        """Test that get_accessible_projects returns only owned projects when shared_project_ids is empty list."""
        user_email = "user@example.com"

        # Mock owned project
        owned_project = self._create_mock_project("owned-1", "Owned Project", user_email)

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [owned_project]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(user_email, shared_project_ids=[])

        # Assert
        assert len(result) == 1
        assert result[0].id == "owned-1"

    def test_get_accessible_projects_includes_shared_projects(self):
        """Test that get_accessible_projects includes both owned and shared projects."""
        user_email = "user@example.com"

        # Mock owned and shared projects
        owned_project = self._create_mock_project("owned-1", "Owned Project", user_email)
        shared_project = self._create_mock_project("shared-1", "Shared Project", "other@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [owned_project, shared_project]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(
            user_email, shared_project_ids=["shared-1"]
        )

        # Assert
        assert len(result) == 2
        project_ids = [p.id for p in result]
        assert "owned-1" in project_ids
        assert "shared-1" in project_ids

    def test_get_accessible_projects_excludes_deleted_projects(self):
        """Test that get_accessible_projects filters out soft-deleted projects."""
        user_email = "user@example.com"

        # Mock active project
        active_project = self._create_mock_project("active-1", "Active Project", user_email)

        # Mock query chain - deleted projects already filtered by query
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [active_project]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(user_email, shared_project_ids=None)

        # Assert: deleted_at.is_(None) filter is applied in query
        assert len(result) == 1
        assert result[0].id == "active-1"

    def test_get_filtered_projects_with_user_filter(self):
        """Test get_filtered_projects filters by user_id."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.requests.project_requests import ProjectFilter

        user1_project = self._create_mock_project("proj-1", "User 1 Project", "user1@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [user1_project]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test with user filter
        project_filter = ProjectFilter(user_id="user1@example.com")
        result = self.repo.get_filtered_projects(project_filter)

        # Assert
        assert len(result) == 1
        assert result[0].id == "proj-1"
        assert result[0].user_id == "user1@example.com"

    def test_get_filtered_projects_without_user_filter(self):
        """Test get_filtered_projects returns all projects when no filter."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.requests.project_requests import ProjectFilter

        project1 = self._create_mock_project("proj-1", "Project 1", "user1@example.com")
        project2 = self._create_mock_project("proj-2", "Project 2", "user2@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [project1, project2]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test without user filter
        project_filter = ProjectFilter(user_id=None)
        result = self.repo.get_filtered_projects(project_filter)

        # Assert
        assert len(result) == 2

    def test_get_accessible_projects_handles_empty_result(self):
        """Test that get_accessible_projects returns empty list when no projects found."""
        user_email = "newuser@example.com"

        # Mock empty query result
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = []
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(user_email, shared_project_ids=None)

        # Assert
        assert result == []

    def test_get_accessible_projects_with_multiple_shared_projects(self):
        """Test that get_accessible_projects handles multiple shared project IDs."""
        user_email = "user@example.com"

        # Mock multiple shared projects
        shared1 = self._create_mock_project("shared-1", "Shared 1", "owner1@example.com")
        shared2 = self._create_mock_project("shared-2", "Shared 2", "owner2@example.com")
        shared3 = self._create_mock_project("shared-3", "Shared 3", "owner3@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [shared1, shared2, shared3]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_accessible_projects(
            user_email, shared_project_ids=["shared-1", "shared-2", "shared-3"]
        )

        # Assert
        assert len(result) == 3
        project_ids = [p.id for p in result]
        assert "shared-1" in project_ids
        assert "shared-2" in project_ids
        assert "shared-3" in project_ids

    def test_get_all_projects_returns_all_non_deleted(self):
        """Test that get_all_projects returns all non-deleted projects."""
        # Mock projects
        project1 = self._create_mock_project("proj-1", "Project 1", "user1@example.com")
        project2 = self._create_mock_project("proj-2", "Project 2", "user2@example.com")
        project3 = self._create_mock_project("proj-3", "Project 3", "user3@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [project1, project2, project3]
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_all_projects()

        # Assert
        assert len(result) == 3
        project_ids = [p.id for p in result]
        assert "proj-1" in project_ids
        assert "proj-2" in project_ids
        assert "proj-3" in project_ids

    def test_get_by_id_returns_project_when_found(self):
        """Test get_by_id returns project when it exists."""
        project = self._create_mock_project("proj-1", "Test Project", "user@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = project
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_by_id("proj-1")

        # Assert
        assert result is not None
        assert result.id == "proj-1"
        assert result.name == "Test Project"

    def test_get_by_id_returns_none_when_not_found(self):
        """Test get_by_id returns None when project doesn't exist."""
        # Mock query chain returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.get_by_id("nonexistent-id")

        # Assert
        assert result is None

    def test_update_modifies_project_fields(self):
        """Test update modifies project fields and returns updated project."""
        project = self._create_mock_project("proj-1", "Old Name", "user@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = project
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        update_data = {"name": "New Name", "description": "New Description"}
        result = self.repo.update("proj-1", update_data)

        # Assert
        assert result is not None
        assert result.name == "New Name"
        assert result.description == "New Description"
        assert self.mock_db.flush.called
        assert self.mock_db.refresh.called

    def test_update_returns_none_when_project_not_found(self):
        """Test update returns None when project doesn't exist."""
        # Mock query chain returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.update("nonexistent-id", {"name": "New Name"})

        # Assert
        assert result is None

    def test_delete_removes_project_and_returns_true(self):
        """Test delete removes project and returns True."""
        # Mock query chain with delete
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.delete.return_value = 1  # 1 row deleted
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.delete("proj-1")

        # Assert
        assert result is True
        assert self.mock_db.flush.called

    def test_delete_returns_false_when_project_not_found(self):
        """Test delete returns False when project doesn't exist."""
        # Mock query chain with no deletion
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.delete.return_value = 0  # 0 rows deleted
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.delete("nonexistent-id")

        # Assert
        assert result is False

    def test_soft_delete_marks_project_as_deleted(self):
        """Test soft_delete marks project with deleted_at timestamp."""
        project = self._create_mock_project("proj-1", "Project", "user@example.com")

        # Mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = project
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.soft_delete("proj-1", "deleting-user@example.com")

        # Assert
        assert result is True
        assert project.deleted_at is not None
        assert project.deleted_by == "deleting-user@example.com"
        assert self.mock_db.flush.called

    def test_soft_delete_returns_false_when_project_not_found(self):
        """Test soft_delete returns False when project doesn't exist."""
        # Mock query chain returning None
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        self.mock_db.query.return_value = mock_query

        # Test
        result = self.repo.soft_delete("nonexistent-id", "deleting-user@example.com")

        # Assert
        assert result is False
