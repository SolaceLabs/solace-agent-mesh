"""
Background Tasks Config API Tests

Tests the background_tasks configuration exposure via the /api/v1/config endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import WebUIBackendFactory


# Custom header for test user identification
TEST_USER_HEADER = "X-Test-User-Id"


def _create_background_tasks_config_client(
    db_url: str,
    background_tasks_enabled: bool = False,
    background_tasks_timeout_ms: int = 3600000
):
    """
    Helper to create a test client with custom background_tasks configuration.

    Args:
        db_url: Database URL to use
        background_tasks_enabled: Value for background_tasks.enabled config
        background_tasks_timeout_ms: Value for background_tasks.default_timeout_ms config

    Returns:
        TestClient configured with specified settings
    """
    factory = WebUIBackendFactory(db_url=db_url)

    def custom_get_config(key, default=None):
        # Override specific config keys
        if key == "background_tasks":
            return {
                "default_timeout_ms": background_tasks_timeout_ms
            }
        if key == "projects":
            return {"enabled": True}
        if key == "frontend_feature_enablement":
            return {"projects": True, "background_tasks": background_tasks_enabled}
        if key == "name":
            return "A2A_WebUI_App"
        if key == "session_service":
            return {"type": "sql"}
        if key == "task_logging":
            return {"enabled": False}
        if key == "prompt_library":
            return {"enabled": True}
        if key == "model":
            return {}
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
        if key == "frontend_logo_url":
            return ""

        # For other keys, return the default to avoid Mock objects
        return default if default is not None else {}

    factory.mock_component.get_config = custom_get_config

    # Set up auth overrides
    from fastapi import Request
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    from solace_agent_mesh.gateway.http_sse.dependencies import get_user_id

    async def override_get_current_user(request: Request):
        user_id = request.headers.get(TEST_USER_HEADER, "sam_dev_user")
        return {
            "id": user_id,
            "name": "Sam Dev User" if user_id == "sam_dev_user" else "Test User",
            "email": f"{user_id}@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }

    def override_get_user_id(request: Request):
        return request.headers.get(TEST_USER_HEADER, "sam_dev_user")

    factory.app.dependency_overrides[get_current_user] = override_get_current_user
    factory.app.dependency_overrides[get_user_id] = override_get_user_id

    # Create header-based test client
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str = "sam_dev_user"):
            super().__init__(app)
            self.test_user_id = user_id
            self._factory = factory  # Store factory reference for cleanup

        def request(self, method, url, **kwargs):
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)

        def cleanup(self):
            """Clean up the factory"""
            self._factory.teardown()

    return HeaderBasedTestClient(factory.app)


class TestBackgroundTasksConfigEndpoint:
    """Tests for the /api/v1/config endpoint's background_tasks exposure"""

    def test_config_exposes_background_tasks_disabled_by_default(
        self, api_client: TestClient
    ):
        """Test that config endpoint exposes background_tasks with default disabled state"""
        response = api_client.get("/api/v1/config")
        assert response.status_code == 200

        config_data = response.json()
        assert "frontend_feature_enablement" in config_data
        assert "background_tasks" in config_data["frontend_feature_enablement"]
        assert "background_tasks_config" in config_data
        assert "default_timeout_ms" in config_data["background_tasks_config"]

    def test_config_background_tasks_enabled_true(self, db_provider):
        """Test that config endpoint shows background_tasks.enabled=true when configured"""
        if hasattr(db_provider, "get_gateway_url_with_credentials"):
            db_url = db_provider.get_gateway_url_with_credentials()
        else:
            db_url = str(db_provider.get_sync_gateway_engine().url)

        client = _create_background_tasks_config_client(
            db_url=db_url,
            background_tasks_enabled=True,
            background_tasks_timeout_ms=7200000  # 2 hours
        )

        try:
            response = client.get("/api/v1/config")
            assert response.status_code == 200

            config_data = response.json()
            assert "frontend_feature_enablement" in config_data
            assert config_data["frontend_feature_enablement"]["background_tasks"] is True
            assert "background_tasks_config" in config_data
            assert config_data["background_tasks_config"]["default_timeout_ms"] == 7200000
        finally:
            client.cleanup()

    def test_config_background_tasks_enabled_false(self, db_provider):
        """Test that config endpoint shows background_tasks.enabled=false when configured"""
        if hasattr(db_provider, "get_gateway_url_with_credentials"):
            db_url = db_provider.get_gateway_url_with_credentials()
        else:
            db_url = str(db_provider.get_sync_gateway_engine().url)

        client = _create_background_tasks_config_client(
            db_url=db_url,
            background_tasks_enabled=False,
            background_tasks_timeout_ms=3600000
        )

        try:
            response = client.get("/api/v1/config")
            assert response.status_code == 200

            config_data = response.json()
            assert "frontend_feature_enablement" in config_data
            assert config_data["frontend_feature_enablement"]["background_tasks"] is False
            assert "background_tasks_config" in config_data
            assert config_data["background_tasks_config"]["default_timeout_ms"] == 3600000
        finally:
            client.cleanup()

    def test_config_background_tasks_custom_timeout(self, db_provider):
        """Test that config endpoint exposes custom timeout value"""
        if hasattr(db_provider, "get_gateway_url_with_credentials"):
            db_url = db_provider.get_gateway_url_with_credentials()
        else:
            db_url = str(db_provider.get_sync_gateway_engine().url)

        custom_timeout = 1800000  # 30 minutes
        client = _create_background_tasks_config_client(
            db_url=db_url,
            background_tasks_enabled=True,
            background_tasks_timeout_ms=custom_timeout
        )

        try:
            response = client.get("/api/v1/config")
            assert response.status_code == 200

            config_data = response.json()
            assert config_data["background_tasks_config"]["default_timeout_ms"] == custom_timeout
        finally:
            client.cleanup()

    def test_config_consistency_across_requests(self, db_provider):
        """Test that config endpoint returns consistent background_tasks status"""
        if hasattr(db_provider, "get_gateway_url_with_credentials"):
            db_url = db_provider.get_gateway_url_with_credentials()
        else:
            db_url = str(db_provider.get_sync_gateway_engine().url)

        client = _create_background_tasks_config_client(
            db_url=db_url,
            background_tasks_enabled=True,
            background_tasks_timeout_ms=3600000
        )

        try:
            # Make multiple requests to config endpoint
            responses = [client.get("/api/v1/config") for _ in range(5)]

            # All should return same background_tasks status
            enabled_values = [r.json()["frontend_feature_enablement"]["background_tasks"] for r in responses]
            timeout_values = [r.json()["background_tasks_config"]["default_timeout_ms"] for r in responses]

            assert all(val == enabled_values[0] for val in enabled_values)
            assert all(val == timeout_values[0] for val in timeout_values)
        finally:
            client.cleanup()