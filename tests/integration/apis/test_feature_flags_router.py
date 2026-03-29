"""
Integration tests for the GET /api/v1/config/features endpoint.

Tests verify the full HTTP request/response cycle through the FastAPI
application, including correct response structure and env-var override
behaviour.
"""

from fastapi.testclient import TestClient


class TestGetFeatureFlagsEndpoint:
    """Tests for GET /api/v1/config/features."""

    def test_returns_200(self, api_client: TestClient):
        """The endpoint must return HTTP 200 OK."""
        response = api_client.get("/api/v1/config/features")
        assert response.status_code == 200

    def test_response_is_a_list(self, api_client: TestClient):
        """The response body must be a JSON array."""
        response = api_client.get("/api/v1/config/features")
        assert isinstance(response.json(), list)

    def test_each_flag_has_required_fields(self, api_client: TestClient):
        """Every flag object must carry all declared DTO fields."""
        response = api_client.get("/api/v1/config/features")
        for flag in response.json():
            assert "key" in flag
            assert "name" in flag
            assert "release_phase" in flag
            assert "resolved" in flag
            assert "has_env_override" in flag
            assert "registry_default" in flag
            assert "description" in flag

    def test_boolean_fields_are_booleans(self, api_client: TestClient):
        """resolved, has_env_override, and registry_default must be booleans."""
        response = api_client.get("/api/v1/config/features")
        for flag in response.json():
            assert isinstance(flag["resolved"], bool)
            assert isinstance(flag["has_env_override"], bool)
            assert isinstance(flag["registry_default"], bool)

    def test_community_yaml_flag_is_present(self, api_client: TestClient):
        """The background_tasks flag from community features.yaml is present."""
        response = api_client.get("/api/v1/config/features")
        keys = [f["key"] for f in response.json()]
        assert "background_tasks" in keys

    def test_background_tasks_flag_fields(self, api_client: TestClient):
        """background_tasks must have the expected metadata values."""
        response = api_client.get("/api/v1/config/features")
        flag = next(
            f for f in response.json() if f["key"] == "background_tasks"
        )
        assert flag["release_phase"] == "general_availability"
        assert flag["registry_default"] is False

    def test_no_env_override_by_default(self, api_client: TestClient, monkeypatch):
        """Without env vars set, has_env_override is False for every flag."""
        monkeypatch.delenv("SAM_FEATURE_BACKGROUND_TASKS", raising=False)
        response = api_client.get("/api/v1/config/features")
        for flag in response.json():
            assert flag["has_env_override"] is False

    def test_env_override_detected(self, api_client: TestClient, monkeypatch):
        """Setting SAM_FEATURE_<KEY> must flip has_env_override to True."""
        monkeypatch.setenv("SAM_FEATURE_BACKGROUND_TASKS", "true")
        response = api_client.get("/api/v1/config/features")
        flag = next(
            f for f in response.json() if f["key"] == "background_tasks"
        )
        assert flag["has_env_override"] is True
        assert flag["resolved"] is True

    def test_env_override_false_value_sets_has_env_override(
        self, api_client: TestClient, monkeypatch
    ):
        """SAM_FEATURE_<KEY>=false: has_env_override True, resolved False."""
        monkeypatch.setenv("SAM_FEATURE_BACKGROUND_TASKS", "false")
        response = api_client.get("/api/v1/config/features")
        flag = next(
            f for f in response.json() if f["key"] == "background_tasks"
        )
        assert flag["has_env_override"] is True
        assert flag["resolved"] is False

    def test_content_type_is_json(self, api_client: TestClient):
        """The endpoint must return application/json content type."""
        response = api_client.get("/api/v1/config/features")
        assert "application/json" in response.headers.get("content-type", "")

    def test_multiple_calls_return_consistent_results(
        self, api_client: TestClient
    ):
        """Successive calls without state changes must return identical data."""
        r1 = api_client.get("/api/v1/config/features")
        r2 = api_client.get("/api/v1/config/features")
        assert r1.json() == r2.json()
