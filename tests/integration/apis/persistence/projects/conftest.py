"""
Pytest fixtures for projects feature flag testing.

Provides custom configured API clients for testing different feature flag scenarios.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from sam_test_infrastructure.fastapi_service.webui_backend_factory import WebUIBackendFactory


# Custom header for test user identification (matches parent conftest)
TEST_USER_HEADER = "X-Test-User-Id"


def _create_custom_config_client(
    db_url: str,
    projects_enabled: bool = True,
    feature_flag_enabled: bool = True
):
    """
    Helper to create a test client with custom project configuration.

    Args:
        db_url: Database URL to use
        projects_enabled: Value for projects.enabled config
        feature_flag_enabled: Value for frontend_feature_enablement.projects

    Returns:
        TestClient configured with specified settings
    """
    factory = WebUIBackendFactory(db_url=db_url)

    # Store original get_config
    original_get_config = factory.mock_component.get_config

    def custom_get_config(key, default=None):
        # Override specific config keys
        if key == "projects":
            return {"enabled": projects_enabled}
        if key == "frontend_feature_enablement":
            return {"projects": feature_flag_enabled}
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
    from solace_agent_mesh.shared.api.auth_utils import get_current_user
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


@pytest.fixture
def projects_disabled_client(db_provider):
    """API client with projects explicitly disabled via projects.enabled=false"""
    if hasattr(db_provider, "get_gateway_url_with_credentials"):
        db_url = db_provider.get_gateway_url_with_credentials()
    else:
        db_url = str(db_provider.get_sync_gateway_engine().url)

    client = _create_custom_config_client(
        db_url=db_url,
        projects_enabled=False,
        feature_flag_enabled=True
    )

    yield client

    client.cleanup()


@pytest.fixture
def feature_flag_disabled_client(db_provider):
    """API client with projects disabled via frontend_feature_enablement.projects=false"""
    if hasattr(db_provider, "get_gateway_url_with_credentials"):
        db_url = db_provider.get_gateway_url_with_credentials()
    else:
        db_url = str(db_provider.get_sync_gateway_engine().url)

    client = _create_custom_config_client(
        db_url=db_url,
        projects_enabled=True,
        feature_flag_enabled=False
    )

    yield client

    client.cleanup()


@pytest.fixture
def both_disabled_client(db_provider):
    """API client with both projects.enabled and feature flag disabled"""
    if hasattr(db_provider, "get_gateway_url_with_credentials"):
        db_url = db_provider.get_gateway_url_with_credentials()
    else:
        db_url = str(db_provider.get_sync_gateway_engine().url)

    client = _create_custom_config_client(
        db_url=db_url,
        projects_enabled=False,
        feature_flag_enabled=False
    )

    yield client

    client.cleanup()


@pytest.fixture
def both_enabled_client(db_provider):
    """API client with both projects.enabled and feature flag enabled"""
    if hasattr(db_provider, "get_gateway_url_with_credentials"):
        db_url = db_provider.get_gateway_url_with_credentials()
    else:
        db_url = str(db_provider.get_sync_gateway_engine().url)

    client = _create_custom_config_client(
        db_url=db_url,
        projects_enabled=True,
        feature_flag_enabled=True
    )

    yield client

    client.cleanup()
