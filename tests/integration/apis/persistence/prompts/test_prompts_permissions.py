"""
Integration tests for prompt permission checking.

Tests permission helper functions against real SQLite and PostgreSQL databases.
These tests replace the mocked unit tests in tests/unit/repository/test_prompt_permissions.py
which used mocked DB sessions.

All tests in this file run against both SQLite and PostgreSQL via pytest parametrization.
Docker must be running for PostgreSQL tests (testcontainers handles container lifecycle).
"""

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.prompts import (
    check_permission,
    get_user_role,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestGetUserRole:
    """Tests for get_user_role helper function with real database."""

    def test_returns_owner_when_user_owns_group(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that owner role is returned when user owns the prompt group."""
        # Arrange: Create prompt group owned by alice
        group_id = "group-owner-test"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Alice's Prompt Group",
            user_id="alice",
        )

        # Act: Get role for alice
        with db_session_factory() as db_session:
            role = get_user_role(db_session, group_id, "alice")

        # Assert
        assert role == "owner"

    def test_returns_editor_when_user_has_editor_share(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that editor role is returned when user has editor access via sharing."""
        # Arrange: Create prompt group owned by alice
        group_id = "group-editor-test"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Prompt Group",
            user_id="alice",
        )

        # Add bob as editor via direct DB insert
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]

            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-editor-1",
                    prompt_group_id=group_id,
                    user_id="bob",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act: Get role for bob
        with db_session_factory() as db_session:
            role = get_user_role(db_session, group_id, "bob")

        # Assert
        assert role == "editor"  # get_user_role returns lowercase

    def test_returns_viewer_when_user_has_viewer_share(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that viewer role is returned when user has viewer access via sharing."""
        # Arrange: Create prompt group owned by alice
        group_id = "group-viewer-test"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Prompt Group",
            user_id="alice",
        )

        # Add charlie as viewer
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]

            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-viewer-1",
                    prompt_group_id=group_id,
                    user_id="charlie",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act: Get role for charlie
        with db_session_factory() as db_session:
            role = get_user_role(db_session, group_id, "charlie")

        # Assert
        assert role == "viewer"  # get_user_role returns lowercase

    def test_returns_none_when_user_has_no_access(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that None is returned when user has no access to the group."""
        # Arrange: Create prompt group owned by alice (no sharing)
        group_id = "group-no-access-test"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Prompt Group",
            user_id="alice",
        )

        # Act: Get role for dave (who has no access)
        with db_session_factory() as db_session:
            role = get_user_role(db_session, group_id, "dave")

        # Assert
        assert role is None


class TestCheckPermission:
    """Tests for check_permission helper function with real database."""

    def test_read_permission_allowed_for_owner(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that owner can read prompts."""
        # Arrange: Create prompt group
        group_id = "group-read-owner"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Owner's Group",
            user_id="alice",
        )

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "alice", "read")

    def test_read_permission_allowed_for_editor(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that editor can read prompts."""
        # Arrange: Create prompt group and add editor
        group_id = "group-read-editor"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-read-editor",
                    prompt_group_id=group_id,
                    user_id="bob",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "bob", "read")

    def test_read_permission_allowed_for_viewer(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that viewer can read prompts."""
        # Arrange: Create prompt group and add viewer
        group_id = "group-read-viewer"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-read-viewer",
                    prompt_group_id=group_id,
                    user_id="charlie",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "charlie", "read")

    def test_write_permission_allowed_for_owner(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that owner can write to prompts."""
        # Arrange
        group_id = "group-write-owner"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Owner's Group",
            user_id="alice",
        )

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "alice", "write")

    def test_write_permission_allowed_for_editor(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that editor can write to prompts."""
        # Arrange: Create group and add editor
        group_id = "group-write-editor"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-write-editor",
                    prompt_group_id=group_id,
                    user_id="bob",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "bob", "write")

    def test_write_permission_denied_for_viewer(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that viewer cannot write to prompts."""
        # Arrange: Create group and add viewer
        group_id = "group-write-viewer-deny"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-write-viewer-deny",
                    prompt_group_id=group_id,
                    user_id="charlie",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should raise 403
        with db_session_factory() as db_session:
            with pytest.raises(HTTPException) as exc_info:
                check_permission(db_session, group_id, "charlie", "write")

        assert exc_info.value.status_code == 403

    def test_delete_permission_allowed_for_owner(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that owner can delete prompts."""
        # Arrange
        group_id = "group-delete-owner"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Owner's Group",
            user_id="alice",
        )

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "alice", "delete")

    def test_delete_permission_allowed_for_editor(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that editor can delete prompts."""
        # Arrange: Create group and add editor
        group_id = "group-delete-editor"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-delete-editor",
                    prompt_group_id=group_id,
                    user_id="bob",
                    role="EDITOR",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should not raise
        with db_session_factory() as db_session:
            check_permission(db_session, group_id, "bob", "delete")

    def test_delete_permission_denied_for_viewer(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that viewer cannot delete prompts."""
        # Arrange: Create group and add viewer
        group_id = "group-delete-viewer-deny"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Shared Group",
            user_id="alice",
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            group_users_table = metadata.tables["prompt_group_users"]
            conn.execute(
                sa.insert(group_users_table).values(
                    id="pgu-delete-viewer-deny",
                    prompt_group_id=group_id,
                    user_id="charlie",
                    role="VIEWER",
                    added_at=now_epoch_ms(),
                    added_by_user_id="alice",
                )
            )
            conn.commit()

        # Act & Assert: Should raise 403
        with db_session_factory() as db_session:
            with pytest.raises(HTTPException) as exc_info:
                check_permission(db_session, group_id, "charlie", "delete")

        assert exc_info.value.status_code == 403

    def test_permission_denied_when_no_access(
        self,
        gateway_adapter: GatewayAdapter,
        db_session_factory,
    ):
        """Test that 404 is raised when user has no access to the group."""
        # Arrange: Create prompt group owned by alice (no sharing)
        group_id = "group-no-access"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Group",
            user_id="alice",
        )

        # Act & Assert: Should raise 404 for dave (no access)
        with db_session_factory() as db_session:
            with pytest.raises(HTTPException) as exc_info:
                check_permission(db_session, group_id, "dave", "read")

        assert exc_info.value.status_code == 404


class TestPermissionMatrix:
    """Test complete permission matrix for all roles with real database."""

    @pytest.mark.parametrize(
        "role,permission,should_allow",
        [
            # Owner permissions
            ("OWNER", "read", True),
            ("OWNER", "write", True),
            ("OWNER", "delete", True),
            # Editor permissions
            ("EDITOR", "read", True),
            ("EDITOR", "write", True),
            ("EDITOR", "delete", True),
            # Viewer permissions
            ("VIEWER", "read", True),
            ("VIEWER", "write", False),
            ("VIEWER", "delete", False),
        ],
    )
    def test_permission_matrix(
        self,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
        role,
        permission,
        should_allow,
    ):
        """Test complete permission matrix for all role/permission combinations."""
        # Arrange: Create unique group for this test case
        group_id = f"group-matrix-{role}-{permission}"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name=f"Permission Test Group - {role}/{permission}",
            user_id="alice",
        )

        # Add user with specified role (if not owner)
        test_user = "alice" if role == "OWNER" else "test-user"
        if role != "OWNER":
            with database_inspector.db_manager.get_gateway_connection() as conn:
                metadata = sa.MetaData()
                metadata.reflect(bind=conn)
                group_users_table = metadata.tables["prompt_group_users"]
                conn.execute(
                    sa.insert(group_users_table).values(
                        id=f"pgu-matrix-{role}-{permission}",
                        prompt_group_id=group_id,
                        user_id=test_user,
                        role=role,  # Already uppercase from parametrize
                        added_at=now_epoch_ms(),
                        added_by_user_id="alice",
                    )
                )
                conn.commit()

        # Act & Assert
        with db_session_factory() as db_session:
            if should_allow:
                # Should not raise
                check_permission(db_session, group_id, test_user, permission)
            else:
                # Should raise 403
                with pytest.raises(HTTPException) as exc_info:
                    check_permission(db_session, group_id, test_user, permission)
                assert exc_info.value.status_code == 403
