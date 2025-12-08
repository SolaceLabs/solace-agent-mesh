#!/usr/bin/env python3
"""
Unit tests for frontend_server_url auto-construction in WebUIBackendComponent.

Tests the auto-construction logic that builds the frontend_server_url from
fastapi_host, fastapi_port, and SSL configuration when not explicitly provided.
"""

import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


@pytest.fixture
def base_config():
    """Base configuration for WebUI Gateway component."""
    return {
        "component_config": {
            "app_config": {
                "namespace": "/test",
                "gateway_id": "test_gateway",
                "session_secret_key": "test_secret_key",
                "session_service": {"type": "memory"},
            }
        }
    }


class TestFrontendServerUrlConstruction:
    """Tests for frontend_server_url auto-construction logic."""

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_default_http_localhost(self, mock_dependencies, base_config):
        """Test default construction: HTTP on localhost:8000."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 8000,
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://localhost:8000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_https_with_ssl_configured(self, mock_dependencies, base_config):
        """Test HTTPS construction when SSL certificates are configured."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 8000,
            "fastapi_https_port": 8443,
            "ssl_keyfile": "/path/to/key.pem",
            "ssl_certfile": "/path/to/cert.pem",
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "https://localhost:8443"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_custom_host_preserved(self, mock_dependencies, base_config):
        """Test that custom hosts (not 127.0.0.1) are preserved."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "192.168.1.100",
            "fastapi_port": 8000,
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://192.168.1.100:8000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_custom_port(self, mock_dependencies, base_config):
        """Test custom port is used in URL."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 9000,
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://localhost:9000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_explicit_configuration_takes_precedence(self, mock_dependencies, base_config):
        """Test that explicitly configured URL overrides auto-construction."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 8000,
            "frontend_server_url": "https://custom.example.com",
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "https://custom.example.com"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_domain_name_host(self, mock_dependencies, base_config):
        """Test domain name host is preserved."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "webui-gateway.example.com",
            "fastapi_port": 8000,
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://webui-gateway.example.com:8000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_ssl_only_with_both_cert_files(self, mock_dependencies, base_config):
        """Test that SSL is only used when BOTH keyfile and certfile are configured."""
        # Only keyfile, no certfile - should use HTTP
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 8000,
            "fastapi_https_port": 8443,
            "ssl_keyfile": "/path/to/key.pem",
            "ssl_certfile": "",  # Empty certfile
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://localhost:8000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_0_0_0_0_host_preserved(self, mock_dependencies, base_config):
        """Test that 0.0.0.0 host is preserved (not converted to localhost)."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "0.0.0.0",
            "fastapi_port": 8000,
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "http://0.0.0.0:8000"

    @patch('solace_agent_mesh.gateway.http_sse.component.dependencies')
    def test_custom_https_port(self, mock_dependencies, base_config):
        """Test custom HTTPS port is used when SSL is configured."""
        base_config["component_config"]["app_config"].update({
            "fastapi_host": "127.0.0.1",
            "fastapi_port": 8000,
            "fastapi_https_port": 9443,
            "ssl_keyfile": "/path/to/key.pem",
            "ssl_certfile": "/path/to/cert.pem",
        })

        component = WebUIBackendComponent(**base_config)

        assert component.frontend_server_url == "https://localhost:9443"