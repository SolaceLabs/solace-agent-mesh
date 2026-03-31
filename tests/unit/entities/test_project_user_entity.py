"""
Unit tests for ProjectUser entity business logic.

Tests pure entity methods without database interactions.
Extracted from tests/unit/repository/test_project_user_repository.py
"""

import pytest

from solace_agent_mesh.gateway.http_sse.repository.entities.project_user import (
    ProjectUser,
)


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
            added_by_user_id="user-456",
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
            added_by_user_id="user-owner",
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
            added_by_user_id="user-owner",
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
            added_by_user_id="user-456",
        )

        editor = ProjectUser(
            id="pu-2",
            project_id="proj-123",
            user_id="user-789",
            role="editor",
            added_at=1000,
            added_by_user_id="user-456",
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
                added_by_user_id="user-owner",
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
            added_by_user_id="user-owner",
        )

        # Valid role should work
        user.update_role("editor")
        assert user.role == "editor"

        # Invalid role should raise ValueError
        with pytest.raises(ValueError, match="Invalid role"):
            user.update_role("invalid_role")
