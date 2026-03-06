"""Lightweight HTTP health server for K8s probes."""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Dict

log = logging.getLogger(__name__)

DEFAULT_HEALTH_PORT = 8081


class HealthHandler(BaseHTTPRequestHandler):
    """Handles /healthz, /readyz, /startup probe requests."""

    checks: Dict[str, Callable[[], dict]]

    def do_GET(self):
        check_fn = self.checks.get(self.path)
        if check_fn is None:
            self.send_response(404)
            self.end_headers()
            return

        result = check_fn()
        status_code = 200 if result["ok"] else 503
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, format, *args):
        pass


def start_health_server(
    checks: Dict[str, Callable[[], dict]],
    port: int = DEFAULT_HEALTH_PORT,
) -> HTTPServer:
    """Start health server in a daemon thread.

    Args:
        checks: Map of path -> callable returning {"ok": bool, ...}
        port: Port to listen on

    Returns:
        The HTTPServer instance (for shutdown)
    """
    HealthHandler.checks = checks
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    log.info("Health server listening on port %d (endpoints: %s)", port, list(checks.keys()))
    return server
