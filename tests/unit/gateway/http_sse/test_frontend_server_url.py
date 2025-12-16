#!/usr/bin/env python3
"""
Unit tests for frontend_server_url auto-construction in WebUIBackendComponent.

Tests the auto-construction logic that builds the frontend_server_url from
fastapi_host, fastapi_port, and SSL configuration when not explicitly provided.
"""

import pytest


def _construct_frontend_url(fastapi_host, fastapi_port, fastapi_https_port=8443,
                            ssl_keyfile="", ssl_certfile="", frontend_server_url=""):
    """
    Helper function that replicates the frontend_server_url construction logic
    from WebUIBackendComponent for unit testing without full component initialization.
    """
    if frontend_server_url:
        return frontend_server_url

    if ssl_keyfile and ssl_certfile:
        protocol = "https"
        port = fastapi_https_port
    else:
        protocol = "http"
        port = fastapi_port

    host = "localhost" if fastapi_host == "127.0.0.1" else fastapi_host
    return f"{protocol}://{host}:{port}"


class TestFrontendServerUrlConstruction:
    """Tests for frontend_server_url auto-construction logic."""

    def test_default_http_localhost(self):
        """Test default construction: HTTP on localhost:8000."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=8000,
        )
        assert url == "http://localhost:8000"

    def test_https_with_ssl_configured(self):
        """Test HTTPS construction when SSL certificates are configured."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=8000,
            fastapi_https_port=8443,
            ssl_keyfile="/path/to/key.pem",
            ssl_certfile="/path/to/cert.pem",
        )
        assert url == "https://localhost:8443"

    def test_custom_host_preserved(self):
        """Test that custom hosts (not 127.0.0.1) are preserved."""
        url = _construct_frontend_url(
            fastapi_host="192.168.1.100",
            fastapi_port=8000,
        )
        assert url == "http://192.168.1.100:8000"

    def test_custom_port(self):
        """Test custom port is used in URL."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=9000,
        )
        assert url == "http://localhost:9000"

    def test_explicit_configuration_takes_precedence(self):
        """Test that explicitly configured URL overrides auto-construction."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=8000,
            frontend_server_url="https://custom.example.com",
        )
        assert url == "https://custom.example.com"

    def test_domain_name_host(self):
        """Test domain name host is preserved."""
        url = _construct_frontend_url(
            fastapi_host="webui-gateway.example.com",
            fastapi_port=8000,
        )
        assert url == "http://webui-gateway.example.com:8000"

    def test_ssl_only_with_both_cert_files(self):
        """Test that SSL is only used when BOTH keyfile and certfile are configured."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=8000,
            fastapi_https_port=8443,
            ssl_keyfile="/path/to/key.pem",
            ssl_certfile="",  # Empty certfile
        )
        assert url == "http://localhost:8000"

    def test_0_0_0_0_host_preserved(self):
        """Test that 0.0.0.0 host is preserved (not converted to localhost)."""
        url = _construct_frontend_url(
            fastapi_host="0.0.0.0",
            fastapi_port=8000,
        )
        assert url == "http://0.0.0.0:8000"

    def test_custom_https_port(self):
        """Test custom HTTPS port is used when SSL is configured."""
        url = _construct_frontend_url(
            fastapi_host="127.0.0.1",
            fastapi_port=8000,
            fastapi_https_port=9443,
            ssl_keyfile="/path/to/key.pem",
            ssl_certfile="/path/to/cert.pem",
        )
        assert url == "https://localhost:9443"
