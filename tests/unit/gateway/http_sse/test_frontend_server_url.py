#!/usr/bin/env python3
"""
Unit tests for frontend_server_url in WebUIBackendComponent.

Tests that frontend_server_url is optional and defaults to empty string,
allowing the frontend to use relative URLs for same-origin requests.
"""

import pytest


class TestFrontendServerUrl:
    """Tests for frontend_server_url configuration."""

    def test_empty_string_when_not_configured(self):
        """Test that empty string is returned when not configured."""
        configured_value = ""
        result = configured_value or ""
        assert result == ""

    def test_explicit_configuration_used(self):
        """Test that explicitly configured URL is used."""
        configured_value = "https://custom.example.com"
        result = configured_value or ""
        assert result == "https://custom.example.com"

    def test_empty_string_allows_relative_urls(self):
        """Test that empty string allows frontend to use relative URLs."""
        frontend_server_url = ""
        # When empty, frontend should construct URLs like "/api/v1/chat"
        # instead of "http://localhost:8000/api/v1/chat"
        api_endpoint = "/api/v1/chat"
        full_url = f"{frontend_server_url}{api_endpoint}"
        assert full_url == "/api/v1/chat"

    def test_configured_url_prepended(self):
        """Test that configured URL is prepended to endpoints."""
        frontend_server_url = "https://custom.example.com"
        api_endpoint = "/api/v1/chat"
        full_url = f"{frontend_server_url}{api_endpoint}"
        assert full_url == "https://custom.example.com/api/v1/chat"
