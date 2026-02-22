#!/usr/bin/env python3
"""
Unit tests for visualization router focusing on testable components.

Tests cover:
1. Pydantic model validation (SubscriptionTarget, ActualSubscribedTarget)
2. Helper function (_resolve_user_identity_for_authorization)
3. HNP mitigation (_generate_sse_url, _strip_port, _is_host_allowed with SOLACE_AGENT_MESH_ALLOWED_HOSTS)
"""

import os
import pytest
from unittest.mock import MagicMock

# Import the router and related classes
from solace_agent_mesh.gateway.http_sse.routers.visualization import (
    SubscriptionTarget,
    ActualSubscribedTarget,
    _resolve_user_identity_for_authorization,
    _generate_sse_url,
    _strip_port,
    _is_host_allowed,
    _get_candidate_host,
    _parse_allowed_hosts,
)


class TestSubscriptionTarget:
    """Test SubscriptionTarget model validation."""

    def test_subscription_target_valid_types(self):
        """Test SubscriptionTarget with valid target types."""
        valid_types = [
            "my_a2a_messages",
            "current_namespace_a2a_messages", 
            "namespace_a2a_messages",
            "agent_a2a_messages"
        ]
        
        for target_type in valid_types:
            target = SubscriptionTarget(type=target_type, identifier="test_id")
            assert target.type == target_type
            assert target.identifier == "test_id"

    def test_subscription_target_optional_identifier(self):
        """Test SubscriptionTarget with optional identifier."""
        target = SubscriptionTarget(type="current_namespace_a2a_messages")
        assert target.type == "current_namespace_a2a_messages"
        assert target.identifier is None

    def test_actual_subscribed_target_with_status(self):
        """Test ActualSubscribedTarget includes status."""
        target = ActualSubscribedTarget(
            type="namespace_a2a_messages",
            identifier="test_namespace",
            status="subscribed"
        )
        assert target.type == "namespace_a2a_messages"
        assert target.identifier == "test_namespace"
        assert target.status == "subscribed"


class TestHelperFunctions:
    """Test helper functions for user identity resolution."""

    def test_resolve_user_identity_with_force_identity(self):
        """Test user identity resolution with force_identity in development mode."""
        mock_component = MagicMock()
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "force_user_identity": "dev-user"
        }.get(key, default))
        
        result = _resolve_user_identity_for_authorization(
            component=mock_component,
            raw_user_id="original-user"
        )
        
        assert result == "dev-user"

    def test_resolve_user_identity_no_auth_fallback(self):
        """Test user identity resolution falls back to 'sam_dev_user' when not required."""
        mock_component = MagicMock()
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "force_user_identity": None,
            "frontend_use_authorization": False
        }.get(key, default))
        
        result = _resolve_user_identity_for_authorization(
            component=mock_component,
            raw_user_id=None
        )
        
        assert result == "sam_dev_user"

    def test_resolve_user_identity_auth_required_no_user(self):
        """Test user identity resolution raises error when auth required but no user."""
        mock_component = MagicMock()
        mock_component.get_config = MagicMock(side_effect=lambda key, default=None: {
            "force_user_identity": None,
            "frontend_use_authorization": True
        }.get(key, default))
        
        with pytest.raises(ValueError) as exc_info:
            _resolve_user_identity_for_authorization(
                component=mock_component,
                raw_user_id=None
            )
        
        assert "authorization is required" in str(exc_info.value)

    def test_resolve_user_identity_passthrough(self):
        """Test user identity resolution passes through valid user."""
        mock_component = MagicMock()
        mock_component.get_config = MagicMock(return_value=None)
        
        result = _resolve_user_identity_for_authorization(
            component=mock_component,
            raw_user_id="user-123"
        )
        
        assert result == "user-123"


def _make_mock_request(
    hostname="localhost",
    scheme="http",
    x_forwarded_host=None,
    x_forwarded_proto=None,
    path="/api/v1/sse/viz/stream-1/events",
):
    """Build a minimal mock request for _generate_sse_url."""
    mock_url = MagicMock()
    mock_url.hostname = hostname
    mock_url.scheme = scheme

    def _replace(scheme=None, netloc=None):
        out = f"{scheme or 'http'}://{netloc or hostname}{path}"
        return out

    mock_base = MagicMock()
    mock_base.path = path
    mock_base.replace = _replace
    mock_base.__str__ = lambda s, _scheme=scheme, _hostname=hostname, _path=path: f"{_scheme}://{_hostname}{_path}"

    mock_request = MagicMock()
    mock_request.url = mock_url
    mock_request.headers.get = lambda k, default=None: {
        "x-forwarded-host": x_forwarded_host,
        "x-forwarded-proto": x_forwarded_proto,
    }.get(k.lower() if isinstance(k, str) else k, default)
    mock_request.url_for = lambda name, stream_id: mock_base
    return mock_request


class TestHNPMitigation:
    """Test Host header poisoning mitigation in _generate_sse_url."""

    def test_strip_port(self):
        assert _strip_port("example.com:443") == "example.com"
        assert _strip_port("example.com") == "example.com"
        assert _strip_port("[::1]:8080") == "[::1]"
        assert _strip_port("[::1]") == "[::1]"

    def test_parse_allowed_hosts_default(self):
        with _env_restore():
            os.environ.pop("SOLACE_AGENT_MESH_ALLOWED_HOSTS", None)
            assert _parse_allowed_hosts() == "*"

    def test_parse_allowed_hosts_list(self):
        with _env_restore():
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = "localhost, 127.0.0.1 "
            parsed = _parse_allowed_hosts()
            assert parsed != "*"
            assert "localhost" in parsed
            assert "127.0.0.1" in parsed

    def test_hnp_evil_host_without_allowlist_returns_full_url(self):
        """Without ALLOWED_HOSTS (default *), evil host appears in URL (no mitigation)."""
        with _env_restore():
            os.environ.pop("SOLACE_AGENT_MESH_ALLOWED_HOSTS", None)
            req = _make_mock_request(hostname="evil.example.com", x_forwarded_host="evil.example.com")
            result = _generate_sse_url(req, "stream-1")
            assert "evil.example.com" in result
            assert result.startswith("http")

    def test_hnp_evil_host_with_allowlist_returns_path_only(self):
        """With ALLOWED_HOSTS=localhost,127.0.0.1, evil host must not appear (path-only)."""
        with _env_restore():
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
            req = _make_mock_request(hostname="evil.example.com", x_forwarded_host="evil.example.com")
            result = _generate_sse_url(req, "stream-1")
            assert "evil.example.com" not in result
            assert result.startswith("/") and "stream-1" in result

    def test_hnp_allowed_host_returns_full_url(self):
        """With allowlist, allowed host gets full URL."""
        with _env_restore():
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
            req = _make_mock_request(hostname="localhost", x_forwarded_host="localhost")
            result = _generate_sse_url(req, "stream-1")
            assert "localhost" in result
            assert result.startswith("http")

    def test_hnp_forwarded_host_port_stripped_in_netloc(self):
        """forwarded_host with :443 should yield netloc without port (strip_port in replace)."""
        with _env_restore():
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = "example.com"
            req = _make_mock_request(
                hostname="example.com",
                x_forwarded_host="example.com:443",
                x_forwarded_proto="https",
            )
            result = _generate_sse_url(req, "stream-1")
            assert "https://example.com" in result
            assert ":443" not in result

    def test_safe_proto_fallback_to_request_scheme(self):
        """When no forwarded_proto, scheme should come from request.url.scheme (no downgrade)."""
        with _env_restore():
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = "localhost"
            req = _make_mock_request(hostname="localhost", scheme="https", x_forwarded_host=None, x_forwarded_proto=None)
            result = _generate_sse_url(req, "stream-1")
            assert result.startswith("https://")


class _env_restore:
    """Restore SOLACE_AGENT_MESH_ALLOWED_HOSTS after test."""

    def __init__(self):
        self._saved = os.environ.get("SOLACE_AGENT_MESH_ALLOWED_HOSTS")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._saved is not None:
            os.environ["SOLACE_AGENT_MESH_ALLOWED_HOSTS"] = self._saved
        else:
            os.environ.pop("SOLACE_AGENT_MESH_ALLOWED_HOSTS", None)
        return False