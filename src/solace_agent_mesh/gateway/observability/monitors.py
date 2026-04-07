"""Concrete monitor implementations for SAM gateway operations."""

import threading

from starlette.requests import Request
from starlette.responses import Response

from solace_ai_connector.common.observability.monitors.base import MonitorInstance
from solace_ai_connector.common.observability.monitors.gateway import (
    GatewayMonitor,
    GatewayTTFBMonitor,
)


class SamGatewayMonitor(GatewayMonitor):
    """
    Concrete monitor for SAM gateway request duration.

    Maps to: gateway.duration histogram
    Labels: gateway.name, operation.name, error.type

    Usage:
        monitor = SamGatewayMonitor.create(
            gateway_name="WebUIBackend",
            operation_name="task"
        )
        async with MonitorLatency(monitor):
            # ... operation code ...
    """

    @classmethod
    def create(cls, gateway_name: str, operation_name: str) -> MonitorInstance:
        """
        Factory method to create a gateway monitor instance.

        Args:
            gateway_name: Name of the gateway (e.g., "WebUIBackend", "GenericGateway")
            operation_name: Grouped operation name to control cardinality:
                - "task": All task operations (submit, cancel, get status, search)
                - "session": All session operations (list, get, create, update, delete)
                - "sse": SSE connection and streaming operations
                - "artifact": All artifact operations (upload, download, list, delete)
                - "message": Message submission endpoints (send, stream)
                - "handle_external_input": Generic gateway external request handling
                - "send_update": Generic gateway update delivery
        Returns:
            MonitorInstance with gateway.name, operation.name, and error.type labels
        """
        labels = {
            "gateway.name": gateway_name,
            "operation.name": operation_name,
            "error.type": "none",  # Default, updated on error
        }

        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels=labels,
            error_parser=cls.parse_error,
        )

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """
        Categorize exceptions into error types for observability.

        Maps exceptions to error.type label values:
        - "4xx_error": HTTP 4xx client errors
        - "5xx_error": HTTP 5xx server errors
        - "auth_error": Permission/authorization errors
        - "client_error": ValueError, TypeError, KeyError (invalid input)
        - "server_error": RuntimeError, OSError (server-side failures)
        - Exception class name: Fallback for uncategorized errors

        Args:
            exc: Exception to categorize

        Returns:
            Error type string for error.type label
        """
        # Check for HTTP status code-based errors (FastAPI HTTPException)
        if hasattr(exc, "status_code"):
            code = exc.status_code
            if 400 <= code < 500:
                # Special case for auth errors
                if code in (401, 403):
                    return "auth_error"
                return "4xx_error"
            if 500 <= code < 600:
                return "5xx_error"
            return f"http_{code}"

        # Check for permission errors
        if isinstance(exc, PermissionError):
            return "auth_error"

        # Fallback to base class categorization
        # (ValueError/TypeError/KeyError → client_error, RuntimeError/OSError → server_error)
        return GatewayMonitor.parse_error(exc)


class SamGatewayTTFBMonitor(GatewayTTFBMonitor):
    """
    Concrete monitor for SAM gateway Time-To-First-Byte duration.

    Maps to: gateway.ttfb.duration histogram
    Labels: gateway.name, operation.name

    Usage:
        monitor = SamGatewayTTFBMonitor.create(
            gateway_name="WebUIBackend",
            operation_name="sse"
        )
        async def event_generator():
            async with MonitorLatency(monitor):
                yield first_event
            # TTFB measurement ends here
            # ... continue streaming ...
    """

    @classmethod
    def create(cls, gateway_name: str, operation_name: str) -> MonitorInstance:
        """
        Factory method to create a TTFB monitor instance.

        Args:
            gateway_name: Name of the gateway (e.g., "WebUIBackend", "GenericGateway")
            operation_name: Grouped operation name (see SamGatewayMonitor.create for values)

        Returns:
            MonitorInstance with gateway.name and operation.name labels
        """
        labels = {
            "gateway.name": gateway_name,
            "operation.name": operation_name,
        }

        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels=labels,
            error_parser=cls.parse_error,
        )

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Same error categorization as SamGatewayMonitor."""
        return SamGatewayMonitor.parse_error(exc)


class SamWebGatewayCounter:
    """
    Counter for WebUI gateway HTTP request counts by route, method, and error type.

    Maps to: gateway.requests counter
    Labels: gateway.name, route.template, http.method, error.type

    Usage:
        from starlette.requests import Request
        from starlette.responses import Response

        SamWebGatewayCounter.record(request, response)
    """

    _counter = None
    _lock = threading.Lock()

    @classmethod
    def _get_counter(cls):
        """Lazy initialization of counter (thread-safe)."""
        if cls._counter is None:  # Fast path check (avoid lock overhead)
            with cls._lock:  # Double-checked locking
                if cls._counter is None:  # Recheck inside lock
                    from solace_ai_connector.common.observability import MetricRegistry
                    registry = MetricRegistry.get_instance()
                    cls._counter = registry.create_counter(
                        name="gateway.requests",
                        description="Total gateway requests by route, method, and error type"
                    )
        return cls._counter

    @classmethod
    def record(cls, request: Request, response: Response) -> None:
        """
        Record a gateway request with automatic label extraction.

        Args:
            request: Starlette Request object
            response: Starlette Response object
        """
        # Extract route template from FastAPI
        route = request.scope.get("route")
        route_template = route.path if route and hasattr(route, "path") else "unknown"

        # Categorize error type from status code
        status_code = response.status_code
        if status_code < 400:
            error_type = "none"
        elif status_code in (401, 403):
            error_type = "auth_error"
        elif 400 <= status_code < 500:
            error_type = "4xx_error"
        elif 500 <= status_code < 600:
            error_type = "5xx_error"
        else:
            error_type = "unknown"

        counter = cls._get_counter()

        labels = {
            "gateway.name": "WebUIGateway",
            "route.template": route_template,
            "http.method": request.method,
            "error.type": error_type,
        }

        counter.record(1, labels)
