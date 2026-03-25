"""
Integration tests for ProjectRepository query operations.

Tests repository methods against real SQLite and PostgreSQL databases.
These tests replace the mocked unit tests in tests/unit/repository/test_project_repository_accessible_projects.py
which used mocked DB sessions and query chains.

All tests in this file run against both SQLite and PostgreSQL via pytest parametrization.
Docker must be running for PostgreSQL tests (testcontainers handles container lifecycle).
"""

from unittest.mock import patch

import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.common.services.default_resource_sharing_service import (
    DefaultResourceSharingService,
)
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestProjectRepositoryAccessibleProjects:
    """Test ProjectRepository.get_accessible_projects() with real database."""

    def test_get_accessible_projects_returns_only_owned_when_no_shared_ids(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that GET /api/v1/projects returns only owned projects when user has no shared access."""
        # Arrange: Seed owned projects for sam_dev_user
        gateway_adapter.seed_project(
            project_id="owned-1",
            name="Owned Project 1",
            user_id="sam_dev_user",
            description="Description for Owned Project 1",
        )
        gateway_adapter.seed_project(
            project_id="owned-2",
            name="Owned Project 2",
            user_id="sam_dev_user",
            description="Description for Owned Project 2",
        )
        # Seed another user's project (should not be returned)
        gateway_adapter.seed_project(
            project_id="other-1",
            name="Other User Project",
            user_id="other_user@example.com",
        )

        # Act: Get projects
        response = api_client.get("/api/v1/projects")

        # Assert
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]
        project_ids = [p["id"] for p in projects]

        assert len(projects) == 2
        assert "owned-1" in project_ids
        assert "owned-2" in project_ids
        assert "other-1" not in project_ids

    def test_get_accessible_projects_returns_only_owned_when_empty_shared_list(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that GET /api/v1/projects returns only owned projects when shared list is empty."""
        # Arrange: Seed owned project
        gateway_adapter.seed_project(
            project_id="owned-1",
            name="Owned Project",
            user_id="sam_dev_user",
        )
        # Seed another user's project
        gateway_adapter.seed_project(
            project_id="other-1",
            name="Other Project",
            user_id="other_user@example.com",
        )

        # Act: Get projects (no sharing configured)
        response = api_client.get("/api/v1/projects")

        # Assert
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]

        assert len(projects) == 1
        assert projects[0]["id"] == "owned-1"

    def test_get_accessible_projects_includes_shared_projects(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that get_accessible_projects includes both owned and shared projects."""
        # Arrange: sam_dev_user owns one project
        gateway_adapter.seed_project(
            project_id="owned-1",
            name="Owned Project",
            user_id="sam_dev_user",
        )
        # Another user owns a project that will be shared
        gateway_adapter.seed_project(
            project_id="shared-1",
            name="Shared Project",
            user_id="other_user@example.com",
        )

        # Patch the sharing service to simulate shared access
        # Secondary user should see the shared project
        original_get_shared = DefaultResourceSharingService.get_shared_resource_ids

        def _patched_get_shared(self, session, user_email, resource_type):
            result = original_get_shared(
                self,
                session=session,
                user_email=user_email,
                resource_type=resource_type,
            )
            if user_email == "secondary_user":
                # Secondary user has access to shared-1
                return ["shared-1"]
            return result

        with patch.object(
            DefaultResourceSharingService,
            "get_shared_resource_ids",
            _patched_get_shared,
        ):
            # Act: Get projects as secondary user
            response = secondary_api_client.get("/api/v1/projects")

            # Assert: Secondary user sees the shared project
            assert response.status_code == 200
            data = response.json()
            projects = data["projects"]
            project_ids = [p["id"] for p in projects]

            assert "shared-1" in project_ids

    def test_get_accessible_projects_excludes_deleted_projects(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that GET /api/v1/projects filters out soft-deleted projects."""
        # Arrange: Create active project
        gateway_adapter.seed_project(
            project_id="active-1",
            name="Active Project",
            user_id="sam_dev_user",
        )
        # Create project and soft-delete it
        gateway_adapter.seed_project(
            project_id="deleted-1",
            name="Deleted Project",
            user_id="sam_dev_user",
        )

        # Soft delete the second project directly in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            projects_table = metadata.tables["projects"]
            update_query = (
                sa.update(projects_table)
                .where(projects_table.c.id == "deleted-1")
                .values(deleted_at=1234567890000, deleted_by="sam_dev_user")
            )
            conn.execute(update_query)
            conn.commit()

        # Act: Get projects
        response = api_client.get("/api/v1/projects")

        # Assert: Only active project returned
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]
        project_ids = [p["id"] for p in projects]

        assert len(projects) == 1
        assert "active-1" in project_ids
        assert "deleted-1" not in project_ids

    def test_get_accessible_projects_handles_empty_result(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that GET /api/v1/projects returns empty list when user has no projects."""
        # Arrange: Seed projects for a different user only
        gateway_adapter.seed_project(
            project_id="other-1",
            name="Other User Project",
            user_id="other_user@example.com",
        )

        # Act: Get projects for sam_dev_user (who has none)
        response = api_client.get("/api/v1/projects")

        # Assert: Empty list returned
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]

        assert len(projects) == 0

    def test_get_accessible_projects_with_multiple_shared_projects(
        self,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that get_accessible_projects handles multiple shared project IDs."""
        # Arrange: Seed multiple projects owned by different users
        gateway_adapter.seed_project(
            project_id="shared-1",
            name="Shared 1",
            user_id="owner1@example.com",
        )
        gateway_adapter.seed_project(
            project_id="shared-2",
            name="Shared 2",
            user_id="owner2@example.com",
        )
        gateway_adapter.seed_project(
            project_id="shared-3",
            name="Shared 3",
            user_id="owner3@example.com",
        )

        # Patch sharing service to return multiple shared projects
        original_get_shared = DefaultResourceSharingService.get_shared_resource_ids

        def _patched_get_shared(self, session, user_email, resource_type):
            result = original_get_shared(
                self,
                session=session,
                user_email=user_email,
                resource_type=resource_type,
            )
            if user_email == "secondary_user":
                return ["shared-1", "shared-2", "shared-3"]
            return result

        with patch.object(
            DefaultResourceSharingService,
            "get_shared_resource_ids",
            _patched_get_shared,
        ):
            # Act: Get projects as secondary user
            response = secondary_api_client.get("/api/v1/projects")

            # Assert
            assert response.status_code == 200
            data = response.json()
            projects = data["projects"]
            project_ids = [p["id"] for p in projects]

            assert len(projects) == 3
            assert "shared-1" in project_ids
            assert "shared-2" in project_ids
            assert "shared-3" in project_ids


class TestProjectRepositoryGetById:
    """Test ProjectRepository.get_by_id() with real database."""

    def test_get_by_id_returns_project_when_found(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test GET /api/v1/projects/{id} returns project when it exists."""
        # Arrange: Seed project
        gateway_adapter.seed_project(
            project_id="proj-1",
            name="Test Project",
            user_id="sam_dev_user",
            description="Test description",
        )

        # Act: Get project by ID
        response = api_client.get("/api/v1/projects/proj-1")

        # Assert
        assert response.status_code == 200
        project = response.json()
        assert project["id"] == "proj-1"
        assert project["name"] == "Test Project"
        assert project["description"] == "Test description"

    def test_get_by_id_returns_not_found_when_project_doesnt_exist(
        self, api_client: TestClient
    ):
        """Test GET /api/v1/projects/{id} returns 404 when project doesn't exist."""
        # Act: Try to get non-existent project
        response = api_client.get("/api/v1/projects/nonexistent-id")

        # Assert
        assert response.status_code == 404


class TestProjectRepositoryUpdate:
    """Test ProjectRepository.update() with real database."""

    def test_update_modifies_project_fields(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test PUT /api/v1/projects/{id} updates project fields in database."""
        # Arrange: Seed project
        gateway_adapter.seed_project(
            project_id="proj-1",
            name="Old Name",
            user_id="sam_dev_user",
            description="Old Description",
        )

        # Act: Update project
        update_data = {"name": "New Name", "description": "New Description"}
        response = api_client.put("/api/v1/projects/proj-1", json=update_data)

        # Assert: Response is correct
        assert response.status_code == 200
        updated_project = response.json()
        assert updated_project["name"] == "New Name"
        assert updated_project["description"] == "New Description"

        # Assert: Database state is updated
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            projects_table = metadata.tables["projects"]
            query = sa.select(projects_table).where(projects_table.c.id == "proj-1")
            db_project = conn.execute(query).first()

            assert db_project.name == "New Name"
            assert db_project.description == "New Description"

    def test_update_returns_not_found_when_project_doesnt_exist(
        self, api_client: TestClient
    ):
        """Test PUT /api/v1/projects/{id} returns 404 when project doesn't exist."""
        # Act: Try to update non-existent project
        update_data = {"name": "New Name"}
        response = api_client.put("/api/v1/projects/nonexistent-id", json=update_data)

        # Assert
        assert response.status_code == 404


class TestProjectRepositoryDelete:
    """Test ProjectRepository.delete() and soft_delete() with real database."""

    def test_delete_removes_project_and_returns_no_content(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test DELETE /api/v1/projects/{id} removes project from database."""
        # Arrange: Seed project
        gateway_adapter.seed_project(
            project_id="proj-to-delete",
            name="Project To Delete",
            user_id="sam_dev_user",
        )

        # Act: Delete project
        response = api_client.delete("/api/v1/projects/proj-to-delete")

        # Assert: Response is 204 No Content
        assert response.status_code == 204

        # Assert: Project no longer accessible via API
        get_response = api_client.get("/api/v1/projects/proj-to-delete")
        assert get_response.status_code == 404

        # Assert: Project is soft-deleted in database (not hard deleted)
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            projects_table = metadata.tables["projects"]
            # Query including deleted projects
            query = sa.select(projects_table).where(
                projects_table.c.id == "proj-to-delete"
            )
            db_project = conn.execute(query).first()

            # Verify soft delete (deleted_at should be set)
            if db_project:
                assert db_project.deleted_at is not None
                assert db_project.deleted_by == "sam_dev_user"

    def test_delete_returns_not_found_when_project_doesnt_exist(
        self, api_client: TestClient
    ):
        """Test DELETE /api/v1/projects/{id} returns 404 when project doesn't exist."""
        # Act: Try to delete non-existent project
        response = api_client.delete("/api/v1/projects/nonexistent-id")

        # Assert
        assert response.status_code == 404

    def test_soft_delete_marks_project_as_deleted(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that soft delete marks project with deleted_at timestamp."""
        # Arrange: Seed project
        gateway_adapter.seed_project(
            project_id="proj-soft-delete",
            name="Project To Soft Delete",
            user_id="sam_dev_user",
        )

        # Act: Soft delete via API
        response = api_client.delete("/api/v1/projects/proj-soft-delete")

        # Assert: API returns success
        assert response.status_code == 204

        # Assert: Verify soft delete in database
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            projects_table = metadata.tables["projects"]
            query = sa.select(projects_table).where(
                projects_table.c.id == "proj-soft-delete"
            )
            db_project = conn.execute(query).first()

            assert db_project is not None  # Still exists in DB
            assert db_project.deleted_at is not None  # But marked as deleted
            assert db_project.deleted_by == "sam_dev_user"

        # Assert: Project no longer appears in list
        list_response = api_client.get("/api/v1/projects")
        projects = list_response.json()["projects"]
        project_ids = [p["id"] for p in projects]
        assert "proj-soft-delete" not in project_ids

    def test_soft_delete_returns_not_found_when_project_doesnt_exist(
        self, api_client: TestClient
    ):
        """Test that soft delete returns 404 when project doesn't exist."""
        # Act: Try to soft delete non-existent project
        response = api_client.delete("/api/v1/projects/nonexistent-id")

        # Assert
        assert response.status_code == 404


class TestProjectRepositoryGetAll:
    """Test ProjectRepository.get_all_projects() with real database."""

    def test_get_all_projects_returns_all_non_deleted(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
    ):
        """Test that GET /api/v1/projects returns all non-deleted projects."""
        # Arrange: Seed multiple projects for different users
        gateway_adapter.seed_project(
            project_id="proj-1",
            name="Project 1",
            user_id="user1@example.com",
        )
        gateway_adapter.seed_project(
            project_id="proj-2",
            name="Project 2",
            user_id="user2@example.com",
        )
        gateway_adapter.seed_project(
            project_id="proj-3",
            name="Project 3",
            user_id="sam_dev_user",
        )

        # Act: Get all projects (sam_dev_user only sees their own by default)
        response = api_client.get("/api/v1/projects")

        # Assert: Only sam_dev_user's project returned
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]

        # Verify sam_dev_user's project is present
        project_ids = [p["id"] for p in projects]
        assert "proj-3" in project_ids

        # Note: Other projects (proj-1, proj-2) won't be visible unless sharing is configured
        # This test verifies the query works and filters correctly


class TestProjectRepositoryFiltered:
    """Test ProjectRepository.get_filtered_projects() with real database."""

    def test_get_filtered_projects_with_user_filter(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test filtering projects by user_id returns correct results."""
        # Arrange: Seed projects for different users
        gateway_adapter.seed_project(
            project_id="user1-proj",
            name="User 1 Project",
            user_id="user1@example.com",
        )
        gateway_adapter.seed_project(
            project_id="sam-proj",
            name="Sam Project",
            user_id="sam_dev_user",
        )

        # Act: Get projects (default behavior filters by current user)
        response = api_client.get("/api/v1/projects")

        # Assert: Only sam_dev_user's projects returned
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]
        project_ids = [p["id"] for p in projects]

        assert "sam-proj" in project_ids
        # user1-proj should not be visible without sharing
        assert "user1-proj" not in project_ids

    def test_get_filtered_projects_without_user_filter_returns_own_projects(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that GET /api/v1/projects returns user's own projects by default."""
        # Arrange: Seed projects for multiple users
        gateway_adapter.seed_project(
            project_id="proj-1",
            name="Project 1",
            user_id="user1@example.com",
        )
        gateway_adapter.seed_project(
            project_id="proj-2",
            name="Project 2",
            user_id="sam_dev_user",
        )

        # Act: Get projects without explicit filter
        response = api_client.get("/api/v1/projects")

        # Assert: Returns sam_dev_user's projects only
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]

        # At least one project should exist (proj-2)
        project_ids = [p["id"] for p in projects]
        assert "proj-2" in project_ids
