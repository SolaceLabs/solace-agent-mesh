"""Shared SSRF protection helpers.

Provides an httpx transport and IP-block predicate that prevent outbound
requests from reaching loopback, private, or link-local addresses (including
cloud metadata endpoints).

Validation is enforced inside the transport — not only on a pre-flight URL
check — so HTTP redirects are re-validated on every hop and DNS rebinding
(resolution changing between the safety check and the actual connection)
cannot bypass the guard.
"""

import asyncio
import ipaddress
import socket

import httpx

_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),  # Private
    ipaddress.ip_network("172.16.0.0/12"),  # Private
    ipaddress.ip_network("192.168.0.0/16"),  # Private
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / cloud metadata
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


class BlockedIPError(ValueError):
    """Raised when a destination resolves to a blocked IP range."""


def check_ip_blocked(ip_str: str) -> None:
    """Raise :class:`BlockedIPError` if ``ip_str`` falls within a blocked range.

    IPv4-mapped IPv6 literals (``::ffff:a.b.c.d``, RFC 4291 §2.5.5.2) route to
    the underlying IPv4 destination on dual-stack hosts. Without unwrapping,
    ``http://[::ffff:127.0.0.1]/`` and ``http://[::ffff:169.254.169.254]/``
    bypass the IPv4 blocklist because membership comparisons across address
    families always return False. Unwrap the mapped form so the IPv4
    blocklist applies.
    """
    ip = ipaddress.ip_address(ip_str)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    for network in _BLOCKED_IP_NETWORKS:
        if ip in network:
            raise BlockedIPError(
                f"URL resolves to blocked IP range ({ip}). "
                "Private, loopback, and link-local addresses are not allowed."
            )


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    """Async transport that enforces the IP blocklist at connection time.

    Every request — including each redirect hop followed by httpx — passes
    through ``handle_async_request``, so the blocklist applies uniformly.
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        try:
            # socket.getaddrinfo is a blocking syscall; run it in a worker
            # thread so a slow resolver doesn't stall the event loop for every
            # other in-flight coroutine.
            addrinfos = await asyncio.to_thread(socket.getaddrinfo, hostname, port)
        except socket.gaierror as exc:
            # Match httpx's own behavior so callers' httpx.RequestError handlers
            # (including web_request's retry loop) treat DNS failures uniformly.
            raise httpx.ConnectError(
                f"Could not resolve hostname: {hostname}", request=request
            ) from exc
        for *_, sockaddr in addrinfos:
            check_ip_blocked(sockaddr[0])
        return await super().handle_async_request(request)
