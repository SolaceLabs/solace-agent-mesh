"""
Tests for router registration in main.py.

Verifies that the version router is correctly registered in the FastAPI app
at line 609 of main.py.
"""

import pytest
from fastapi.testclient import TestClient


class TestVersionRouterRegistration:
    """Tests that the version router is properly registered in the app."""

    def test_version_router_is_registered_with_correct_prefix(
        self, api_client: TestClient
    ):
        """Test that version router is accessible at /api/v1/version."""
        response = api_client.get("/api/v1/version")
        assert response.status_code == 200

    def test_version_router_not_accessible_without_prefix(
        self, api_client: TestClient
    ):
        """Test that version endpoint requires the /api/v1 prefix."""
        response = api_client.get("/version")
        assert response.status_code == 404

    def test_version_router_has_correct_tag_in_openapi(
        self, api_client: TestClient
    ):
        """Test that version router is tagged with 'Version' in OpenAPI schema."""
        response = api_client.get("/openapi.json")
        assert response.status_code == 200
        openapi_schema = response.json()

        # Verify the /api/v1/version path exists
        assert "/api/v1/version" in openapi_schema["paths"]

        # Verify it has the correct tag
        version_endpoint = openapi_schema["paths"]["/api/v1/version"]["get"]
        assert "tags" in version_endpoint
        assert "Version" in version_endpoint["tags"]