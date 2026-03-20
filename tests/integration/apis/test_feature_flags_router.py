"""
Integration tests for the GET /api/v1/config/features endpoint.

Tests verify the full HTTP request/response cycle through the FastAPI
application, including correct response structure and env-var override
behaviour.

These tests use a test-only features.yaml with fake flag names to avoid
coupling framework tests to real production flag definitions.
"""

from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)

from solace_agent_mesh.gateway.http_sse.dependencies import get_user_id
from solace_agent_mesh.shared.api.auth_utils import get_current_user

TEST_FEATURES_YAML = str(
    Path(__file__).parent / "fixtures" / "test_features.yaml"
)

TEST_USER_HEADER = "X-Test-User-Id"


def _create_feature_flags_client(db_url: str) -> TestClient:
    factory = WebUIBackendFactory(
        db_url=db_url,
        features_yaml_path=TEST_FEATURES_YAML,
    )

    async def override_get_current_user(request: Request):
        user_id = request.headers.get(TEST_USER_HEADER, "sam_dev_user")
        return {
            "id": user_id,
            "name": "Sam Dev User",
            "email": f"{user_id}@dev.local",
            "authenticated": True,
            "auth_method": "development",
        }

    def override_get_user_id(request: Request):
        return request.headers.get(TEST_USER_HEADER, "sam_dev_user")

    factory.app.dependency_overrides[get_current_user] = override_get_current_user
    factory.app.dependency_overrides[get_user_id] = override_get_user_id

    class HeaderBasedTestClient(TestClient):
        def __init__(self, app):
            super().__init__(app)
            self._factory = factory

        def request(self, method, url, **kwargs):
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = "sam_dev_user"
            return super().request(method, url, **kwargs)

        def cleanup(self):
            self._factory.teardown()

    return HeaderBasedTestClient(factory.app)


class TestGetFeatureFlagsEndpoint:
    """Tests for GET /api/v1/config/features using test-only flags."""

    @pytest.fixture(autouse=True)
    def _setup_client(self, db_provider):
        if hasattr(db_provider, "get_gateway_url_with_credentials"):
            db_url = db_provider.get_gateway_url_with_credentials()
        else:
            db_url = str(db_provider.get_sync_gateway_engine().url)

        self.client = _create_feature_flags_client(db_url)
        yield
        self.client.cleanup()

    def test_returns_200(self):
        response = self.client.get("/api/v1/config/features")
        assert response.status_code == 200

    def test_response_is_a_list(self):
        response = self.client.get("/api/v1/config/features")
        assert isinstance(response.json(), list)

    def test_each_flag_has_required_fields(self):
        response = self.client.get("/api/v1/config/features")
        for flag in response.json():
            assert "key" in flag
            assert "name" in flag
            assert "release_phase" in flag
            assert "resolved" in flag
            assert "has_env_override" in flag
            assert "registry_default" in flag
            assert "description" in flag

    def test_boolean_fields_are_booleans(self):
        response = self.client.get("/api/v1/config/features")
        for flag in response.json():
            assert isinstance(flag["resolved"], bool)
            assert isinstance(flag["has_env_override"], bool)
            assert isinstance(flag["registry_default"], bool)

    def test_expected_test_flags_are_present(self):
        response = self.client.get("/api/v1/config/features")
        keys = [f["key"] for f in response.json()]
        assert "test_flag_alpha" in keys
        assert "test_flag_beta" in keys
        assert "test_flag_gamma" in keys

    def test_no_production_flags_loaded(self):
        response = self.client.get("/api/v1/config/features")
        keys = {f["key"] for f in response.json()}
        assert "mentions" not in keys
        assert "auto_title_generation" not in keys

    def test_flag_metadata_matches_yaml(self):
        response = self.client.get("/api/v1/config/features")
        alpha = next(f for f in response.json() if f["key"] == "test_flag_alpha")
        assert alpha["release_phase"] == "beta"
        assert alpha["registry_default"] is False

        beta = next(f for f in response.json() if f["key"] == "test_flag_beta")
        assert beta["release_phase"] == "general_availability"
        assert beta["registry_default"] is True

    def test_no_env_override_by_default(self, monkeypatch):
        monkeypatch.delenv("SAM_FEATURE_TEST_FLAG_ALPHA", raising=False)
        monkeypatch.delenv("SAM_FEATURE_TEST_FLAG_BETA", raising=False)
        monkeypatch.delenv("SAM_FEATURE_TEST_FLAG_GAMMA", raising=False)
        response = self.client.get("/api/v1/config/features")
        for flag in response.json():
            assert flag["has_env_override"] is False

    def test_env_override_detected(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_TEST_FLAG_ALPHA", "true")
        response = self.client.get("/api/v1/config/features")
        flag = next(
            f for f in response.json() if f["key"] == "test_flag_alpha"
        )
        assert flag["has_env_override"] is True
        assert flag["resolved"] is True

    def test_env_override_false_value(self, monkeypatch):
        monkeypatch.setenv("SAM_FEATURE_TEST_FLAG_BETA", "false")
        response = self.client.get("/api/v1/config/features")
        flag = next(
            f for f in response.json() if f["key"] == "test_flag_beta"
        )
        assert flag["has_env_override"] is True
        assert flag["resolved"] is False

    def test_content_type_is_json(self):
        response = self.client.get("/api/v1/config/features")
        assert "application/json" in response.headers.get("content-type", "")

    def test_multiple_calls_return_consistent_results(self):
        r1 = self.client.get("/api/v1/config/features")
        r2 = self.client.get("/api/v1/config/features")
        assert r1.json() == r2.json()
