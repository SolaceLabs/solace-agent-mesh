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
            # IPv4-mapped IPv6 (RFC 4291 §2.5.5.2). These route to the
            # embedded IPv4 destination on dual-stack hosts and must be
            # blocked, or `http://[::ffff:169.254.169.254]/` is a free pass
            # to cloud metadata.
            "::ffff:127.0.0.1",
            "::ffff:10.0.0.1",
            "::ffff:172.16.0.1",
            "::ffff:192.168.1.1",
            "::ffff:169.254.169.254",
            # Regression: a CIDR-only blocklist (which an earlier revision
            # of this PR shipped) missed each of these. is_private /
            # is_reserved catches them all.
            "0.0.0.0",  # routes to localhost on Linux
            "192.0.2.1",  # TEST-NET-1
            "198.18.0.1",  # benchmarking (RFC 2544)
            "203.0.113.1",  # TEST-NET-3
            "240.0.0.1",  # 240/4 reserved
            "255.255.255.255",  # limited broadcast
            "224.0.0.1",  # IPv4 multicast
        ],
    )
    def test_blocks_private_and_reserved(self, ip):
        with pytest.raises(BlockedIPError, match="blocked IP range"):
            check_ip_blocked(ip)

    @pytest.mark.parametrize("ip", ["127.0.0.1", "127.0.0.5", "0.0.0.0"])
    def test_allow_loopback_exempts_loopback(self, ip):
        # allow_loopback is the dev-mode escape hatch for localhost services.
        check_ip_blocked(ip, allow_loopback=True)

    @pytest.mark.parametrize(
        "ip",
        ["169.254.169.254", "10.0.0.1", "192.168.1.1", "172.16.0.1", "224.0.0.1"],
    )
    def test_allow_loopback_does_not_exempt_metadata_or_private(self, ip):
        # Critical: enabling allow_loopback must NOT silently disable
        # cloud-metadata / RFC1918 / multicast protection. This is the lesson
        # from the review pass that found the coarse on/off switch in
        # web_tools.py.
        with pytest.raises(BlockedIPError, match="blocked IP range"):
            check_ip_blocked(ip, allow_loopback=True)

    @pytest.mark.parametrize(
        "ip",
        ["::ffff:8.8.8.8", "::ffff:93.184.216.34"],
    )
    def test_allows_public_via_ipv4_mapped(self, ip):
        # Sanity check that the IPv4-mapped unwrap doesn't over-block
        # legitimately-public addresses.
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
        ), pytest.raises(BlockedIPError, match="blocked IP range"):
            await transport.handle_async_request(request)

    async def test_dns_failure_surfaces_as_httpx_connect_error(self):
        # web_request's retry loop catches httpx.RequestError; gaierror would
        # leak past it without this conversion.
        transport = SSRFSafeTransport()
        request = httpx.Request("GET", "http://nonexistent.invalid/")
        import socket as _socket

        with patch(
            "solace_agent_mesh.common.utils.ssrf.socket.getaddrinfo",
            side_effect=_socket.gaierror("DNS fail"),
        ), pytest.raises(httpx.ConnectError, match="Could not resolve hostname"):
            await transport.handle_async_request(request)

    async def test_redirect_hop_to_loopback_is_blocked(self):
        """A 302 to a loopback target must be refused at the redirect hop.

        With the fix, ``SSRFSafeTransport`` and ``_is_safe_url`` both call
        ``socket.getaddrinfo``, so the canonical end-to-end shape ("attacker
        host appears public, redirects to loopback") cannot be simulated by
        DNS-mocking alone — both layers see the same answer. To exercise the
        redirect-revalidation path in isolation, this test composes the SSRF
        check (with a fake DNS table) over an ``httpx.MockTransport`` that
        plays the 302 response.
        """

        def upstream(request: httpx.Request) -> httpx.Response:
            if request.url.host == "attacker.test":
                return httpx.Response(
                    302, headers={"Location": "http://127.0.0.1/secret"}
                )
            pytest.fail(
                f"Redirect hop should have been blocked before reaching {request.url}"
            )

        fake_dns = {"attacker.test": "93.184.216.34", "127.0.0.1": "127.0.0.1"}

        class _CheckThenDelegate(SSRFSafeTransport):
            def __init__(self, inner: httpx.MockTransport):
                super().__init__()
                self._inner = inner

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                check_ip_blocked(fake_dns[request.url.host])
                return await self._inner.handle_async_request(request)

        transport = _CheckThenDelegate(httpx.MockTransport(upstream))
        async with httpx.AsyncClient(
            transport=transport, follow_redirects=True
        ) as client:
            with pytest.raises(BlockedIPError, match="blocked IP range"):
                await client.get("http://attacker.test/")
