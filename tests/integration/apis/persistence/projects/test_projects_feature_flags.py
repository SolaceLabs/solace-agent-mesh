"""
Projects Feature Flags API Tests

Tests the feature flag system for the Projects feature, including:
1. Persistence-dependent behavior (auto-disable when persistence disabled)
2. Explicit configuration control (projects.enabled)
3. Feature flag override (frontend_feature_enablement.projects)
4. API endpoint protection (501 Not Implemented when disabled)
5. Config endpoint exposure of feature flag status
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestProjectsFeatureFlagConfig:
    """Tests for the /api/v1/config endpoint's projects feature flag exposure"""

    def test_config_exposes_projects_enabled_with_sql_persistence(
        self, api_client: TestClient
    ):
        """Test that config endpoint exposes projectsEnabled=true when SQL persistence is enabled"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200

        config_data = response.json()
        assert "frontend_feature_enablement" in config_data
        assert "projects" in config_data["frontend_feature_enablement"]

        # With SQL persistence (default in test setup), projects should be enabled
        assert config_data["frontend_feature_enablement"]["projects"] is True

    def test_config_persistence_enabled_flag(self, api_client: TestClient):
        """Test that config endpoint exposes persistence_enabled flag"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200

        config_data = response.json()
        assert "persistence_enabled" in config_data

        # Test setup uses SQL persistence
        assert config_data["persistence_enabled"] is True


class TestProjectsAPIEndpointProtection:
    """Tests for API endpoint protection when projects feature is disabled"""

    def test_create_project_returns_501_when_explicitly_disabled(
        self, projects_disabled_client: TestClient
    ):
        """Test POST /projects returns 501 when projects.enabled=false"""
        response = projects_disabled_client.post("/api/v1/projects", data={
            "name": "Test Project",
            "description": "Test Description"
        })

        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        assert "disabled" in detail or "not implemented" in detail

    def test_list_projects_returns_501_when_feature_flag_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test GET /projects returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.get("/api/v1/projects")
        assert response.status_code == 501

    def test_get_project_returns_501_when_disabled(
        self, projects_disabled_client: TestClient
    ):
        """Test GET /projects/{id} returns 501 when projects feature is disabled"""
        response = projects_disabled_client.get("/api/v1/projects/test-id")
        assert response.status_code == 501

    def test_update_project_returns_501_when_disabled(
        self, projects_disabled_client: TestClient
    ):
        """Test PUT /projects/{id} returns 501 when projects feature is disabled"""
        response = projects_disabled_client.put("/api/v1/projects/test-id", json={
            "name": "Updated",
            "description": "Updated"
        })
        assert response.status_code == 501

    def test_delete_project_returns_501_when_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test DELETE /projects/{id} returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.delete("/api/v1/projects/test-id")
        assert response.status_code == 501

    def test_get_project_artifacts_returns_501_when_disabled(
        self, projects_disabled_client: TestClient
    ):
        """Test GET /projects/{id}/artifacts returns 501 when projects feature is disabled"""
        response = projects_disabled_client.get("/api/v1/projects/test-id/artifacts")
        assert response.status_code == 501

    def test_add_project_artifacts_returns_501_when_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test POST /projects/{id}/artifacts returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.post("/api/v1/projects/test-id/artifacts", files={})
        assert response.status_code == 501

    def test_delete_project_artifact_returns_501_when_disabled(
        self, projects_disabled_client: TestClient
    ):
        """Test DELETE /projects/{id}/artifacts/{filename} returns 501 when projects feature is disabled"""
        response = projects_disabled_client.delete("/api/v1/projects/test-id/artifacts/test.txt")
        assert response.status_code == 501


class TestProjectsEnabledBehavior:
    """Tests for normal project operations when feature is enabled"""

    def test_create_project_succeeds_when_enabled(
        self, api_client: TestClient
    ):
        """Test that project creation works normally when feature is enabled"""
        response = api_client.post(
            "/api/v1/projects",
            data={"name": "Test Project", "description": "Test Description"},
        )

        assert response.status_code == 201
        project_data = response.json()

        assert "id" in project_data
        assert project_data["name"] == "Test Project"
        assert project_data["description"] == "Test Description"

    def test_list_projects_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that listing projects works normally when feature is enabled"""
        # Create a project first using gateway adapter
        gateway_adapter.seed_project(
            project_id="list-test-project",
            name="Test Project",
            user_id="sam_dev_user",
            description="Test Description"
        )

        response = api_client.get("/api/v1/projects")
        assert response.status_code == 200

        projects_data = response.json()
        assert "projects" in projects_data
        assert len(projects_data["projects"]) >= 1

    def test_get_project_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that getting a project works normally when feature is enabled"""
        # Create a project using gateway adapter
        project_id = "get-test-project"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="sam_dev_user",
            description="Test Description"
        )

        response = api_client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200

        project_data = response.json()
        assert project_data["id"] == project_id
        assert project_data["name"] == "Test Project"

    def test_update_project_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that updating a project works normally when feature is enabled"""
        # Create a project using gateway adapter
        project_id = "update-test-project"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original Description"
        )

        response = api_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Project", "description": "Updated Description"},
        )
        assert response.status_code == 200

        project_data = response.json()
        assert project_data["name"] == "Updated Project"
        assert project_data["description"] == "Updated Description"

    def test_delete_project_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that deleting a project works normally when feature is enabled"""
        # Create a project using gateway adapter
        project_id = "delete-test-project"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Project To Delete",
            user_id="sam_dev_user",
            description="Test Description"
        )

        response = api_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

        # Verify project is deleted
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404


class TestProjectsFeatureFlagPriority:
    """Tests for feature flag priority resolution logic"""

    def test_explicit_config_disables_projects(
        self, projects_disabled_client: TestClient
    ):
        """Test that projects.enabled=false disables projects"""
        # Config should show disabled
        response = projects_disabled_client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json()["frontend_feature_enablement"]["projects"] is False

        # API should return 501
        response = projects_disabled_client.post("/api/v1/projects", data={
            "name": "Test",
            "description": "Test"
        })
        assert response.status_code == 501

    def test_feature_flag_disables_projects(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test that feature flag can disable projects"""
        # Config should show disabled
        response = feature_flag_disabled_client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json()["frontend_feature_enablement"]["projects"] is False

        # API should return 501
        response = feature_flag_disabled_client.post("/api/v1/projects", data={
            "name": "Test",
            "description": "Test"
        })
        assert response.status_code == 501

    def test_both_enabled_allows_projects(
        self, both_enabled_client: TestClient
    ):
        """Test that projects work when both config and feature flag are enabled"""
        # Config should show enabled
        response = both_enabled_client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json()["frontend_feature_enablement"]["projects"] is True

        # API should work
        response = both_enabled_client.post("/api/v1/projects", data={
            "name": "Test",
            "description": "Test"
        })
        assert response.status_code == 201


class TestProjectsErrorMessages:
    """Tests for error messages when feature is disabled"""

    def test_501_error_mentions_explicit_disable(
        self, projects_disabled_client: TestClient
    ):
        """Test that 501 error mentions explicit disable when applicable"""
        response = projects_disabled_client.post("/api/v1/projects", data={
            "name": "Test",
            "description": "Test"
        })

        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        # Error should mention that it's disabled
        assert "disabled" in detail or "not implemented" in detail

    def test_501_error_mentions_feature_flag(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test that 501 error mentions feature flag when applicable"""
        response = feature_flag_disabled_client.post("/api/v1/projects", data={
            "name": "Test",
            "description": "Test"
        })

        assert response.status_code == 501
        detail = response.json()["detail"]
        # Error should be descriptive
        assert len(detail) > 20  # Should have a meaningful message

    def test_501_error_is_consistent_across_endpoints(
        self, projects_disabled_client: TestClient
    ):
        """Test that all endpoints return consistent 501 errors"""
        # Test multiple endpoints
        endpoints_to_test = [
            ("POST", "/api/v1/projects", {"data": {"name": "Test", "description": "Test"}}),
            ("GET", "/api/v1/projects", {}),
            ("GET", "/api/v1/projects/test-id", {}),
        ]

        for method, url, kwargs in endpoints_to_test:
            if method == "POST":
                response = projects_disabled_client.post(url, **kwargs)
            else:
                response = projects_disabled_client.get(url, **kwargs)

            assert response.status_code == 501, f"{method} {url} should return 501"


class TestProjectsFeatureFlagIntegration:
    """Integration tests for projects feature flag system"""

    def test_end_to_end_project_workflow_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test complete project workflow when feature is enabled"""
        # 1. Check config shows projects enabled
        config_response = api_client.get("/api/v1/config")
        assert config_response.json()["frontend_feature_enablement"]["projects"] is True

        # 2. Create project
        create_response = api_client.post(
            "/api/v1/projects",
            data={"name": "Integration Test Project", "description": "Test Description"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # 3. List projects
        list_response = api_client.get("/api/v1/projects")
        assert list_response.status_code == 200
        assert len(list_response.json()["projects"]) >= 1

        # 4. Get project
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200

        # 5. Update project
        update_response = api_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Name", "description": "Updated Description"},
        )
        assert update_response.status_code == 200

        # 6. Delete project
        delete_response = api_client.delete(f"/api/v1/projects/{project_id}")
        assert delete_response.status_code == 204

    def test_config_consistency_across_requests(self, api_client: TestClient):
        """Test that config endpoint returns consistent feature flag status"""
        # Make multiple requests to config endpoint
        responses = [api_client.get("/api/v1/config") for _ in range(5)]

        # All should return same feature flag status
        feature_flags = [r.json()["frontend_feature_enablement"]["projects"] for r in responses]
        assert all(flag == feature_flags[0] for flag in feature_flags)
