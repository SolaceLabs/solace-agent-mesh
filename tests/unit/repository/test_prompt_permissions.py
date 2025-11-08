"""
Unit tests for prompt sharing permission helpers.

Tests the permission checking logic including:
1. get_user_role() - determining user's role for a prompt
2. check_permission() - enforcing role-based access control
3. Permission levels for owner, editor, and viewer roles
"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.solace_agent_mesh.gateway.http_sse.repository.models import (
    PromptGroupModel,
    PromptGroupUserModel,
)
from src.solace_agent_mesh.gateway.http_sse.routers.prompts import (
    get_user_role,
    check_permission,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    return Mock(spec=Session)


class TestGetUserRole:
    """Tests for get_user_role helper function"""

    def test_returns_owner_when_user_owns_group(self, mock_db_session):
        """Test that owner role is returned when user owns the prompt group"""
        # Setup: User owns the group
        mock_group = Mock(id="group-1", user_id="alice")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_group
        mock_db_session.query.return_value = mock_query
        
        # Execute
        role = get_user_role(mock_db_session, "group-1", "alice")
        
        # Verify
        assert role == "owner"

    def test_returns_editor_when_user_has_editor_share(self, mock_db_session):
        """Test that editor role is returned when user has editor access"""
        # Setup: User doesn't own but has editor share
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="editor")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute
        role = get_user_role(mock_db_session, "group-1", "bob")
        
        # Verify
        assert role == "editor"

    def test_returns_viewer_when_user_has_viewer_share(self, mock_db_session):
        """Test that viewer role is returned when user has viewer access"""
        # Setup: User doesn't own but has viewer share
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="viewer")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute
        role = get_user_role(mock_db_session, "group-1", "charlie")
        
        # Verify
        assert role == "viewer"

    def test_returns_none_when_user_has_no_access(self, mock_db_session):
        """Test that None is returned when user has no access"""
        # Setup: User doesn't own and has no share
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = None
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute
        role = get_user_role(mock_db_session, "group-1", "dave")
        
        # Verify
        assert role is None


class TestCheckPermission:
    """Tests for check_permission helper function"""

    def test_read_permission_allowed_for_owner(self, mock_db_session):
        """Test that owner can read"""
        # Setup
        mock_group = Mock(id="group-1", user_id="alice")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_group
        mock_db_session.query.return_value = mock_query
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "alice", "read")

    def test_read_permission_allowed_for_editor(self, mock_db_session):
        """Test that editor can read"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="editor")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "bob", "read")

    def test_read_permission_allowed_for_viewer(self, mock_db_session):
        """Test that viewer can read"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="viewer")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "charlie", "read")

    def test_write_permission_allowed_for_owner(self, mock_db_session):
        """Test that owner can write"""
        # Setup
        mock_group = Mock(id="group-1", user_id="alice")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_group
        mock_db_session.query.return_value = mock_query
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "alice", "write")

    def test_write_permission_allowed_for_editor(self, mock_db_session):
        """Test that editor can write"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="editor")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "bob", "write")

    def test_write_permission_denied_for_viewer(self, mock_db_session):
        """Test that viewer cannot write"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="viewer")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should raise 403
        with pytest.raises(HTTPException) as exc_info:
            check_permission(mock_db_session, "group-1", "charlie", "write")
        
        assert exc_info.value.status_code == 403
        assert "viewer" in exc_info.value.detail.lower()

    def test_delete_permission_allowed_for_owner(self, mock_db_session):
        """Test that owner can delete"""
        # Setup
        mock_group = Mock(id="group-1", user_id="alice")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_group
        mock_db_session.query.return_value = mock_query
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "alice", "delete")

    def test_delete_permission_allowed_for_editor(self, mock_db_session):
        """Test that editor can delete"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="editor")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should not raise
        check_permission(mock_db_session, "group-1", "bob", "delete")

    def test_delete_permission_denied_for_viewer(self, mock_db_session):
        """Test that viewer cannot delete"""
        # Setup
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_share = Mock(role="viewer")
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = mock_share
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should raise 403
        with pytest.raises(HTTPException) as exc_info:
            check_permission(mock_db_session, "group-1", "charlie", "delete")
        
        assert exc_info.value.status_code == 403
        assert "viewer" in exc_info.value.detail.lower()

    def test_permission_denied_when_no_access(self, mock_db_session):
        """Test that 404 is raised when user has no access"""
        # Setup: User has no access
        mock_query_group = MagicMock()
        mock_query_group.filter.return_value.first.return_value = None
        
        mock_query_share = MagicMock()
        mock_query_share.filter.return_value.first.return_value = None
        
        mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute - should raise 404 (to hide existence)
        with pytest.raises(HTTPException) as exc_info:
            check_permission(mock_db_session, "group-1", "dave", "read")
        
        assert exc_info.value.status_code == 404


class TestPermissionMatrix:
    """Test complete permission matrix for all roles"""

    @pytest.mark.parametrize("role,permission,should_allow", [
        # Owner permissions
        ("owner", "read", True),
        ("owner", "write", True),
        ("owner", "delete", True),
        # Editor permissions
        ("editor", "read", True),
        ("editor", "write", True),
        ("editor", "delete", True),
        # Viewer permissions
        ("viewer", "read", True),
        ("viewer", "write", False),
        ("viewer", "delete", False),
    ])
    def test_permission_matrix(self, mock_db_session, role, permission, should_allow):
        """Test complete permission matrix for all role/permission combinations"""
        # Setup based on role
        if role == "owner":
            mock_group = Mock(id="group-1", user_id="user-1")
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = mock_group
            mock_db_session.query.return_value = mock_query
        else:
            mock_query_group = MagicMock()
            mock_query_group.filter.return_value.first.return_value = None
            
            mock_share = Mock(role=role)
            mock_query_share = MagicMock()
            mock_query_share.filter.return_value.first.return_value = mock_share
            
            mock_db_session.query.side_effect = [mock_query_group, mock_query_share]
        
        # Execute
        if should_allow:
            # Should not raise
            check_permission(mock_db_session, "group-1", "user-1", permission)
        else:
            # Should raise 403
            with pytest.raises(HTTPException) as exc_info:
                check_permission(mock_db_session, "group-1", "user-1", permission)
            assert exc_info.value.status_code == 403