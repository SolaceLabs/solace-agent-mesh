"""Request-scoped correlation id (x-request-id) propagation primitive.

Holds a single ContextVar; provides a context-manager API modeled on the
existing ObservabilityContext pattern. The token-based set/reset prevents
leakage between asyncio tasks and across exception boundaries.

The mechanism is consumed by:
- The wrapped LogRecord factory in request_context_logging.py (stamps the
  id on every LogRecord at construction time).
- The handler-level RequestContextLogFilter (safety-net normalization for
  records that bypassed the factory).
- The five propagation choke points (publish, agent receive, gateway loop,
  HTTP middleware, non-HTTP entry) — these will call .start() or
  .from_user_properties() when wiring is added.
"""
from __future__ import annotations

import contextlib
import contextvars
import re
import uuid
from typing import ContextManager, Optional

HEADER_NAME = "X-Request-ID"
WIRE_KEY = "xRequestId"
LOG_FIELD = "x_request_id"
MISSING_VALUE = "-"
MAX_LENGTH = 128

_VALID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_X_REQUEST_ID_VAR: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "x_request_id", default=None
)


def _validate_or_generate(candidate: Optional[str]) -> str:
    if candidate and isinstance(candidate, str) and _VALID.match(candidate):
        return candidate
    return uuid.uuid4().hex


class RequestContext:
    """Context manager that enters/exits an x-request-id binding.

    Use one of the factories rather than the constructor:
      - RequestContext.start(maybe_id)         — for external entry points
      - RequestContext.from_user_properties(up) — for broker receivers
    """

    def __init__(self, x_request_id: str):
        self.x_request_id = x_request_id
        self._token: Optional[contextvars.Token] = None

    @classmethod
    def start(cls, x_request_id: Optional[str] = None) -> "RequestContext":
        return cls(_validate_or_generate(x_request_id))

    @classmethod
    def from_user_properties(
        cls, user_properties: Optional[dict]
    ) -> ContextManager:
        """Returns a context manager that enters a RequestContext only if
        the inbound user_properties carry a valid xRequestId. Otherwise
        returns a no-op context manager — leaving `current()` untouched.

        This is intentional: at broker receive points, only user-initiated
        traffic carries an upstream id. Internal/discovery/health-check
        messages legitimately have no id, and minting a synthetic one
        here would create meaningless ids that pollute search space.
        Logs emitted during such events keep the `-` placeholder.

        Use `RequestContext.start(...)` at *external* entry boundaries
        (HTTP middleware, scheduler fire, plugin gateway handler) where
        a fresh id is appropriate.
        """
        candidate = (user_properties or {}).get(WIRE_KEY)
        if candidate and isinstance(candidate, str) and _VALID.match(candidate):
            return cls(candidate)
        return contextlib.nullcontext()

    @classmethod
    def current(cls) -> Optional[str]:
        return _X_REQUEST_ID_VAR.get()

    def __enter__(self) -> "RequestContext":
        self._token = _X_REQUEST_ID_VAR.set(self.x_request_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._token is not None:
            _X_REQUEST_ID_VAR.reset(self._token)
            self._token = None
        return False


def append_x_request_id(message: str) -> str:
    """Append the active x-request-id to a user-facing message.

    For chat-only gateways (Teams, Slack, future plugins) the bot's reply
    is the only customer-visible surface. When something goes wrong, the
    user has nothing to quote unless we put the id into the error message
    itself. Use this helper at every customer-facing error-reply site so
    the format stays consistent across plugins:

        await turn_context.send_activity(
            append_x_request_id("Sorry, I encountered an error...")
        )

    Returns the message unchanged when no context is active.
    """
    rid = RequestContext.current()
    if not rid:
        return message
    return f"{message}\nx-request-id: {rid}"