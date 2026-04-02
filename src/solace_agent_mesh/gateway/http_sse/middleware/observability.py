"""
Gateway observability middleware for monitoring HTTP requests.

This middleware automatically instruments HTTP requests to measure:
- Request duration (gateway.duration metric)
- Time-to-first-byte for streaming responses (gateway.ttfb.duration metric)
- Error rates by type (4xx_error, 5xx_error, auth_error, etc.)
- Operation-level performance (grouped by resource type)
- HTTP method distribution (GET, POST, PUT, DELETE, PATCH)

Only monitors user-facing, performance-critical endpoints to avoid metric explosion.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from solace_ai_connector.common.observability import MonitorLatency
from ...observability.monitors import SamGatewayMonitor, SamGatewayTTFBMonitor, SamWebGatewayCounter

log = logging.getLogger(__name__)


class GatewayObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware to instrument HTTP requests with observability metrics.

    Metrics emitted:
    1. gateway.duration (histogram): Request latency for all operations
       Labels: gateway.name, operation.name
       Cardinality: ~72 series (1 gateway * 6 operations * ~12 buckets)

    2. gateway.ttfb.duration (histogram): Time-to-first-byte for streaming endpoints
       Labels: gateway.name, operation.name
       Cardinality: ~24 series (1 gateway * 2 streaming operations * 12 buckets)

    3. gateway.requests (counter): Request counts per route with error breakdown
       Labels: gateway.name, route.template, http.method, error.type
       Cardinality: ~666 series (1 gateways * ~74 routes * 3 avg methods * ~3 error_types)

    Operation groups (collapsed by prefix):
    - task: /api/v1/tasks/*
    - message: /api/v1/message*
    - session: /api/v1/sessions/*
    - sse: /api/v1/sse/*
    - artifact: /api/v1/artifacts/*
    - other: Everything else (/api/v1/config, /api/v1/version, /api/v1/users/*, etc.)

    Measurement strategy:
    - **SSE endpoints**: Only TTFB (connection lifetime is indefinite)
    - **Streaming endpoints**: Duration (setup) + TTFB (first chunk)
    - **Regular endpoints**: Duration only
    - **All endpoints**: Request counter with route template

    Skipped endpoints (no monitoring): /health, /metrics
    """

    # Map path prefixes to operation names (grouped by resource type)
    # Only includes user-facing, performance-critical operations
    PATH_TO_OPERATION = {
        '/api/v1/tasks': '/tasks',
        '/api/v1/message': '/message',
        '/api/v1/sessions': '/sessions',
        '/api/v1/sse': '/sse',
        '/api/v1/artifacts': '/artifacts',
    }

    # Streaming endpoints that should measure TTFB
    STREAMING_PATHS = {
        '/api/v1/sse/subscribe',  # SSE event streaming
        '/api/v1/message:stream',  # Streaming message responses
    }

    async def dispatch(self, request: Request, call_next):
        """
        Intercept request, measure duration, and record metrics.

        Measurement strategy:
        - SSE endpoints: Only TTFB (connection stays open indefinitely)
        - Streaming endpoints: Both duration (setup) and TTFB (first chunk)
        - Regular endpoints: Only duration

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response from handler (possibly wrapped for TTFB measurement)
        """
        # Extract operation name from path
        operation_name = self._get_operation_name(request.url.path)

        if not operation_name:
            # No monitoring for health checks, static files, config endpoints
            return await call_next(request)

        is_streaming = self._is_streaming_endpoint(request.url.path)
        is_sse = operation_name == 'sse'

        # Branch 1: SSE endpoints - only measure TTFB
        if is_sse:
            response = await call_next(request)
            SamWebGatewayCounter.record(request, response)
            return self._wrap_streaming_with_ttfb(response, operation_name)

        # Branch 2: Non-SSE streaming endpoints - measure duration AND TTFB
        if is_streaming:
            # Measure duration (all requests, no error_type in histogram)
            monitor = MonitorLatency(SamGatewayMonitor.create(
                gateway_name="WebUIGateway",
                operation_name=operation_name
            ))
            monitor.start()
            response = await call_next(request)
            monitor.stop()

            SamWebGatewayCounter.record(request, response)
            return self._wrap_streaming_with_ttfb(response, operation_name)

        # Branch 3: Regular endpoints - measure duration
        monitor = MonitorLatency(SamGatewayMonitor.create(
            gateway_name="WebUIGateway",
            operation_name=operation_name
        ))
        monitor.start()
        response = await call_next(request)
        monitor.stop()

        SamWebGatewayCounter.record(request, response)
        return response

    def _get_operation_name(self, path: str) -> str | None:
        """
        Extract operation name from request path.

        Args:
            path: HTTP request path (e.g., "/api/v1/tasks/123/status")

        Returns:
            Operation name ("task", "session", "sse", "artifact", "message", "other") or None if should skip
        """
        # Skip health and metrics endpoints
        if path in ('/health', '/metrics'):
            return None

        # Check specific operations
        for prefix, operation in self.PATH_TO_OPERATION.items():
            if path.startswith(prefix):
                return operation

        # Everything else goes to "other"
        return "other"

    def _is_streaming_endpoint(self, path: str) -> bool:
        """
        Check if path is a streaming endpoint that should measure TTFB.

        Args:
            path: HTTP request path

        Returns:
            True if endpoint streams responses (SSE, message:stream)
        """
        for streaming_prefix in self.STREAMING_PATHS:
            if path.startswith(streaming_prefix):
                return True
        return False

    def _wrap_streaming_with_ttfb(self, response: Response, operation_name: str) -> Response:
        """
        Wrap a streaming response to measure time-to-first-byte.

        Uses MonitorLatency.start()/stop() to measure the time from now until
        the first chunk is yielded from the iterator.

        Args:
            response: Original streaming response
            operation_name: Operation name for metrics

        Returns:
            Response with TTFB-measuring iterator
        """
        # Only wrap if it has a body_iterator (duck typing for streaming responses)
        if not hasattr(response, 'body_iterator'):
            log.warning(f"Response has no body_iterator attribute, skipping TTFB measurement")
            return response

        monitor = MonitorLatency(
            SamGatewayTTFBMonitor.create(
                gateway_name="WebUIGateway",
                operation_name=operation_name
            )
        )
        monitor.start()

        # Wrap the body iterator to stop timing on first chunk
        original_body_iterator = response.body_iterator
        async def ttfb_measuring_iterator():
            """Iterator that stops TTFB measurement when first chunk arrives."""
            first_chunk_seen = False
            try:
                async for chunk in original_body_iterator:
                    if not first_chunk_seen:
                        # Stop TTFB measurement when first chunk arrives
                        monitor.stop()
                        first_chunk_seen = True
                    yield chunk
            except Exception as e:
                # If error occurs before first chunk, record error
                if not first_chunk_seen:
                    monitor.error(e)
                raise

        # Replace body iterator with TTFB-measuring version
        response.body_iterator = ttfb_measuring_iterator()

        return response
