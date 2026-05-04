"""HTTP middleware that establishes a RequestContext per request.

Reads the inbound ``X-Request-ID`` header (validating and falling back to
a fresh UUID if absent or malformed), enters a ``RequestContext`` for the
duration of the call, and echoes the resolved id on the response. Every
log line emitted while serving the request — and every A2A message
published downstream — carries the id thanks to the LogRecord factory
and the publish helper.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from solace_agent_mesh.common.observability.request_context import (
    HEADER_NAME,
    RequestContext,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        with RequestContext.start(request.headers.get(HEADER_NAME)) as rc:
            response = await call_next(request)
            response.headers[HEADER_NAME] = rc.x_request_id
            return response