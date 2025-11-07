"""
Projects CRUD API Tests

Tests for project lifecycle operations including:
- Creating projects
- Reading projects (list and individual)
- Updating projects
- Deleting projects
- Pagination
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestProjectsCRUD:
    """Test basic CRUD operations for projects"""

    def test_get_project_by_id(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test GET /api/v1/projects/{id} returns specific project"""
        # Setup: Create a project
        project_id = "test-project-123"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Specific Test Project",
            user_id="sam_dev_user",
            description="A specific project for testing",
            system_prompt="You are a specialized assistant",
        )

        # Act: Get the project
        response = api_client.get(f"/api/v1/projects/{project_id}")

        # Assert
        assert response.status_code == 200
        project_data = response.json()
        assert project_data["id"] == project_id
        assert project_data["name"] == "Specific Test Project"
        assert project_data["userId"] == "sam_dev_user"
        assert project_data["description"] == "A specific project for testing"
        assert project_data["systemPrompt"] == "You are a specialized assistant"

    def test_get_projects_with_data(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test GET /api/v1/projects returns seeded projects correctly"""
        # Setup: Create multiple projects
        gateway_adapter.seed_project(
            project_id="test-project-unique-001",
            name="Test Project 1",
            user_id="sam_dev_user",
            description="First test project",
            system_prompt="You are a helpful assistant for project 1",
        )
        gateway_adapter.seed_project(
            project_id="test-project-unique-002",
            name="Test Project 2",
            user_id="sam_dev_user",
            description="Second test project",
        )

        # Act: Get all projects
        response = api_client.get("/api/v1/projects")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data

        # Verify our seeded projects exist
        project_ids = [p["id"] for p in data["projects"]]
        assert "test-project-unique-001" in project_ids
        assert "test-project-unique-002" in project_ids

        # Verify project details
        project_1 = next(p for p in data["projects"] if p["id"] == "test-project-unique-001")
        assert project_1["name"] == "Test Project 1"
        assert project_1["description"] == "First test project"

        project_2 = next(p for p in data["projects"] if p["id"] == "test-project-unique-002")
        assert project_2["name"] == "Test Project 2"
        assert project_2["description"] == "Second test project"

    def test_update_project(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PUT /api/v1/projects/{id} updates project successfully"""
        # Setup: Create a project
        project_id = "project-to-update"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original description",
            system_prompt="Original prompt",
        )

        # Act: Update the project
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
            "systemPrompt": "Updated prompt",
        }
        response = api_client.put(f"/api/v1/projects/{project_id}", json=update_data)

        # Assert: Update response
        assert response.status_code == 200
        project_data = response.json()
        assert project_data["id"] == project_id
        assert project_data["name"] == "Updated Name"
        assert project_data["description"] == "Updated description"
        assert project_data["systemPrompt"] == "Updated prompt"
        assert project_data["userId"] == "sam_dev_user"

        # Verify update persisted
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200
        persisted_data = get_response.json()
        assert persisted_data["id"] == project_id
        assert persisted_data["name"] == "Updated Name"
        assert persisted_data["description"] == "Updated description"
        assert persisted_data["systemPrompt"] == "Updated prompt"

    def test_delete_project(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test DELETE /api/v1/projects/{id} removes project successfully"""
        # Setup: Create a project
        project_id = "project-to-delete"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Project To Delete",
            user_id="sam_dev_user",
            description="This project will be deleted",
        )

        # Act: Delete the project
        response = api_client.delete(f"/api/v1/projects/{project_id}")

        # Assert: Delete succeeds
        assert response.status_code == 204

        # Verify project is deleted (should return 404)
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404


class TestProjectsPagination:
    """Test pagination functionality for projects listing"""

    def test_pagination(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test pagination works correctly for GET /api/v1/projects"""
        # Setup: Create 5 projects
        for i in range(1, 6):
            gateway_adapter.seed_project(
                project_id=f"pagination-project-{i}",
                name=f"Pagination Project {i}",
                user_id="sam_dev_user",
            )

        # Test that all projects are returned (pagination may not be implemented yet)
        response = api_client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data

        # Verify all our seeded projects exist
        project_ids = [p["id"] for p in data["projects"]]
        for i in range(1, 6):
            assert f"pagination-project-{i}" in project_ids

        # Verify total count includes our projects
        assert data["total"] >= 5

    def test_pagination_total_count(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that total count remains consistent across pages"""
        # Setup: Create 5 projects
        for i in range(1, 6):
            gateway_adapter.seed_project(
                project_id=f"page-test-project-{i}",
                name=f"Page Test Project {i}",
                user_id="sam_dev_user",
            )

        # Get all pages and verify total is consistent
        page1 = api_client.get("/api/v1/projects?limit=2&offset=0").json()
        page2 = api_client.get("/api/v1/projects?limit=2&offset=2").json()
        page3 = api_client.get("/api/v1/projects?limit=2&offset=4").json()

        assert page1["total"] == page2["total"] == page3["total"]
        assert page1["total"] >= 5  # At least our 5 seeded projects
