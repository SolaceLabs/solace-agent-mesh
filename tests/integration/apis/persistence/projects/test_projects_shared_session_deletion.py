"""
Projects Shared Session Deletion Tests

Tests for ensuring shared users' sessions are deleted when a project is deleted.
This validates that sessions created by users with shared access to a project
are properly cleaned up during project deletion.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from solace_agent_mesh.services.resource_sharing_service import ResourceType
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestProjectSharedSessionDeletion:
    """Tests for deleting shared users' sessions when a project is deleted."""

    def test_delete_project_deletes_owner_sessions(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that deleting a project deletes the owner's sessions (baseline).

        This test validates the existing behavior where the project owner's
        sessions are deleted when the project is soft-deleted.
        """
        # Setup: Create a project and sessions for the owner
        project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        owner_user_id = "sam_dev_user"

        gateway_adapter.seed_project(
            project_id=project_id,
            name="Owner Sessions Test Project",
            user_id=owner_user_id,
        )

        # Create sessions for the owner
        session_id_1 = f"owner-session-{uuid.uuid4().hex[:8]}"
        session_id_2 = f"owner-session-{uuid.uuid4().hex[:8]}"

        gateway_adapter.seed_session_for_project(
            session_id=session_id_1,
            project_id=project_id,
            user_id=owner_user_id,
            name="Owner Session 1",
        )
        gateway_adapter.seed_session_for_project(
            session_id=session_id_2,
            project_id=project_id,
            user_id=owner_user_id,
            name="Owner Session 2",
        )

        # Verify sessions exist before deletion
        sessions_before = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_before) == 2

        # Act: Delete the project
        response = api_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

        # Assert: Owner's sessions should be soft-deleted (not visible without include_deleted)
        sessions_after = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_after) == 0

        # Sessions should still exist in DB with deleted_at set
        sessions_deleted = database_inspector.get_sessions_for_project(
            project_id, include_deleted=True
        )
        assert len(sessions_deleted) == 2

    def test_delete_project_deletes_shared_user_sessions_with_mock(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that deleting a project also deletes shared users' sessions.

        This test mocks the DefaultResourceSharingService.get_shared_users() method
        to simulate enterprise sharing behavior where users have shared access
        to projects.
        """
        # Setup: Create a project and sessions for owner and shared user
        project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        owner_user_id = "sam_dev_user"
        shared_user_email = "shared@example.com"

        gateway_adapter.seed_project(
            project_id=project_id,
            name="Shared Sessions Test Project",
            user_id=owner_user_id,
        )

        # Create sessions for the owner
        owner_session_id = f"owner-session-{uuid.uuid4().hex[:8]}"
        gateway_adapter.seed_session_for_project(
            session_id=owner_session_id,
            project_id=project_id,
            user_id=owner_user_id,
            name="Owner Session",
        )

        # Create sessions for the shared user
        shared_session_id = f"shared-session-{uuid.uuid4().hex[:8]}"
        gateway_adapter.seed_session_for_project(
            session_id=shared_session_id,
            project_id=project_id,
            user_id=shared_user_email,
            name="Shared User Session",
        )

        # Verify sessions exist before deletion
        sessions_before = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_before) == 2

        # Mock get_shared_users on the DefaultResourceSharingService class
        with patch(
            "solace_agent_mesh.common.services.default_resource_sharing_service."
            "DefaultResourceSharingService.get_shared_users"
        ) as mock_get_shared_users:
            mock_get_shared_users.return_value = [shared_user_email]

            # Act: Delete the project
            response = api_client.delete(f"/api/v1/projects/{project_id}")
            assert response.status_code == 204

            # Verify get_shared_users was called
            assert mock_get_shared_users.called

        # Assert: Both owner's and shared user's sessions should be soft-deleted
        sessions_after = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_after) == 0

        # Sessions should still exist in DB with deleted_at set
        sessions_deleted = database_inspector.get_sessions_for_project(
            project_id, include_deleted=True
        )
        assert len(sessions_deleted) == 2

    def test_delete_project_no_shared_users_still_works(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that project deletion works when there are no shared users.

        This is an edge case test for community edition behavior where
        get_shared_users returns an empty list.
        """
        # Setup: Create a project with only owner sessions
        project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        owner_user_id = "sam_dev_user"

        gateway_adapter.seed_project(
            project_id=project_id,
            name="No Shared Users Test Project",
            user_id=owner_user_id,
        )

        # Create session for the owner only
        owner_session_id = f"owner-session-{uuid.uuid4().hex[:8]}"
        gateway_adapter.seed_session_for_project(
            session_id=owner_session_id,
            project_id=project_id,
            user_id=owner_user_id,
            name="Owner Session",
        )

        # Verify session exists
        sessions_before = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_before) == 1

        # Act: Delete the project (default behavior returns empty list for get_shared_users)
        response = api_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

        # Assert: Owner's session should be soft-deleted
        sessions_after = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_after) == 0

    def test_delete_project_with_multiple_shared_users(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test project deletion cleans up sessions for multiple shared users.

        This test validates that when multiple users have shared access,
        all of their sessions are properly cleaned up.
        """
        # Setup: Create a project and sessions for owner and multiple shared users
        project_id = f"test-project-{uuid.uuid4().hex[:8]}"
        owner_user_id = "sam_dev_user"
        shared_users = [
            "shared1@example.com",
            "shared2@example.com",
            "shared3@example.com",
        ]

        gateway_adapter.seed_project(
            project_id=project_id,
            name="Multiple Shared Users Test Project",
            user_id=owner_user_id,
        )

        # Create session for the owner
        gateway_adapter.seed_session_for_project(
            session_id=f"owner-session-{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            user_id=owner_user_id,
            name="Owner Session",
        )

        # Create sessions for each shared user (some users have multiple sessions)
        for i, shared_user in enumerate(shared_users):
            gateway_adapter.seed_session_for_project(
                session_id=f"shared-session-{i}-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                user_id=shared_user,
                name=f"Shared User {i + 1} Session",
            )
            # Add an extra session for the first shared user
            if i == 0:
                gateway_adapter.seed_session_for_project(
                    session_id=f"shared-session-{i}-extra-{uuid.uuid4().hex[:8]}",
                    project_id=project_id,
                    user_id=shared_user,
                    name=f"Shared User {i + 1} Extra Session",
                )

        # Verify sessions exist (1 owner + 4 shared = 5 total)
        sessions_before = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_before) == 5

        # Mock get_shared_users on the DefaultResourceSharingService class
        with patch(
            "solace_agent_mesh.common.services.default_resource_sharing_service."
            "DefaultResourceSharingService.get_shared_users"
        ) as mock_get_shared_users:
            mock_get_shared_users.return_value = shared_users

            # Act: Delete the project
            response = api_client.delete(f"/api/v1/projects/{project_id}")
            assert response.status_code == 204

        # Assert: All sessions should be soft-deleted
        sessions_after = database_inspector.get_sessions_for_project(project_id)
        assert len(sessions_after) == 0

        # All sessions should still exist in DB with deleted_at set
        sessions_deleted = database_inspector.get_sessions_for_project(
            project_id, include_deleted=True
        )
        assert len(sessions_deleted) == 5
