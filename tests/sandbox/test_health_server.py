"""Tests for the sandbox health server."""

import json
import urllib.request
import urllib.error

import pytest

from solace_agent_mesh.sandbox.health_server import start_health_server


@pytest.fixture()
def health_server_with_checks():
    """Start a health server with configurable check results, yield helper, then shut down."""
    state = {"liveness": True, "readiness": True, "startup": True}

    def liveness():
        ok = state["liveness"]
        return {"ok": ok, "broker": "connected" if ok else "disconnected"}

    def readiness():
        ok = state["readiness"]
        return {"ok": ok, "broker": "connected", "tools": 3 if ok else 0}

    def startup():
        ok = state["startup"]
        return {"ok": ok, "startup_complete": ok, "tool_sync": "ok" if ok else "failed"}

    server = start_health_server(
        checks={"/healthz": liveness, "/readyz": readiness, "/startup": startup},
        port=0,
    )
    port = server.server_address[1]

    class Helper:
        def url(self, path: str) -> str:
            return f"http://127.0.0.1:{port}{path}"

        def set(self, **kwargs):
            state.update(kwargs)

    try:
        yield Helper()
    finally:
        server.shutdown()


class TestHealthServer:
    def test_healthz_returns_200_when_healthy(self, health_server_with_checks):
        h = health_server_with_checks
        resp = urllib.request.urlopen(h.url("/healthz"))
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body["ok"] is True
        assert body["broker"] == "connected"

    def test_healthz_returns_503_when_broker_disconnected(self, health_server_with_checks):
        h = health_server_with_checks
        h.set(liveness=False)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(h.url("/healthz"))
        assert exc_info.value.code == 503
        body = json.loads(exc_info.value.read())
        assert body["ok"] is False
        assert body["broker"] == "disconnected"

    def test_readyz_returns_200_when_ready(self, health_server_with_checks):
        h = health_server_with_checks
        resp = urllib.request.urlopen(h.url("/readyz"))
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body["ok"] is True
        assert body["tools"] == 3

    def test_readyz_returns_503_when_no_tools(self, health_server_with_checks):
        h = health_server_with_checks
        h.set(readiness=False)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(h.url("/readyz"))
        assert exc_info.value.code == 503
        body = json.loads(exc_info.value.read())
        assert body["ok"] is False
        assert body["tools"] == 0

    def test_startup_returns_200_when_complete(self, health_server_with_checks):
        h = health_server_with_checks
        resp = urllib.request.urlopen(h.url("/startup"))
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body["ok"] is True
        assert body["startup_complete"] is True
        assert body["tool_sync"] == "ok"

    def test_startup_returns_503_when_sync_failed(self, health_server_with_checks):
        h = health_server_with_checks
        h.set(startup=False)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(h.url("/startup"))
        assert exc_info.value.code == 503
        body = json.loads(exc_info.value.read())
        assert body["ok"] is False
        assert body["tool_sync"] == "failed"

    def test_unknown_path_returns_404(self, health_server_with_checks):
        h = health_server_with_checks
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(h.url("/foo"))
        assert exc_info.value.code == 404

    def test_response_is_json(self, health_server_with_checks):
        h = health_server_with_checks
        resp = urllib.request.urlopen(h.url("/healthz"))
        assert resp.headers.get("Content-Type") == "application/json"
        body = json.loads(resp.read())
        assert isinstance(body, dict)
