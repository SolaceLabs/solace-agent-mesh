#!/usr/bin/env python3
"""
Unit tests for CORS auto-construction in Platform Service.

Tests the auto-construction logic that builds the frontend URL from environment
variables and automatically adds it to CORS allowed origins.
"""

from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.services.platform.api.main import _setup_middleware


@pytest.fixture
def mock_component():
    """Mock PlatformServiceComponent."""
    component = MagicMock()
    component.get_cors_origins.return_value = ["http://localhost:3000"]
    component.get_cors_origin_regex.return_value = ""
    component.get_config.return_value = False
    return component


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables before each test."""
    env_vars = [
        "FRONTEND_SERVER_URL",
        "PLATFORM_SERVICE_URL",
        "FASTAPI_HOST",
        "FASTAPI_PORT",
        "FASTAPI_HTTPS_PORT",
        "SSL_KEYFILE",
        "SSL_CERTFILE",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture(autouse=True)
def mock_oauth_middleware():
    """Auto-patch OAuth middleware for all tests."""
    with patch('solace_agent_mesh.shared.auth.middleware.create_oauth_middleware'):
        yield


@pytest.fixture(autouse=True)
def mock_fastapi_app():
    """Auto-patch FastAPI app for all tests."""
    with patch('solace_agent_mesh.services.platform.api.main.app') as mock_app:
        yield mock_app


def _get_cors_allowed_origins(mock_fastapi_app):
    """Helper to get CORS allowed origins from the first add_middleware call."""
    cors_call = mock_fastapi_app.add_middleware.call_args_list[0]
    return cors_call[1]["allow_origins"]


def _get_cors_origin_regex(mock_fastapi_app):
    """Helper to get CORS origin regex from the first add_middleware call."""
    cors_call = mock_fastapi_app.add_middleware.call_args_list[0]
    return cors_call[1].get("allow_origin_regex")


class TestPlatformServiceCorsAutoConstruction:
    """Tests for Platform Service CORS auto-construction."""

    def test_auto_construct_from_default_env_vars(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test auto-construction using default environment variables."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "http://localhost:8000" in allowed_origins
        assert "http://localhost:3000" in allowed_origins  # Configured origin

    def test_explicit_frontend_url_takes_precedence(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that explicit FRONTEND_SERVER_URL overrides auto-construction."""
        clean_env.setenv("FRONTEND_SERVER_URL", "https://custom.example.com")
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "https://custom.example.com" in allowed_origins
        assert "http://localhost:8000" not in allowed_origins  # Not auto-constructed

    def test_ssl_auto_detection(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test HTTPS construction when SSL certificates are configured."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")
        clean_env.setenv("FASTAPI_HTTPS_PORT", "8443")
        clean_env.setenv("SSL_KEYFILE", "/path/to/key.pem")
        clean_env.setenv("SSL_CERTFILE", "/path/to/cert.pem")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "https://localhost:8443" in allowed_origins

    def test_custom_host_preserved(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that custom hosts (not 127.0.0.1) are preserved."""
        clean_env.setenv("FASTAPI_HOST", "192.168.1.100")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "http://192.168.1.100:8000" in allowed_origins

    def test_platform_service_url_added(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that PLATFORM_SERVICE_URL is added to allowed origins."""
        clean_env.setenv("PLATFORM_SERVICE_URL", "http://localhost:8001")
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "http://localhost:8001" in allowed_origins
        assert "http://localhost:8000" in allowed_origins

    def test_deduplication_of_origins(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that duplicate origins are deduplicated."""
        # Component already has http://localhost:3000 in cors_allowed_origins
        clean_env.setenv("FRONTEND_SERVER_URL", "http://localhost:3000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        # Should only appear once
        assert allowed_origins.count("http://localhost:3000") == 1

    def test_empty_env_vars_handled(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that empty environment variables are handled gracefully."""
        clean_env.setenv("FRONTEND_SERVER_URL", "")
        clean_env.setenv("PLATFORM_SERVICE_URL", "")
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        # Should auto-construct from FASTAPI_HOST/PORT since FRONTEND_SERVER_URL is empty
        assert "http://localhost:8000" in allowed_origins

    def test_ssl_requires_both_cert_files(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that SSL is only used when BOTH keyfile and certfile are present."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")
        clean_env.setenv("FASTAPI_HTTPS_PORT", "8443")
        clean_env.setenv("SSL_KEYFILE", "/path/to/key.pem")
        clean_env.setenv("SSL_CERTFILE", "")  # Empty certfile

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        # Should use HTTP, not HTTPS
        assert "http://localhost:8000" in allowed_origins
        assert "https://localhost:8443" not in allowed_origins

    def test_configured_origins_preserved(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that configured CORS origins are preserved."""
        mock_component.get_cors_origins.return_value = [
            "http://localhost:3000",
            "https://app.example.com"
        ]
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        # All origins should be present
        assert "http://localhost:3000" in allowed_origins
        assert "https://app.example.com" in allowed_origins
        assert "http://localhost:8000" in allowed_origins

    def test_custom_https_port(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test custom HTTPS port is used when SSL is configured."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")
        clean_env.setenv("FASTAPI_HTTPS_PORT", "9443")
        clean_env.setenv("SSL_KEYFILE", "/path/to/key.pem")
        clean_env.setenv("SSL_CERTFILE", "/path/to/cert.pem")

        _setup_middleware(mock_component)

        allowed_origins = _get_cors_allowed_origins(mock_fastapi_app)

        assert "https://localhost:9443" in allowed_origins

    def test_cors_origin_regex_not_set_by_default(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that CORS origin regex is None when not configured."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")

        _setup_middleware(mock_component)

        cors_regex = _get_cors_origin_regex(mock_fastapi_app)

        assert cors_regex is None

    def test_cors_origin_regex_passed_to_middleware(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that CORS origin regex is passed to CORSMiddleware when configured."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")
        mock_component.get_cors_origin_regex.return_value = r"https?://(localhost|127\.0\.0\.1):\d+"

        _setup_middleware(mock_component)

        cors_regex = _get_cors_origin_regex(mock_fastapi_app)

        assert cors_regex == r"https?://(localhost|127\.0\.0\.1):\d+"

    def test_cors_origin_regex_empty_string_becomes_none(
        self, mock_fastapi_app, mock_component, clean_env
    ):
        """Test that empty string regex is converted to None."""
        clean_env.setenv("FASTAPI_HOST", "127.0.0.1")
        clean_env.setenv("FASTAPI_PORT", "8000")
        mock_component.get_cors_origin_regex.return_value = ""

        _setup_middleware(mock_component)

        cors_regex = _get_cors_origin_regex(mock_fastapi_app)

        assert cors_regex is None