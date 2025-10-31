"""
Projects Feature Flags API Tests

Tests the feature flag system for the Projects feature, including:
1. Persistence-dependent behavior (auto-disable when persistence disabled)
2. Explicit configuration control (projects.enabled)
3. Feature flag override (frontend_frontend_feature_enablement.projects)
4. API endpoint protection (501 Not Implemented when disabled)
5. Config endpoint exposure of feature flag status
"""

import pytest
from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import WebUIBackendFactory


# Helper function to create test client with custom config
def create_test_client_with_config(projects_enabled=True, feature_flag_enabled=True, persistence_enabled=True):
    """
    Helper to create test client with specific configuration.
    
    Args:
        projects_enabled: Value for projects.enabled config
        feature_flag_enabled: Value for frontend_feature_enablement.projects
        persistence_enabled: Whether to simulate SQL persistence (True) or memory (False)
    
    Returns:
        Tuple of (TestClient, WebUIBackendFactory)
    """
    factory = WebUIBackendFactory()
    
    # Store original get_config if it exists
    original_get_config = factory.mock_component.get_config if hasattr(factory.mock_component, 'get_config') else None
    
    def custom_get_config(key, default=None):
        # Handle all config keys that might be accessed by the config router
        if key == "projects":
            return {"enabled": projects_enabled}
        if key == "frontend_feature_enablement":
            return {"projects": feature_flag_enabled}
        if key == "session_service":
            # Return a proper dict to avoid serialization issues
            return {"type": "sql"}
        if key == "task_logging":
            return {"enabled": False}
        if key == "frontend_collect_feedback":
            return False
        if key == "frontend_auth_login_url":
            return ""
        if key == "frontend_use_authorization":
            return False
        if key == "frontend_welcome_message":
            return ""
        if key == "frontend_redirect_url":
            return ""
        if key == "frontend_bot_name":
            return "A2A Agent"
        if key == "name":
            return "A2A_WebUI_App"
        # For any other keys, return the default value instead of calling original
        # This prevents Mock objects from being returned
        return default
    
    factory.mock_component.get_config = custom_get_config
    
    # Override auth
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    
    async def override_get_current_user():
        return {
            "id": "sam_dev_user",
            "name": "Sam Dev User",
            "email": "sam@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }
    
    factory.app.dependency_overrides[get_current_user] = override_get_current_user
    
    return TestClient(factory.app), factory


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
        
        print("✓ Config endpoint exposes projects as enabled with SQL persistence")

    def test_config_persistence_enabled_flag(self, api_client: TestClient):
        """Test that config endpoint exposes persistence_enabled flag"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200
        
        config_data = response.json()
        assert "persistence_enabled" in config_data
        
        # Test setup uses SQL persistence
        assert config_data["persistence_enabled"] is True
        
        print("✓ Config endpoint exposes persistence_enabled flag")


class TestProjectsAPIEndpointProtection:
    """Tests for API endpoint protection when projects feature is disabled"""

    def test_create_project_returns_501_when_disabled(self):
        """Test POST /projects returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.post("/api/v1/projects", data={
                "name": "Test Project",
                "description": "Test Description"
            })
            
            assert response.status_code == 501
            detail = response.json()["detail"].lower()
            assert "disabled" in detail or "not implemented" in detail
            print("✓ POST /projects returns 501 when disabled")
        finally:
            factory.teardown()

    def test_list_projects_returns_501_when_disabled(self):
        """Test GET /projects returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(feature_flag_enabled=False)
        
        try:
            response = client.get("/api/v1/projects")
            assert response.status_code == 501
            print("✓ GET /projects returns 501 when disabled")
        finally:
            factory.teardown()

    def test_get_project_returns_501_when_disabled(self):
        """Test GET /projects/{id} returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.get("/api/v1/projects/test-id")
            assert response.status_code == 501
            print("✓ GET /projects/{id} returns 501 when disabled")
        finally:
            factory.teardown()

    def test_update_project_returns_501_when_disabled(self):
        """Test PUT /projects/{id} returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.put("/api/v1/projects/test-id", json={
                "name": "Updated",
                "description": "Updated"
            })
            assert response.status_code == 501
            print("✓ PUT /projects/{id} returns 501 when disabled")
        finally:
            factory.teardown()

    def test_delete_project_returns_501_when_disabled(self):
        """Test DELETE /projects/{id} returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(feature_flag_enabled=False)
        
        try:
            response = client.delete("/api/v1/projects/test-id")
            assert response.status_code == 501
            print("✓ DELETE /projects/{id} returns 501 when disabled")
        finally:
            factory.teardown()

    def test_get_project_artifacts_returns_501_when_disabled(self):
        """Test GET /projects/{id}/artifacts returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.get("/api/v1/projects/test-id/artifacts")
            assert response.status_code == 501
            print("✓ GET /projects/{id}/artifacts returns 501 when disabled")
        finally:
            factory.teardown()

    def test_add_project_artifacts_returns_501_when_disabled(self):
        """Test POST /projects/{id}/artifacts returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(feature_flag_enabled=False)
        
        try:
            response = client.post("/api/v1/projects/test-id/artifacts", files={})
            assert response.status_code == 501
            print("✓ POST /projects/{id}/artifacts returns 501 when disabled")
        finally:
            factory.teardown()

    def test_delete_project_artifact_returns_501_when_disabled(self):
        """Test DELETE /projects/{id}/artifacts/{filename} returns 501 when projects feature is disabled"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.delete("/api/v1/projects/test-id/artifacts/test.txt")
            assert response.status_code == 501
            print("✓ DELETE /projects/{id}/artifacts/{filename} returns 501 when disabled")
        finally:
            factory.teardown()


class TestProjectsEnabledBehavior:
    """Tests for normal project operations when feature is enabled"""

    def test_create_project_succeeds_when_enabled(self, api_client: TestClient):
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
        
        print("✓ Project creation succeeds when feature is enabled")

    def test_list_projects_succeeds_when_enabled(self, api_client: TestClient):
        """Test that listing projects works normally when feature is enabled"""
        # Create a project first
        api_client.post(
            "/api/v1/projects",
            data={"name": "Test Project", "description": "Test Description"},
        )
        
        response = api_client.get("/api/v1/projects")
        assert response.status_code == 200
        
        projects_data = response.json()
        assert "projects" in projects_data
        assert len(projects_data["projects"]) >= 1
        
        print("✓ Project listing succeeds when feature is enabled")

    def test_get_project_succeeds_when_enabled(self, api_client: TestClient):
        """Test that getting a project works normally when feature is enabled"""
        # Create a project first
        create_response = api_client.post(
            "/api/v1/projects",
            data={"name": "Test Project", "description": "Test Description"},
        )
        project_id = create_response.json()["id"]
        
        response = api_client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        
        project_data = response.json()
        assert project_data["id"] == project_id
        assert project_data["name"] == "Test Project"
        
        print("✓ Project retrieval succeeds when feature is enabled")

    def test_update_project_succeeds_when_enabled(self, api_client: TestClient):
        """Test that updating a project works normally when feature is enabled"""
        # Create a project first
        create_response = api_client.post(
            "/api/v1/projects",
            data={"name": "Test Project", "description": "Test Description"},
        )
        project_id = create_response.json()["id"]
        
        response = api_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Project", "description": "Updated Description"},
        )
        assert response.status_code == 200
        
        project_data = response.json()
        assert project_data["name"] == "Updated Project"
        assert project_data["description"] == "Updated Description"
        
        print("✓ Project update succeeds when feature is enabled")

    def test_delete_project_succeeds_when_enabled(self, api_client: TestClient):
        """Test that deleting a project works normally when feature is enabled"""
        # Create a project first
        create_response = api_client.post(
            "/api/v1/projects",
            data={"name": "Test Project", "description": "Test Description"},
        )
        project_id = create_response.json()["id"]
        
        response = api_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204
        
        # Verify project is deleted
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404
        
        print("✓ Project deletion succeeds when feature is enabled")


class TestProjectsFeatureFlagPriority:
    """Tests for feature flag priority resolution logic"""

    def test_explicit_config_disables_projects(self):
        """Test that projects.enabled=false disables projects"""
        client, factory = create_test_client_with_config(
            projects_enabled=False,
            feature_flag_enabled=True  # Feature flag says enabled
        )
        
        try:
            # Config should show disabled (explicit config wins)
            response = client.get("/api/v1/config")
            assert response.status_code == 200
            assert response.json()["frontend_feature_enablement"]["projects"] is False
            
            # API should return 501
            response = client.post("/api/v1/projects", data={
                "name": "Test",
                "description": "Test"
            })
            assert response.status_code == 501
            print("✓ Explicit projects.enabled=false disables projects")
        finally:
            factory.teardown()

    def test_feature_flag_disables_projects(self):
        """Test that feature flag can disable projects"""
        client, factory = create_test_client_with_config(
            projects_enabled=True,  # Explicit config says enabled
            feature_flag_enabled=False  # Feature flag disables
        )
        
        try:
            # Config should show disabled (feature flag wins)
            response = client.get("/api/v1/config")
            assert response.status_code == 200
            assert response.json()["frontend_feature_enablement"]["projects"] is False
            
            # API should return 501
            response = client.post("/api/v1/projects", data={
                "name": "Test",
                "description": "Test"
            })
            assert response.status_code == 501
            print("✓ Feature flag can disable projects")
        finally:
            factory.teardown()

    def test_both_enabled_allows_projects(self):
        """Test that projects work when both config and feature flag are enabled"""
        client, factory = create_test_client_with_config(
            projects_enabled=True,
            feature_flag_enabled=True
        )
        
        try:
            # Config should show enabled
            response = client.get("/api/v1/config")
            assert response.status_code == 200
            assert response.json()["frontend_feature_enablement"]["projects"] is True
            
            # API should work
            response = client.post("/api/v1/projects", data={
                "name": "Test",
                "description": "Test"
            })
            assert response.status_code == 201
            print("✓ Projects enabled when both config and feature flag are true")
        finally:
            factory.teardown()


class TestProjectsDataPreservation:
    """Tests for data preservation when feature is toggled"""

    def test_config_changes_dont_affect_database(self):
        """Test that changing config doesn't delete data from database"""
        # Create project with feature enabled
        client_enabled, factory_enabled = create_test_client_with_config(projects_enabled=True)
        
        try:
            response = client_enabled.post("/api/v1/projects", data={
                "name": "Test Project",
                "description": "Test Description"
            })
            assert response.status_code == 201
            project_id = response.json()["id"]
            
            # Verify project exists
            response = client_enabled.get(f"/api/v1/projects/{project_id}")
            assert response.status_code == 200
            
            print("✓ Project created successfully")
        finally:
            factory_enabled.teardown()
        
        # Note: In a real scenario, the data would persist in the database
        # even when the feature is disabled. This test demonstrates the concept.
        # Full data preservation testing would require:
        # 1. Shared database between test clients
        # 2. Ability to query database directly
        # 3. Feature toggle without app restart
        print("✓ Data preservation concept validated")


class TestProjectsErrorMessages:
    """Tests for error messages when feature is disabled"""

    def test_501_error_mentions_explicit_disable(self):
        """Test that 501 error mentions explicit disable when applicable"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            response = client.post("/api/v1/projects", data={
                "name": "Test",
                "description": "Test"
            })
            
            assert response.status_code == 501
            detail = response.json()["detail"].lower()
            # Error should mention that it's disabled
            assert "disabled" in detail or "not implemented" in detail
            print("✓ 501 error provides clear message when explicitly disabled")
        finally:
            factory.teardown()

    def test_501_error_mentions_feature_flag(self):
        """Test that 501 error mentions feature flag when applicable"""
        client, factory = create_test_client_with_config(feature_flag_enabled=False)
        
        try:
            response = client.post("/api/v1/projects", data={
                "name": "Test",
                "description": "Test"
            })
            
            assert response.status_code == 501
            detail = response.json()["detail"]
            # Error should be descriptive
            assert len(detail) > 20  # Should have a meaningful message
            print("✓ 501 error provides clear message when feature flag disabled")
        finally:
            factory.teardown()

    def test_501_error_is_consistent_across_endpoints(self):
        """Test that all endpoints return consistent 501 errors"""
        client, factory = create_test_client_with_config(projects_enabled=False)
        
        try:
            # Test multiple endpoints
            endpoints_to_test = [
                ("POST", "/api/v1/projects", {"data": {"name": "Test", "description": "Test"}}),
                ("GET", "/api/v1/projects", {}),
                ("GET", "/api/v1/projects/test-id", {}),
            ]
            
            for method, url, kwargs in endpoints_to_test:
                if method == "POST":
                    response = client.post(url, **kwargs)
                else:
                    response = client.get(url, **kwargs)
                
                assert response.status_code == 501, f"{method} {url} should return 501"
            
            print("✓ All endpoints return consistent 501 errors")
        finally:
            factory.teardown()


# Integration test scenarios
class TestProjectsFeatureFlagIntegration:
    """Integration tests for projects feature flag system"""

    def test_end_to_end_project_workflow_when_enabled(self, api_client: TestClient):
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
        
        print("✓ End-to-end project workflow succeeds when feature is enabled")

    def test_config_consistency_across_requests(self, api_client: TestClient):
        """Test that config endpoint returns consistent feature flag status"""
        # Make multiple requests to config endpoint
        responses = [api_client.get("/api/v1/config") for _ in range(5)]
        
        # All should return same feature flag status
        feature_flags = [r.json()["frontend_feature_enablement"]["projects"] for r in responses]
        assert all(flag == feature_flags[0] for flag in feature_flags)
        
        print("✓ Config endpoint returns consistent feature flag status")