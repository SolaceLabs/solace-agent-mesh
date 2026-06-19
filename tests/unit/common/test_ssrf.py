"""Tests for the shared SSRF protection helpers."""

from unittest.mock import patch

import httpx
import pytest

from solace_agent_mesh.common.utils.ssrf import (
    BlockedIPError,
    SSRFSafeTransport,
    check_ip_blocked,
)


class TestCheckIPBlocked:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "::1",
            "fc00::1",
            "fe80::1",
        ],
    )
    def test_blocks_private_and_reserved(self, ip):
        with pytest.raises(BlockedIPError, match="blocked IP range"):
            check_ip_blocked(ip)

    @pytest.mark.parametrize("ip", ["8.8.8.8", "93.184.216.34"])
    def test_allows_public(self, ip):
        check_ip_blocked(ip)

    def test_blocked_ip_error_is_value_error(self):
        # Callers in webhook validation rely on `pytest.raises(ValueError)` semantics.
        with pytest.raises(ValueError):
            check_ip_blocked("127.0.0.1")


class TestSSRFSafeTransport:
    """Connection-time enforcement closes the redirect-revalidation gap."""

    async def test_blocks_loopback_at_connect_time(self):
        transport = SSRFSafeTransport()
        request = httpx.Request("GET", "http://127.0.0.1/")
        with pytest.raises(BlockedIPError, match="blocked IP range"):
            await transport.handle_async_request(request)

    async def test_blocks_metadata_endpoint(self):
        transport = SSRFSafeTransport()
        request = httpx.Request("GET", "http://169.254.169.254/latest/meta-data/")
        with pytest.raises(BlockedIPError, match="blocked IP range"):
            await transport.handle_async_request(request)

    async def test_blocks_when_dns_resolves_to_private_ip(self):
        # Simulates DNS rebinding: the hostname appears innocuous but
        # `getaddrinfo` returns an RFC1918 address at connect time.
        transport = SSRFSafeTransport()
        request = httpx.Request("GET", "http://attacker.test/")
        with patch(
            "solace_agent_mesh.common.utils.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.1.2.3", 80))],
        ):
            with pytest.raises(BlockedIPError, match="blocked IP range"):
                await transport.handle_async_request(request)
