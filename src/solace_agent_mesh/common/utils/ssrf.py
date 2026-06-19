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


def check_ip_blocked(ip_str: str, *, allow_loopback: bool = False) -> None:
    """Raise :class:`BlockedIPError` if ``ip_str`` falls within a blocked range.

    The primary gate is the ``ipaddress`` predicate
    ``is_private | is_reserved | is_loopback | is_link_local | is_multicast |
    is_unspecified`` — strictly broader than any hand-maintained CIDR list,
    and tracks the IANA special-purpose registries that CPython ships with.
    The explicit ``_BLOCKED_IP_NETWORKS`` runs as a second check so the
    minimum guaranteed coverage doesn't drift if a future Python release
    narrows a predicate.

    Why the predicate matters here: a CIDR-only check (which an earlier
    revision of this PR shipped) misses ``0.0.0.0`` (routes to localhost on
    Linux), the TEST-NET / benchmarking / 240/4 reserved ranges, and the
    255.255.255.255 broadcast — every one of which ``is_private`` covers.

    IPv4-mapped IPv6 literals (``::ffff:a.b.c.d``, RFC 4291 §2.5.5.2) route
    to the underlying IPv4 destination on dual-stack hosts. Without
    unwrapping, ``http://[::ffff:169.254.169.254]/`` would slip past the
    IPv4 checks because cross-family membership and predicate evaluation
    don't see the embedded address.

    ``allow_loopback`` is a test-only escape hatch. When true, it exempts
    *only* loopback addresses (127.0.0.0/8, ::1/128, and 0.0.0.0 which
    routes to localhost on Linux). RFC1918, cloud metadata
    (169.254.169.254), link-local, multicast, and redirect re-validation
    all remain in force — so enabling it to talk to a localhost dev
    service doesn't silently disable the rest of the SSRF guarantee.
    """
    ip = ipaddress.ip_address(ip_str)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if allow_loopback and (ip.is_loopback or ip.is_unspecified):
        return

    if (
        ip.is_private
        or ip.is_reserved
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise BlockedIPError(
            f"URL resolves to blocked IP range ({ip}). "
            "Private, loopback, and link-local addresses are not allowed."
        )

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

    ``allow_loopback`` is forwarded to :func:`check_ip_blocked` so a test-mode
    knob exempts only loopback addresses; RFC1918, cloud metadata, IPv6 ULA,
    and redirect re-validation remain in force. Always install this transport
    instead of dropping it for the loopback case — that's the lesson from
    review: a coarse on/off switch would silently disable the entire guard.
    """

    def __init__(self, *args, allow_loopback: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._allow_loopback = allow_loopback

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
            check_ip_blocked(sockaddr[0], allow_loopback=self._allow_loopback)
        return await super().handle_async_request(request)
