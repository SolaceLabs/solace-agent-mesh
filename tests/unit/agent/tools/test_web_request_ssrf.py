"""Regression tests for the SSRF redirect-revalidation bypass in web_request.

Disclosed by tonghuaroot: `_is_safe_url` validated only the initially-submitted
URL, then `httpx.AsyncClient(follow_redirects=True)` followed any 302 without
re-checking. An attacker-controlled public host returning a redirect to a
loopback / metadata address could exfiltrate internal-only content.

The fix installs an SSRF-safe httpx transport that re-validates the destination
IP at every connection (initial request and each redirect hop).
"""

import http.server
import socketserver
import threading
from typing import Optional
from unittest.mock import patch

import pytest

from solace_agent_mesh.agent.tools import web_tools


class _Ctx:
    state: dict = {}
    _invocation_context = None


class _RedirectToLoopback(http.server.BaseHTTPRequestHandler):
    redirect_to = ""

    def do_GET(self):  # noqa: N802 - http.server API
        self.send_response(302)
        self.send_header("Location", self.redirect_to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_):  # silence test output
        pass


@pytest.fixture
def redirector():
    """Spawns a localhost listener that 302s to a configurable URL."""
    socketserver.TCPServer.allow_reuse_address = True
    server: Optional[socketserver.TCPServer] = None

    def _start(redirect_to: str) -> int:
        nonlocal server
        _RedirectToLoopback.redirect_to = redirect_to
        server = socketserver.TCPServer(("127.0.0.1", 0), _RedirectToLoopback)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server.server_address[1]

    yield _start

    if server is not None:
        server.shutdown()
        server.server_close()


async def test_transport_blocks_loopback_when_preflight_bypassed(redirector):
    """Defense-in-depth: if the pre-flight check is bypassed, the transport
    still refuses to connect to a loopback target.

    With the fix, the initial connection itself goes through
    SSRFSafeTransport, so the 302 listener is never reached. This test proves
    the transport is authoritative; ``test_redirect_hop_to_loopback_is_blocked``
    (in ``tests/unit/common/test_ssrf.py``) exercises the redirect-revalidation
    path directly.
    """
    port = redirector("http://127.0.0.1:9/should-not-be-reached")

    with patch.object(web_tools, "_is_safe_url", return_value=True):
        result = await web_tools.web_request(
            url=f"http://127.0.0.1:{port}/", tool_context=_Ctx()
        )

    assert result.status == "error"
    assert "not safe" in result.message.lower()
    assert not result.data_objects


async def test_direct_loopback_request_is_blocked():
    """Pre-flight rejects direct loopback requests without opening a connection."""
    result = await web_tools.web_request(
        url="http://127.0.0.1:9/", tool_context=_Ctx()
    )
    assert result.status == "error"
    assert result.message == "URL is not safe to request."


async def test_metadata_endpoint_is_blocked():
    """Cloud metadata endpoint is blocked by the pre-flight check."""
    result = await web_tools.web_request(
        url="http://169.254.169.254/latest/meta-data/", tool_context=_Ctx()
    )
    assert result.status == "error"
    assert result.message == "URL is not safe to request."


async def test_allow_loopback_bypasses_transport(redirector):
    """The `allow_loopback` test-only knob disables both pre-flight and transport."""
    # Listener that simply returns 200 with a marker body.
    class _OK(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), _OK)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = await web_tools.web_request(
            url=f"http://127.0.0.1:{port}/",
            tool_context=_Ctx(),
            tool_config={"allow_loopback": True},
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.status == "success"
