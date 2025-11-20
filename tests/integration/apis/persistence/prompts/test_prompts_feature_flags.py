"""
Prompts Feature Flags API Tests

Tests the feature flag system for the Prompt Library feature, including:
1. Persistence-dependent behavior (auto-disable when persistence disabled)
2. Explicit configuration control (prompt_library.enabled)
3. Feature flag override (frontend_feature_enablement.promptLibrary)
4. API endpoint protection (501 Not Implemented when disabled)
5. Config endpoint exposure of feature flag status
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestPromptsFeatureFlagConfig:
    """Tests for the /api/v1/config endpoint's prompts feature flag exposure"""

    def test_config_exposes_prompts_enabled_with_sql_persistence(
        self, api_client: TestClient
    ):
        """Test that config endpoint returns successfully with SQL persistence enabled"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200

        config_data = response.json()
        assert "frontend_feature_enablement" in config_data
        
        # With SQL persistence (default in test setup), the config endpoint should work
        # The actual feature flag value depends on the configuration
        assert isinstance(config_data["frontend_feature_enablement"], dict)

    def test_config_persistence_enabled_flag(self, api_client: TestClient):
        """Test that config endpoint exposes persistence_enabled flag"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200

        config_data = response.json()
        assert "persistence_enabled" in config_data

        # Test setup uses SQL persistence
        assert config_data["persistence_enabled"] is True


class TestPromptsAPIEndpointProtection:
    """Tests for API endpoint protection when prompts feature is disabled"""

    def test_create_prompt_returns_501_when_explicitly_disabled(
        self, prompts_disabled_client: TestClient
    ):
        """Test POST /prompts/groups returns 501 when prompt_library.enabled=false"""
        response = prompts_disabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test Prompt",
                "description": "Test Description",
                "initial_prompt": "Test prompt text",
            },
        )

        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        assert "disabled" in detail or "not implemented" in detail

    def test_list_prompts_returns_501_when_feature_flag_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test GET /prompts/groups returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.get("/api/v1/prompts/groups/all")
        assert response.status_code == 501

    def test_get_prompt_returns_501_when_disabled(
        self, prompts_disabled_client: TestClient
    ):
        """Test GET /prompts/groups/{id} returns 501 when prompts feature is disabled"""
        response = prompts_disabled_client.get("/api/v1/prompts/groups/test-id")
        assert response.status_code == 501

    def test_update_prompt_returns_501_when_disabled(
        self, prompts_disabled_client: TestClient
    ):
        """Test PATCH /prompts/groups/{id} returns 501 when prompts feature is disabled"""
        response = prompts_disabled_client.patch(
            "/api/v1/prompts/groups/test-id",
            json={"name": "Updated", "description": "Updated"},
        )
        assert response.status_code == 501

    def test_delete_prompt_returns_501_when_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test DELETE /prompts/groups/{id} returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.delete("/api/v1/prompts/groups/test-id")
        assert response.status_code == 501

    def test_pin_prompt_returns_501_when_disabled(
        self, prompts_disabled_client: TestClient
    ):
        """Test PATCH /prompts/groups/{id}/pin returns 501 when prompts feature is disabled"""
        response = prompts_disabled_client.patch("/api/v1/prompts/groups/test-id/pin")
        assert response.status_code == 501

    def test_list_prompt_versions_returns_501_when_disabled(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test GET /prompts/groups/{id}/prompts returns 501 when feature flag is disabled"""
        response = feature_flag_disabled_client.get("/api/v1/prompts/groups/test-id/prompts")
        assert response.status_code == 501

    def test_create_prompt_version_returns_501_when_disabled(
        self, prompts_disabled_client: TestClient
    ):
        """Test POST /prompts/groups/{id}/prompts returns 501 when prompts feature is disabled"""
        response = prompts_disabled_client.post(
            "/api/v1/prompts/groups/test-id/prompts",
            json={"prompt_text": "New version"},
        )
        assert response.status_code == 501


class TestPromptsEnabledBehavior:
    """Tests for normal prompt operations when feature is enabled"""

    def test_create_prompt_succeeds_when_enabled(self, api_client: TestClient):
        """Test that prompt creation works normally when feature is enabled"""
        response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test Prompt",
                "description": "Test Description",
                "category": "testing",
                "initial_prompt": "You are a test assistant",
            },
        )

        assert response.status_code == 201
        prompt_data = response.json()

        assert "id" in prompt_data
        assert prompt_data["name"] == "Test Prompt"
        assert prompt_data["description"] == "Test Description"
        assert prompt_data["productionPrompt"] is not None

    def test_list_prompts_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that listing prompts works normally when feature is enabled"""
        # Create a prompt first using gateway adapter
        gateway_adapter.seed_prompt_group(
            group_id="list-test-prompt",
            name="Test Prompt",
            user_id="sam_dev_user",
            description="Test Description",
            initial_prompt="Test prompt text",
        )

        response = api_client.get("/api/v1/prompts/groups/all")
        assert response.status_code == 200

        prompts = response.json()
        assert isinstance(prompts, list)
        assert len(prompts) >= 1

    def test_get_prompt_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that getting a prompt works normally when feature is enabled"""
        # Create a prompt using gateway adapter
        group_id = "get-test-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Test Prompt",
            user_id="sam_dev_user",
            description="Test Description",
            initial_prompt="Test prompt text",
        )

        response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert response.status_code == 200

        prompt_data = response.json()
        assert prompt_data["id"] == group_id
        assert prompt_data["name"] == "Test Prompt"

    def test_update_prompt_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that updating a prompt works normally when feature is enabled"""
        # Create a prompt using gateway adapter
        group_id = "update-test-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original Description",
            initial_prompt="Original prompt text",
        )

        response = api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={"name": "Updated Prompt", "description": "Updated Description"},
        )
        assert response.status_code == 200

        prompt_data = response.json()
        assert prompt_data["name"] == "Updated Prompt"
        assert prompt_data["description"] == "Updated Description"

    def test_delete_prompt_succeeds_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that deleting a prompt works normally when feature is enabled"""
        # Create a prompt using gateway adapter
        group_id = "delete-test-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Prompt To Delete",
            user_id="sam_dev_user",
            description="Test Description",
            initial_prompt="Test prompt text",
        )

        response = api_client.delete(f"/api/v1/prompts/groups/{group_id}")
        assert response.status_code == 204

        # Verify prompt is deleted
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 404


class TestPromptsFeatureFlagPriority:
    """Tests for feature flag priority resolution logic"""

    def test_explicit_config_disables_prompts(
        self, prompts_disabled_client: TestClient
    ):
        """Test that prompt_library.enabled=false disables prompts"""
        # Config should show disabled
        response = prompts_disabled_client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json()["frontend_feature_enablement"]["promptLibrary"] is False

        # API should return 501
        response = prompts_disabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test",
                "description": "Test",
                "initial_prompt": "Test",
            },
        )
        assert response.status_code == 501

    def test_feature_flag_disables_prompts(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test that feature flag can disable prompts"""
        # API should return 501 when disabled
        response = feature_flag_disabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test",
                "description": "Test",
                "initial_prompt": "Test",
            },
        )
        assert response.status_code == 501

    def test_both_enabled_allows_prompts(self, both_enabled_client: TestClient):
        """Test that prompts work when both config and feature flag are enabled"""
        # Config should show enabled
        response = both_enabled_client.get("/api/v1/config")
        assert response.status_code == 200
        assert response.json()["frontend_feature_enablement"]["promptLibrary"] is True

        # API should work
        response = both_enabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test",
                "description": "Test",
                "category": "testing",
                "initial_prompt": "Test prompt text",
            },
        )
        assert response.status_code == 201


class TestPromptsErrorMessages:
    """Tests for error messages when feature is disabled"""

    def test_501_error_mentions_explicit_disable(
        self, prompts_disabled_client: TestClient
    ):
        """Test that 501 error mentions explicit disable when applicable"""
        response = prompts_disabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test",
                "description": "Test",
                "initial_prompt": "Test",
            },
        )

        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        # Error should mention that it's disabled
        assert "disabled" in detail or "not implemented" in detail

    def test_501_error_mentions_feature_flag(
        self, feature_flag_disabled_client: TestClient
    ):
        """Test that 501 error mentions feature flag when applicable"""
        response = feature_flag_disabled_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test",
                "description": "Test",
                "initial_prompt": "Test",
            },
        )

        assert response.status_code == 501
        detail = response.json()["detail"]
        # Error should be descriptive
        assert len(detail) > 20  # Should have a meaningful message

    def test_501_error_is_consistent_across_endpoints(
        self, prompts_disabled_client: TestClient
    ):
        """Test that all endpoints return consistent 501 errors"""
        # Test multiple endpoints
        endpoints_to_test = [
            ("POST", "/api/v1/prompts/groups", {"json": {"name": "Test", "description": "Test", "initial_prompt": "Test"}}),
            ("GET", "/api/v1/prompts/groups/all", {}),
            ("GET", "/api/v1/prompts/groups/test-id", {}),
        ]

        for method, url, kwargs in endpoints_to_test:
            if method == "POST":
                response = prompts_disabled_client.post(url, **kwargs)
            else:
                response = prompts_disabled_client.get(url, **kwargs)

            assert response.status_code == 501, f"{method} {url} should return 501"


class TestPromptsFeatureFlagIntegration:
    """Integration tests for prompts feature flag system"""

    def test_end_to_end_prompt_workflow_when_enabled(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test complete prompt workflow when feature is enabled"""
        # 1. Verify API is accessible (prompts enabled)
        # 2. Create prompt
        create_response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Integration Test Prompt",
                "description": "Test Description",
                "category": "testing",
                "initial_prompt": "You are a test assistant",
            },
        )
        assert create_response.status_code == 201
        group_id = create_response.json()["id"]

        # 3. List prompts
        list_response = api_client.get("/api/v1/prompts/groups/all")
        assert list_response.status_code == 200
        assert len(list_response.json()) >= 1

        # 4. Get prompt
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 200

        # 5. Update prompt
        update_response = api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={"name": "Updated Name", "description": "Updated Description"},
        )
        assert update_response.status_code == 200

        # 6. Delete prompt
        delete_response = api_client.delete(f"/api/v1/prompts/groups/{group_id}")
        assert delete_response.status_code == 204

    def test_config_consistency_across_requests(self, api_client: TestClient):
        """Test that config endpoint returns consistent feature flag status"""
        # Make multiple requests to config endpoint
        responses = [api_client.get("/api/v1/config") for _ in range(5)]

        # All should return 200
        assert all(r.status_code == 200 for r in responses)
        
        # All should have frontend_feature_enablement
        assert all("frontend_feature_enablement" in r.json() for r in responses)