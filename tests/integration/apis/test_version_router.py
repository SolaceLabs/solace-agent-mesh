"""
Integration tests for the version API router.

Tests the /api/v1/version endpoint and all helper functions for retrieving
version information about installed SAM products.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.routers import version


class TestGetVersionEndpoint:
    """Tests for the GET /api/v1/version endpoint."""

    def test_get_version_returns_200(self, api_client: TestClient):
        """Test that the version endpoint returns 200 OK."""
        response = api_client.get("/api/v1/version")
        assert response.status_code == 200

    def test_get_version_returns_valid_structure(self, api_client: TestClient):
        """Test that the version endpoint returns valid response structure."""
        response = api_client.get("/api/v1/version")
        data = response.json()

        assert "products" in data
        assert isinstance(data["products"], list)

    def test_get_version_includes_base_product(self, api_client: TestClient):
        """Test that the version response includes the base solace-agent-mesh product."""
        response = api_client.get("/api/v1/version")
        data = response.json()

        products = data["products"]
        base_product = next(
            (p for p in products if p["id"] == "solace-agent-mesh"), None
        )

        assert base_product is not None
        assert base_product["name"] == "Solace Agent Mesh"
        assert "version" in base_product
        assert "description" in base_product

    def test_get_version_includes_ui_product(self, api_client: TestClient):
        """Test that the version response includes the UI product."""
        response = api_client.get("/api/v1/version")
        data = response.json()

        products = data["products"]
        ui_product = next(
            (p for p in products if "solace-agent-mesh-ui" in p["id"].lower()), None
        )

        assert ui_product is not None
        assert "version" in ui_product

    def test_get_version_product_has_required_fields(self, api_client: TestClient):
        """Test that each product has all required fields."""
        response = api_client.get("/api/v1/version")
        data = response.json()

        for product in data["products"]:
            assert "id" in product
            assert "name" in product
            assert "description" in product
            assert "version" in product
            # dependencies is optional
            if "dependencies" in product and product["dependencies"] is not None:
                assert isinstance(product["dependencies"], dict)

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_base_product_info")
    def test_get_version_handles_exception_gracefully(
        self, mock_get_base, api_client: TestClient
    ):
        """Test that the endpoint returns 500 on internal errors."""
        mock_get_base.side_effect = Exception("Simulated error")

        response = api_client.get("/api/v1/version")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to retrieve version information" in data["detail"]

    def test_get_version_filters_not_installed_dependencies(
        self, api_client: TestClient
    ):
        """Test that not-installed dependencies are filtered out."""
        response = api_client.get("/api/v1/version")
        data = response.json()

        # Check that if dependencies exist, they don't contain "not-installed"
        for product in data["products"]:
            if "dependencies" in product and product["dependencies"]:
                for dep_version in product["dependencies"].values():
                    assert dep_version != "not-installed"


class TestGetPackageVersion:
    """Tests for the _get_package_version helper function."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version.version")
    def test_get_package_version_installed_package(self, mock_version):
        """Test getting version for an installed package."""
        mock_version.return_value = "1.2.3"

        result = version._get_package_version("test-package", "[TEST] ")

        assert result == "1.2.3"
        mock_version.assert_called_once_with("test-package")

    @patch("solace_agent_mesh.gateway.http_sse.routers.version.version")
    def test_get_package_version_not_installed(self, mock_version):
        """Test getting version for a package that's not installed."""
        from importlib.metadata import PackageNotFoundError

        mock_version.side_effect = PackageNotFoundError()

        result = version._get_package_version("nonexistent-package", "[TEST] ")

        assert result == version.NOT_INSTALLED

    @patch("solace_agent_mesh.gateway.http_sse.routers.version.version")
    def test_get_package_version_edge_case_versions(self, mock_version):
        """Test getting version with various version formats."""
        test_cases = [
            "1.0.0",
            "2.1.3-beta",
            "0.0.1-alpha.1",
            "1.2.3+build.456",
            "10.20.30-rc.1+build.123",
        ]

        for test_version in test_cases:
            mock_version.return_value = test_version
            result = version._get_package_version("test-package", "[TEST] ")
            assert result == test_version


class TestGetBaseProductInfo:
    """Tests for the _get_base_product_info helper function."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_base_product_info_structure(self, mock_get_version):
        """Test that base product info has correct structure."""
        mock_get_version.side_effect = lambda pkg, _: {
            "solace-agent-mesh": "1.0.0",
            "a2a-sdk": "0.5.0",
            "google-adk": "0.3.0",
        }.get(pkg, version.NOT_INSTALLED)

        result = version._get_base_product_info("[TEST] ")

        assert result.id == "solace-agent-mesh"
        assert result.name == "Solace Agent Mesh"
        assert result.version == "1.0.0"
        assert result.dependencies == {"a2a-sdk": "0.5.0", "google-adk": "0.3.0"}

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_base_product_info_missing_dependencies(self, mock_get_version):
        """Test base product when some dependencies are not installed."""
        mock_get_version.side_effect = lambda pkg, _: {
            "solace-agent-mesh": "1.0.0",
            "a2a-sdk": "0.5.0",
            "google-adk": version.NOT_INSTALLED,
        }.get(pkg, version.NOT_INSTALLED)

        result = version._get_base_product_info("[TEST] ")

        # Should only include installed dependencies
        assert result.dependencies == {"a2a-sdk": "0.5.0"}
        assert "google-adk" not in result.dependencies

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_base_product_info_no_dependencies_installed(self, mock_get_version):
        """Test base product when no dependencies are installed."""
        mock_get_version.side_effect = lambda pkg, _: (
            "1.0.0" if pkg == "solace-agent-mesh" else version.NOT_INSTALLED
        )

        result = version._get_base_product_info("[TEST] ")

        # Should have None for dependencies when none are installed
        assert result.dependencies is None


class TestGetUIProductInfo:
    """Tests for the _get_ui_product_info helper function."""

    def test_get_ui_product_info_returns_product_info(self):
        """Test that UI product info is returned."""
        result = version._get_ui_product_info("[TEST] ")

        assert result is not None
        assert "solace-agent-mesh-ui" in result.id.lower()
        assert result.name == "Solace Agent Mesh UI"
        assert result.version is not None

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._read_ui_version_file")
    def test_get_ui_product_info_with_valid_version_file(self, mock_read):
        """Test UI product info when ui-version.json is found."""
        mock_read.return_value = {
            "id": "custom-ui-id",
            "name": "Custom UI Name",
            "description": "Custom description",
            "version": "2.0.0",
        }

        result = version._get_ui_product_info("[TEST] ")

        assert result.id == "custom-ui-id"
        assert result.name == "Custom UI Name"
        assert result.version == "2.0.0"

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._read_ui_version_file")
    def test_get_ui_product_info_with_no_version_file(self, mock_read):
        """Test UI product info when no ui-version.json is found."""
        mock_read.return_value = None

        result = version._get_ui_product_info("[TEST] ")

        # Should return default UI product info
        assert result is not None
        assert result.version == version.UNKNOWN_VERSION

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._read_ui_version_file")
    def test_get_ui_product_info_with_invalid_format(self, mock_read):
        """Test UI product info when ui-version.json has invalid format."""
        # Return dict missing required fields
        mock_read.return_value = {"invalid": "format"}

        result = version._get_ui_product_info("[TEST] ")

        # Should fall back to default
        assert result is not None
        assert result.version == version.UNKNOWN_VERSION


class TestReadUIVersionFile:
    """Tests for the _read_ui_version_file helper function."""

    def test_read_ui_version_file_exists(self):
        """Test reading a valid ui-version.json file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "ui-version.json"
            test_data = {
                "id": "test-ui",
                "name": "Test UI",
                "version": "1.0.0",
                "description": "Test UI description",
            }
            version_file.write_text(json.dumps(test_data))

            result = version._read_ui_version_file(version_file, "[TEST] ")

            assert result == test_data

    def test_read_ui_version_file_not_exists(self):
        """Test reading a non-existent ui-version.json file."""
        non_existent_path = Path("/nonexistent/path/ui-version.json")

        result = version._read_ui_version_file(non_existent_path, "[TEST] ")

        assert result is None

    def test_read_ui_version_file_invalid_json(self):
        """Test reading a ui-version.json file with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "ui-version.json"
            version_file.write_text("{ invalid json }")

            result = version._read_ui_version_file(version_file, "[TEST] ")

            assert result is None

    def test_read_ui_version_file_empty_file(self):
        """Test reading an empty ui-version.json file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "ui-version.json"
            version_file.write_text("")

            result = version._read_ui_version_file(version_file, "[TEST] ")

            assert result is None


class TestGetDefaultUIProductInfo:
    """Tests for the _get_default_ui_product_info helper function."""

    def test_get_default_ui_product_info_structure(self):
        """Test that default UI product info has correct structure."""
        result = version._get_default_ui_product_info()

        assert result.id == "@SolaceLabs/solace-agent-mesh-ui"
        assert result.name == "Solace Agent Mesh UI"
        assert result.description == "React UI components for Solace Agent Mesh"
        assert result.version == version.UNKNOWN_VERSION
        assert result.dependencies is None


class TestGetEnterpriseProductInfo:
    """Tests for the _get_enterprise_product_info helper function."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_enterprise_product_info_installed(self, mock_get_version):
        """Test getting enterprise product info when package is installed."""
        mock_get_version.return_value = "1.5.0"

        result = version._get_enterprise_product_info("[TEST] ")

        assert result is not None
        assert result.id == "solace-agent-mesh-enterprise"
        assert result.name == "Solace Agent Mesh Enterprise"
        assert result.version == "1.5.0"

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_enterprise_product_info_not_installed(self, mock_get_version):
        """Test getting enterprise product info when package is not installed."""
        mock_get_version.return_value = version.NOT_INSTALLED

        result = version._get_enterprise_product_info("[TEST] ")

        assert result is None


class TestGetSolaceChatProductInfo:
    """Tests for the _get_solace_chat_product_info helper function."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_solace_chat_product_info_installed(self, mock_get_version):
        """Test getting solace-chat product info when package is installed."""
        mock_get_version.side_effect = lambda pkg, _: {
            "solace-chat": "2.0.0",
            "sam-slack": "1.0.0",
            "sam-teams-gateway": "1.1.0",
            "sam-confluence": version.NOT_INSTALLED,
        }.get(pkg, version.NOT_INSTALLED)

        result = version._get_solace_chat_product_info("[TEST] ")

        assert result is not None
        assert result.id == "solace-chat"
        assert result.name == "Solace Chat"
        assert result.version == "2.0.0"
        # Should only include installed dependencies
        assert "sam-slack" in result.dependencies
        assert "sam-teams-gateway" in result.dependencies
        assert "sam-confluence" not in result.dependencies

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_solace_chat_product_info_not_installed(self, mock_get_version):
        """Test getting solace-chat product info when package is not installed."""
        mock_get_version.return_value = version.NOT_INSTALLED

        result = version._get_solace_chat_product_info("[TEST] ")

        assert result is None

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_solace_chat_product_info_no_dependencies(self, mock_get_version):
        """Test solace-chat with no dependencies installed."""
        mock_get_version.side_effect = lambda pkg, _: (
            "2.0.0" if pkg == "solace-chat" else version.NOT_INSTALLED
        )

        result = version._get_solace_chat_product_info("[TEST] ")

        assert result is not None
        assert result.dependencies is None


class TestGetEnterpriseUIVersionPath:
    """Tests for the _get_enterprise_ui_version_path helper function."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_get_enterprise_ui_version_path_not_installed(self, mock_get_version):
        """Test getting enterprise UI path when enterprise is not installed."""
        mock_get_version.return_value = version.NOT_INSTALLED

        result = version._get_enterprise_ui_version_path("[TEST] ")

        assert result is None

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    @patch("solace_agent_mesh.gateway.http_sse.routers.version.Path")
    def test_get_enterprise_ui_version_path_import_error(
        self, mock_path, mock_get_version
    ):
        """Test handling of import error when enterprise package exists but can't be imported."""
        mock_get_version.return_value = "1.0.0"

        with patch.dict("sys.modules", {"solace_agent_mesh_enterprise": None}):
            result = version._get_enterprise_ui_version_path("[TEST] ")

        # Should return None when import fails
        assert result is None


class TestGetInstalledUIVersionPath:
    """Tests for the _get_installed_ui_version_path helper function."""

    def test_get_installed_ui_version_path_returns_path(self):
        """Test that installed UI version path is returned."""
        result = version._get_installed_ui_version_path()

        assert isinstance(result, Path)
        # Should construct path relative to current file
        assert "client" in str(result)
        assert "ui-version.json" in str(result)


class TestGetDevUIVersionPath:
    """Tests for the _get_dev_ui_version_path helper function."""

    def test_get_dev_ui_version_path_returns_path(self):
        """Test that dev UI version path is returned."""
        result = version._get_dev_ui_version_path()

        assert isinstance(result, Path)
        # Should construct path relative to current file
        assert "client" in str(result)
        assert "ui-version.json" in str(result)


class TestVersionEndpointEdgeCases:
    """Edge case tests for the version endpoint."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.version._get_package_version")
    def test_version_endpoint_with_special_version_formats(
        self, mock_get_version, api_client: TestClient
    ):
        """Test that the endpoint handles various version string formats."""
        # Test with development version
        mock_get_version.return_value = "1.0.0.dev0"

        response = api_client.get("/api/v1/version")

        assert response.status_code == 200

    def test_version_endpoint_multiple_calls_consistent(self, api_client: TestClient):
        """Test that multiple calls to the endpoint return consistent results."""
        response1 = api_client.get("/api/v1/version")
        response2 = api_client.get("/api/v1/version")

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Product lists should be the same
        assert response1.json()["products"] == response2.json()["products"]

    def test_version_endpoint_response_time(self, api_client: TestClient):
        """Test that the version endpoint responds in reasonable time."""
        import time

        start = time.time()
        response = api_client.get("/api/v1/version")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond within 2 seconds
        assert duration < 2.0

    def test_version_endpoint_content_type(self, api_client: TestClient):
        """Test that the endpoint returns correct content type."""
        response = api_client.get("/api/v1/version")

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
