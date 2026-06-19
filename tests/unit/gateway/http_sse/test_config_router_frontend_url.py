#!/usr/bin/env python3
"""
Unit tests for frontend_server_url in the /api/v1/config endpoint.

Tests that the config router correctly returns the frontend_server_url
from the component. By default, frontend_server_url is empty, allowing
the frontend to use relative URLs for same-origin requests.
"""

import logging

import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.routers.config import (
    MAX_FRONTEND_DISCLAIMER_TEXT_LEN,
    get_app_config,
)


@pytest.fixture
def mock_component():
    """Mock WebUIBackendComponent with frontend_server_url."""
    component = MagicMock()
    component.frontend_server_url = ""  # Default is empty for relative URLs
    component.get_config.side_effect = lambda key, default=None: {
        "platform_service": {"url": "http://localhost:8001"},
        "frontend_feature_enablement": {},
        "task_logging": {},
        "prompt_library": {"enabled": False},
        "frontend_collect_feedback": False,
        "session_service": {"type": "memory"},
        "frontend_auth_login_url": "",
        "frontend_use_authorization": False,
        "frontend_welcome_message": "",
        "frontend_redirect_url": "",
        "frontend_bot_name": "A2A Agent",
        "frontend_logo_url": "",
        "frontend_disclaimer_text": "",
        "speech": {},
    }.get(key, default)
    return component


@pytest.fixture
def mock_api_config():
    """Mock API config."""
    return {
        "persistence_enabled": False,
    }


class TestConfigRouterFrontendServerUrl:
    """Tests for frontend_server_url in /api/v1/config response."""

    @pytest.mark.asyncio
    async def test_returns_empty_string_by_default(self, mock_component, mock_api_config):
        """Test that empty string is returned by default for relative URLs."""
        # Default mock already has empty frontend_server_url
        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == ""

    @pytest.mark.asyncio
    async def test_returns_configured_url(self, mock_component, mock_api_config):
        """Test that configured URL is returned in config."""
        mock_component.frontend_server_url = "http://localhost:8000"

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_returns_explicitly_configured_url(self, mock_component, mock_api_config):
        """Test that explicitly configured URL is returned in config."""
        mock_component.frontend_server_url = "https://custom.example.com"

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "https://custom.example.com"

    @pytest.mark.asyncio
    async def test_returns_https_url_when_ssl_enabled(self, mock_component, mock_api_config):
        """Test that HTTPS URL is returned when SSL is configured."""
        mock_component.frontend_server_url = "https://localhost:8443"

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "https://localhost:8443"

    @pytest.mark.asyncio
    async def test_returns_custom_host_url(self, mock_component, mock_api_config):
        """Test that custom host URLs are returned correctly."""
        mock_component.frontend_server_url = "http://webui-gateway.internal:8000"

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "http://webui-gateway.internal:8000"

    @pytest.mark.asyncio
    async def test_platform_url_also_returned(self, mock_component, mock_api_config):
        """Test that both frontend_server_url and frontend_platform_server_url are returned."""
        mock_component.frontend_server_url = "http://localhost:8000"
        mock_component.get_config.side_effect = lambda key, default=None: {
            "platform_service": {"url": "http://localhost:8001"},
            "frontend_feature_enablement": {},
            "task_logging": {},
            "prompt_library": {"enabled": False},
            "frontend_collect_feedback": False,
            "session_service": {"type": "memory"},
            "frontend_auth_login_url": "",
            "frontend_use_authorization": False,
            "frontend_welcome_message": "",
            "frontend_redirect_url": "",
            "frontend_bot_name": "A2A Agent",
            "frontend_logo_url": "",
            "speech": {},
        }.get(key, default)

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "http://localhost:8000"
        assert response["frontend_platform_server_url"] == "http://localhost:8001"

    @pytest.mark.asyncio
    async def test_empty_platform_url_handled(self, mock_component, mock_api_config):
        """Test that empty platform URL is handled gracefully."""
        mock_component.frontend_server_url = "http://localhost:8000"
        mock_component.get_config.side_effect = lambda key, default=None: {
            "platform_service": {"url": ""},
            "frontend_feature_enablement": {},
            "task_logging": {},
            "prompt_library": {"enabled": False},
            "frontend_collect_feedback": False,
            "session_service": {"type": "memory"},
            "frontend_auth_login_url": "",
            "frontend_use_authorization": False,
            "frontend_welcome_message": "",
            "frontend_redirect_url": "",
            "frontend_bot_name": "A2A Agent",
            "frontend_logo_url": "",
            "speech": {},
        }.get(key, default)

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_server_url"] == "http://localhost:8000"
        assert response["frontend_platform_server_url"] == ""


def _set_disclaimer(mock_component, value: str) -> None:
    """Point the mock's get_config at a map carrying the given disclaimer text."""
    mock_component.get_config.side_effect = lambda key, default=None: {
        "platform_service": {"url": "http://localhost:8001"},
        "frontend_feature_enablement": {},
        "task_logging": {},
        "prompt_library": {"enabled": False},
        "frontend_collect_feedback": False,
        "session_service": {"type": "memory"},
        "frontend_auth_login_url": "",
        "frontend_use_authorization": False,
        "frontend_welcome_message": "",
        "frontend_redirect_url": "",
        "frontend_bot_name": "A2A Agent",
        "frontend_logo_url": "",
        "frontend_disclaimer_text": value,
        "speech": {},
    }.get(key, default)


class TestConfigRouterDisclaimerText:
    """Tests for frontend_disclaimer_text in /api/v1/config response."""

    @pytest.mark.asyncio
    async def test_returns_empty_string_by_default(self, mock_component, mock_api_config):
        """Test that the disclaimer is empty by default."""
        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_disclaimer_text"] == ""

    @pytest.mark.asyncio
    async def test_round_trip(self, mock_component, mock_api_config):
        """Test that a configured disclaimer surfaces unchanged on the response."""
        disclaimer = "This assistant may produce inaccurate information."
        _set_disclaimer(mock_component, disclaimer)

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_disclaimer_text"] == disclaimer

    @pytest.mark.asyncio
    async def test_truncates_over_long_value_with_warning(
        self, mock_component, mock_api_config, caplog
    ):
        """Test that a >500-char value is truncated to exactly 500 chars and warns."""
        over_long = "x" * (MAX_FRONTEND_DISCLAIMER_TEXT_LEN + 123)
        _set_disclaimer(mock_component, over_long)

        with caplog.at_level(logging.WARNING):
            response = await get_app_config(mock_component, mock_api_config)

        assert len(response["frontend_disclaimer_text"]) == MAX_FRONTEND_DISCLAIMER_TEXT_LEN
        assert response["frontend_disclaimer_text"] == over_long[:MAX_FRONTEND_DISCLAIMER_TEXT_LEN]
        assert any(
            "frontend_disclaimer_text exceeds" in record.getMessage()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_value_at_limit_is_not_truncated(self, mock_component, mock_api_config):
        """Test that a value exactly at the limit is returned unchanged."""
        at_limit = "y" * MAX_FRONTEND_DISCLAIMER_TEXT_LEN
        _set_disclaimer(mock_component, at_limit)

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_disclaimer_text"] == at_limit

    @pytest.mark.asyncio
    async def test_non_string_value_is_coerced_not_crashing(self, mock_component, mock_api_config):
        """A hand-edited non-string YAML literal must be coerced, not 500 the endpoint."""
        _set_disclaimer(mock_component, 42)

        response = await get_app_config(mock_component, mock_api_config)

        assert response["frontend_disclaimer_text"] == "42"
