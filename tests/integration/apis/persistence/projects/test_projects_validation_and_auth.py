"""
Projects Validation and Authorization API Tests

Tests for:
- Input validation (missing required fields, invalid data)
- Authorization (cross-user access prevention)
- Not found scenarios
- Empty list responses
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestProjectsValidation:
    """Tests for project input validation"""

    def test_create_project_missing_required_name_field(
        self, api_client: TestClient
    ):
        """Test that creating project without name returns 422 validation error"""
        # Attempt to create project without name (using JSON body)
        response = api_client.post(
            "/api/v1/projects",
            json={"description": "Project without name"}
        )

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_create_project_with_form_data_missing_name(
        self, api_client: TestClient
    ):
        """Test that creating project via form data without name returns 422"""
        # Attempt to create project without name (using form data)
        response = api_client.post(
            "/api/v1/projects",
            data={"description": "Project without name"}
        )

        # Should return 422 for validation error
        assert response.status_code == 422


class TestProjectsNotFound:
    """Tests for 404 not found scenarios"""

    def test_get_nonexistent_project_returns_404(
        self, api_client: TestClient
    ):
        """Test GET /api/v1/projects/{id} returns 404 for non-existent project"""
        response = api_client.get("/api/v1/projects/non-existent-id-12345")

        assert response.status_code == 404

    def test_update_nonexistent_project_returns_404(
        self, api_client: TestClient
    ):
        """Test PUT /api/v1/projects/{id} returns 404 for non-existent project"""
        response = api_client.put(
            "/api/v1/projects/non-existent-id-12345",
            json={"name": "Updated Name", "description": "Updated Description"}
        )

        assert response.status_code == 404

    def test_delete_nonexistent_project_returns_404(
        self, api_client: TestClient
    ):
        """Test DELETE /api/v1/projects/{id} returns 404 for non-existent project"""
        response = api_client.delete("/api/v1/projects/non-existent-id-12345")

        assert response.status_code == 404


class TestProjectsEmptyList:
    """Tests for empty project list responses"""

    def test_get_projects_returns_proper_structure_when_empty(
        self, api_client: TestClient
    ):
        """Test GET /api/v1/projects returns correct structure even with no projects"""
        response = api_client.get("/api/v1/projects")

        assert response.status_code == 200

        # Verify response structure
        data = response.json()
        assert "projects" in data
        assert "total" in data
        assert isinstance(data["projects"], list)
        assert isinstance(data["total"], int)


class TestProjectsAuthorization:
    """Tests for cross-user authorization and access control"""

    def test_user_cannot_access_another_users_project(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot access other users' projects"""
        # Setup: Create a project for user1
        project_id = "user1-private-project-001"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="User 1 Private Project",
            user_id="sam_dev_user",  # Primary user
            description="Private project for user1",
            system_prompt="Test prompt",
        )

        # Act: Try to access as secondary user
        response = secondary_api_client.get(f"/api/v1/projects/{project_id}")

        # Assert: Should get 404 (project not found for this user)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_user_cannot_update_another_users_project(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot update other users' projects"""
        # Setup: Create a project for user1
        project_id = "user1-project-update-001"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="User 1 Project",
            user_id="sam_dev_user",  # Primary user
            description="Private project for user1",
            system_prompt="Original prompt",
        )

        # Act: Try to update as secondary user
        response = secondary_api_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Hacked Name", "description": "Hacked Description"},
        )

        # Assert: Should get 404 (project not found for this user)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Verify project was NOT updated
        original_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert original_response.status_code == 200
        original_data = original_response.json()
        assert original_data["name"] == "User 1 Project"
        assert original_data["description"] == "Private project for user1"

    def test_user_cannot_delete_another_users_project(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot delete other users' projects"""
        # Setup: Create a project for user1
        project_id = "user1-project-delete-001"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="User 1 Project",
            user_id="sam_dev_user",  # Primary user
            description="Private project for user1",
            system_prompt="Test prompt",
        )

        # Act: Try to delete as secondary user
        response = secondary_api_client.delete(f"/api/v1/projects/{project_id}")

        # Assert: Should get 404 (project not found for this user)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Verify project still exists for original user
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == project_id

    def test_user_can_only_see_their_own_projects_in_list(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that listing projects only shows the user's own projects"""
        # Setup: Create projects for both users
        gateway_adapter.seed_project(
            project_id="user1-project-001",
            name="User 1 Project",
            user_id="sam_dev_user",
            description="User 1's project",
        )
        gateway_adapter.seed_project(
            project_id="user2-project-001",
            name="User 2 Project",
            user_id="secondary_user",
            description="User 2's project",
        )

        # Act: List projects for user1
        user1_response = api_client.get("/api/v1/projects")
        assert user1_response.status_code == 200
        user1_data = user1_response.json()
        user1_project_ids = [p["id"] for p in user1_data["projects"]]

        # Act: List projects for user2
        user2_response = secondary_api_client.get("/api/v1/projects")
        assert user2_response.status_code == 200
        user2_data = user2_response.json()
        user2_project_ids = [p["id"] for p in user2_data["projects"]]

        # Assert: User1 should only see their project
        assert "user1-project-001" in user1_project_ids
        assert "user2-project-001" not in user1_project_ids

        # Assert: User2 should only see their project
        assert "user2-project-001" in user2_project_ids
        assert "user1-project-001" not in user2_project_ids
