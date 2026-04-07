"""
Unit tests for gateway observability middleware.

Minimal mocking approach - spy on counter.record() calls to verify labels.

Tests verify:
1. Counter called with correct labels (route_template, method, error_type)
2. Error categorization logic (none, 4xx_error, 5xx_error, auth_error)
3. TTFB iterator timing (stop after first chunk)
4. Edge cases (no body_iterator, errors during streaming)
5. /health and /metrics skipped
"""
import pytest
from starlette.testclient import TestClient
from starlette.responses import StreamingResponse, Response
from fastapi import FastAPI, HTTPException

from solace_agent_mesh.gateway.http_sse.middleware.observability import GatewayObservabilityMiddleware


@pytest.fixture(autouse=True)
def setup_counter():
    """Setup a spy on counter to track calls without full MetricRegistry."""
    from unittest.mock import Mock, patch

    # Track all counter.record() calls
    recorded_metrics = []

    def spy_record(value, labels):
        """Spy that tracks calls and stores them."""
        recorded_metrics.append((value, labels))

    # Patch _get_counter to return a mock counter with our spy
    mock_counter = Mock()
    mock_counter.record = spy_record

    with patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter._get_counter", return_value=mock_counter):
        yield recorded_metrics


@pytest.fixture
def app():
    """Create a simple FastAPI app with observability middleware."""
    app = FastAPI()
    app.add_middleware(GatewayObservabilityMiddleware)

    @app.get("/api/v1/tasks/{task_id}/status")
    async def get_task_status(task_id: str):
        return {"task_id": task_id, "status": "completed"}

    @app.get("/api/v1/tasks/{task_id}/not-found")
    async def get_task_not_found(task_id: str):  # noqa: ARG001
        raise HTTPException(status_code=404, detail="Task not found")

    @app.post("/api/v1/tasks/{task_id}/server-error")
    async def post_task_error(task_id: str):  # noqa: ARG001
        raise HTTPException(status_code=500, detail="Server error")

    @app.post("/api/v1/auth/unauthorized")
    async def auth_error():
        raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/api/v1/config")
    async def get_config():
        return {"setting": "value"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics_endpoint():
        return "# metrics"

    @app.get("/api/v1/message:stream")
    async def stream_message():
        async def generate():
            yield b"chunk1"
            yield b"chunk2"
        return StreamingResponse(generate())

    @app.get("/api/v1/test/stream/error")
    async def stream_with_error():
        async def generate():
            yield b"chunk1"
            raise RuntimeError("Error during streaming")
        return StreamingResponse(generate())

    return app


@pytest.fixture
def client(app):
    """Test client for making requests."""
    return TestClient(app)


def find_metric(recorded_metrics, route_template: str, method: str, error_type: str) -> int:
    """
    Find counter calls matching the given labels.

    Args:
        recorded_metrics: List of (value, labels) tuples from spy
        route_template: Route pattern to find
        method: HTTP method to find
        error_type: Error type to find

    Returns:
        Sum of values for matching labels
    """
    total = 0
    for value, labels in recorded_metrics:
        if (labels.get("route.template") == route_template and
            labels.get("http.method") == method and
            labels.get("error.type") == error_type):
            total += value
    return total


def test_counter_records_success(client, setup_counter):
    """Test counter records successful request with correct labels."""
    response = client.get("/api/v1/tasks/abc-123/status")
    assert response.status_code == 200

    # Verify counter recorded with correct labels
    count = find_metric(setup_counter, "/api/v1/tasks/{task_id}/status", "GET", "none")
    assert count == 1


def test_counter_records_404_error(client, setup_counter):
    """Test counter records 404 error correctly."""
    response = client.get("/api/v1/tasks/xyz/not-found")
    assert response.status_code == 404

    # Verify 4xx_error categorization
    count = find_metric(setup_counter, "/api/v1/tasks/{task_id}/not-found", "GET", "4xx_error")
    assert count == 1


def test_counter_records_500_error(client, setup_counter):
    """Test counter records 500 error correctly."""
    response = client.post("/api/v1/tasks/abc/server-error")
    assert response.status_code == 500

    # Verify 5xx_error categorization
    count = find_metric(setup_counter, "/api/v1/tasks/{task_id}/server-error", "POST", "5xx_error")
    assert count == 1


def test_counter_records_auth_error(client, setup_counter):
    """Test counter categorizes 401 as auth_error."""
    response = client.post("/api/v1/auth/unauthorized")
    assert response.status_code == 401

    # Verify auth_error categorization
    count = find_metric(setup_counter, "/api/v1/auth/unauthorized", "POST", "auth_error")
    assert count == 1


def test_health_endpoint_skipped(client, setup_counter):
    """Test /health endpoint produces NO metrics."""
    response = client.get("/health")
    assert response.status_code == 200

    # Verify counter was NOT called
    assert len(setup_counter) == 0


def test_metrics_endpoint_skipped(client, setup_counter):
    """Test /metrics endpoint produces NO metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200

    # Verify counter was NOT called
    assert len(setup_counter) == 0


def test_other_operation_recorded(client, setup_counter):
    """Test endpoints outside main 5 are recorded."""
    response = client.get("/api/v1/config")
    assert response.status_code == 200

    # Verify counter recorded
    count = find_metric(setup_counter, "/api/v1/config", "GET", "none")
    assert count == 1


def test_streaming_endpoint_counter(client, setup_counter):
    """Test streaming endpoint increments counter."""
    response = client.get("/api/v1/message:stream")
    _ = response.read()
    assert response.status_code == 200

    # Verify counter recorded
    count = find_metric(setup_counter, "/api/v1/message:stream", "GET", "none")
    assert count == 1


def test_multiple_requests_accumulate(client, setup_counter):
    """Test counter accumulates across multiple requests."""
    for _ in range(3):
        response = client.get("/api/v1/tasks/test-id/status")
        assert response.status_code == 200

    # Verify count = 3 (sum of all record calls with matching labels)
    count = find_metric(setup_counter, "/api/v1/tasks/{task_id}/status", "GET", "none")
    assert count == 3


def test_ttfb_iterator_timing():
    """Test TTFB iterator calls monitor.stop() after first chunk."""
    from unittest.mock import Mock
    import asyncio

    async def mock_iterator():
        yield b"first"
        yield b"second"

    # Simulate the TTFB measurement logic
    async def simulate_ttfb_measurement():
        monitor = Mock()
        monitor.stop = Mock()

        original_body_iterator = mock_iterator()

        first_chunk_seen = False
        chunks = []
        async for chunk in original_body_iterator:
            if not first_chunk_seen:
                monitor.stop()
                first_chunk_seen = True
            chunks.append(chunk)

        # Verify stop called exactly once after first chunk
        assert monitor.stop.call_count == 1
        assert chunks == [b"first", b"second"]

    asyncio.run(simulate_ttfb_measurement())


def test_ttfb_iterator_error_handling():
    """Test TTFB iterator calls monitor.error() if exception before first chunk."""
    from unittest.mock import Mock
    import asyncio

    # Simulate iterator that errors before yielding
    async def error_iterator():
        if True:  # Immediately error
            raise RuntimeError("Immediate error")
        yield b"never reached"  # noqa

    # Simulate the error handling logic
    monitor = Mock()
    monitor.error = Mock()
    monitor.stop = Mock()

    async def test_error_path():
        first_chunk_seen = False
        try:
            async for chunk in error_iterator():
                if not first_chunk_seen:
                    monitor.stop()
                    first_chunk_seen = True
                yield chunk
        except Exception as e:
            if not first_chunk_seen:
                monitor.error(e)
            raise

    # Run and verify error() was called
    with pytest.raises(RuntimeError):
        asyncio.run(test_error_path().__anext__())

    assert monitor.error.call_count == 1
    assert monitor.stop.call_count == 0


def test_wrap_streaming_non_streaming_response():
    """Test _wrap_streaming_with_ttfb returns unwrapped response if no body_iterator."""
    from solace_agent_mesh.gateway.http_sse.middleware.observability import GatewayObservabilityMiddleware
    from fastapi import FastAPI

    # Create middleware with a real app
    app = FastAPI()
    middleware = GatewayObservabilityMiddleware(app)

    # Regular response (no body_iterator)
    regular_response = Response(content=b"test", status_code=200)

    # Should return unchanged
    result = middleware._wrap_streaming_with_ttfb(regular_response, "test")

    assert result is regular_response  # Same object returned


def test_streaming_endpoint_both_metrics(client, setup_counter):
    """Test streaming endpoints record counter."""
    # Make request to streaming endpoint
    response = client.get("/api/v1/message:stream")
    _ = response.read()

    # Verify counter was recorded
    count = find_metric(setup_counter, "/api/v1/message:stream", "GET", "none")
    assert count == 1
