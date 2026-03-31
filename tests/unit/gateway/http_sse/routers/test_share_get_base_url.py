"""
Unit tests for get_base_url in the share router.

Verifies that the function correctly respects X-Forwarded-Proto and
X-Forwarded-Host headers set by reverse proxies / load balancers,
so that share URLs use https when the original client request was https.
"""

import pytest
from unittest.mock import MagicMock
from starlette.datastructures import URL, Headers

from solace_agent_mesh.gateway.http_sse.routers.share import get_base_url


def _make_request(
    scheme: str = "http",
    host_header: str | None = None,
    netloc: str = "localhost:8080",
    forwarded_proto: str | None = None,
    forwarded_host: str | None = None,
) -> MagicMock:
    """Build a minimal mock Request with the given headers and URL parts."""
    raw_headers: dict[str, str] = {}
    if host_header:
        raw_headers["host"] = host_header
    if forwarded_proto:
        raw_headers["x-forwarded-proto"] = forwarded_proto
    if forwarded_host:
        raw_headers["x-forwarded-host"] = forwarded_host

    request = MagicMock()
    request.headers = Headers(raw_headers)
    request.url = MagicMock()
    request.url.scheme = scheme
    request.url.netloc = netloc
    return request


class TestGetBaseUrl:
    """Tests for get_base_url proxy-header handling."""

    def test_plain_http_no_proxy_headers(self):
        """Without proxy headers, scheme and host come from the request."""
        req = _make_request(scheme="http", host_header="app.example.com", netloc="app.example.com")
        assert get_base_url(req) == "http://app.example.com"

    def test_x_forwarded_proto_overrides_scheme(self):
        """X-Forwarded-Proto should override the request scheme."""
        req = _make_request(
            scheme="http",
            host_header="app.example.com",
            forwarded_proto="https",
        )
        assert get_base_url(req) == "https://app.example.com"

    def test_x_forwarded_host_overrides_host(self):
        """X-Forwarded-Host should override the Host header."""
        req = _make_request(
            scheme="http",
            host_header="internal-service:8080",
            forwarded_host="app.example.com",
        )
        assert get_base_url(req) == "http://app.example.com"

    def test_both_forwarded_headers(self):
        """Both X-Forwarded-Proto and X-Forwarded-Host together."""
        req = _make_request(
            scheme="http",
            host_header="internal-service:8080",
            netloc="internal-service:8080",
            forwarded_proto="https",
            forwarded_host="app.example.com",
        )
        assert get_base_url(req) == "https://app.example.com"

    def test_falls_back_to_netloc_when_no_host_header(self):
        """When no Host header is present, falls back to URL netloc."""
        req = _make_request(scheme="http", netloc="localhost:8080")
        assert get_base_url(req) == "http://localhost:8080"

    def test_https_scheme_preserved_without_forwarded_headers(self):
        """Direct HTTPS (no proxy) should keep https scheme."""
        req = _make_request(scheme="https", host_header="secure.example.com")
        assert get_base_url(req) == "https://secure.example.com"
