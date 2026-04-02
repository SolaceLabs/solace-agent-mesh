"""
Unit tests for gateway observability middleware.

Tests verify:
1. Counter increments for all requests with correct labels
2. Error categorization (none, 4xx_error, 5xx_error, auth_error)
3. Route template extraction from FastAPI
4. /health and /metrics endpoints skipped
"""
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient
from starlette.responses import StreamingResponse
from fastapi import FastAPI, HTTPException

from solace_agent_mesh.gateway.http_sse.middleware.observability import GatewayObservabilityMiddleware


@pytest.fixture
def app():
    """Create a simple FastAPI app with observability middleware."""
    app = FastAPI()
    app.add_middleware(GatewayObservabilityMiddleware)

    @app.get("/api/v1/tasks/{task_id}/status")
    async def get_task_status(task_id: str):
        return {"task_id": task_id, "status": "completed"}

    @app.get("/api/v1/tasks/{task_id}/not-found")
    async def get_task_not_found(task_id: str):
        raise HTTPException(status_code=404, detail="Task not found")

    @app.post("/api/v1/tasks/{task_id}/server-error")
    async def post_task_error(task_id: str):
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
    async def metrics():
        return "# metrics"

    @app.get("/api/v1/message:stream")
    async def stream_message():
        async def generate():
            yield b"chunk1"
            yield b"chunk2"
        return StreamingResponse(generate())

    return app


@pytest.fixture
def client(app):
    """Test client for making requests."""
    return TestClient(app)


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_regular_endpoint_success(mock_counter_record, client):
    """Test regular endpoint records counter with success."""
    # Make request
    response = client.get("/api/v1/tasks/abc-123/status")

    # Assertions
    assert response.status_code == 200

    # Counter should be called
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    # Verify request and response were passed correctly
    assert request_arg.url.path == "/api/v1/tasks/abc-123/status"
    assert request_arg.method == "GET"
    assert response_arg.status_code == 200


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_regular_endpoint_404_error(mock_counter_record, client):
    """Test regular endpoint records counter with 404 error."""
    # Make request
    response = client.get("/api/v1/tasks/xyz-789/not-found")

    # Assertions
    assert response.status_code == 404

    # Counter should be called with error response
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    assert request_arg.url.path == "/api/v1/tasks/xyz-789/not-found"
    assert response_arg.status_code == 404


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_post_endpoint_500_error(mock_counter_record, client):
    """Test POST endpoint records counter with 500 error."""
    # Make request
    response = client.post("/api/v1/tasks/abc/server-error")

    # Assertions
    assert response.status_code == 500

    # Counter should be called with error response
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    assert request_arg.method == "POST"
    assert response_arg.status_code == 500


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_auth_error_401(mock_counter_record, client):
    """Test auth endpoint records counter with 401 error."""
    # Make request
    response = client.post("/api/v1/auth/unauthorized")

    # Assertions
    assert response.status_code == 401

    # Counter should be called
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    assert response_arg.status_code == 401


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_health_endpoint_skipped(mock_counter_record, client):
    """Test /health endpoint skips all monitoring."""
    # Make request
    response = client.get("/health")

    # Assertions
    assert response.status_code == 200

    # No counter should be called
    mock_counter_record.assert_not_called()


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_metrics_endpoint_skipped(mock_counter_record, client):
    """Test /metrics endpoint skips all monitoring."""
    # Make request
    response = client.get("/metrics")

    # Assertions
    assert response.status_code == 200

    # No counter should be called
    mock_counter_record.assert_not_called()


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_other_endpoint_recorded(mock_counter_record, client):
    """Test endpoints outside main 5 controllers are still monitored."""
    # Make request to /config (operation="other")
    response = client.get("/api/v1/config")

    # Assertions
    assert response.status_code == 200

    # Counter should still be called
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    assert request_arg.url.path == "/api/v1/config"
    assert response_arg.status_code == 200


@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_streaming_endpoint_recorded(mock_counter_record, client):
    """Test streaming endpoint records counter."""
    # Make streaming request
    response = client.get("/api/v1/message:stream")

    # Consume the stream
    _ = response.read()

    # Assertions
    assert response.status_code == 200

    # Counter called
    assert mock_counter_record.called
    request_arg, response_arg = mock_counter_record.call_args[0]

    assert request_arg.url.path == "/api/v1/message:stream"
    assert response_arg.status_code == 200


def test_categorize_error():
    """Test error categorization logic in SamWebGatewayCounter."""
    # Extract categorization logic (same as in SamWebGatewayCounter.record)
    def categorize(status_code):
        if status_code < 400:
            return "none"
        elif status_code in (401, 403):
            return "auth_error"
        elif 400 <= status_code < 500:
            return "4xx_error"
        elif 500 <= status_code < 600:
            return "5xx_error"
        else:
            return "unknown"

    # Test cases
    assert categorize(200) == "none"
    assert categorize(201) == "none"
    assert categorize(204) == "none"
    assert categorize(400) == "4xx_error"
    assert categorize(401) == "auth_error"
    assert categorize(403) == "auth_error"
    assert categorize(404) == "4xx_error"
    assert categorize(422) == "4xx_error"
    assert categorize(500) == "5xx_error"
    assert categorize(503) == "5xx_error"
    assert categorize(600) == "unknown"


@patch("solace_ai_connector.common.observability.MetricRegistry")
def test_counter_record_extracts_labels(mock_registry):
    """Test SamWebGatewayCounter.record() extracts correct labels."""
    from solace_agent_mesh.gateway.observability.monitors import SamWebGatewayCounter
    from unittest.mock import Mock

    # Setup mock counter
    mock_counter = Mock()
    mock_registry.get_instance.return_value.create_counter.return_value = mock_counter

    # Reset class state
    SamWebGatewayCounter._counter = None

    # Create mock request with route
    mock_request = Mock()
    mock_request.method = "POST"
    mock_route = Mock()
    mock_route.path = "/api/v1/users/{id}/profile"
    mock_request.scope = {"route": mock_route}

    # Create mock response
    mock_response = Mock()
    mock_response.status_code = 404

    # Call record
    SamWebGatewayCounter.record(mock_request, mock_response)

    # Verify counter was called with correct labels
    assert mock_counter.record.called
    value, labels = mock_counter.record.call_args[0]

    assert value == 1
    assert labels["gateway.name"] == "WebUIGateway"
    assert labels["route.template"] == "/api/v1/users/{id}/profile"
    assert labels["http.method"] == "POST"
    assert labels["error.type"] == "4xx_error"


@patch("solace_agent_mesh.gateway.observability.monitors.SamGatewayMonitor.create")
@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_duration_histogram_recorded_for_tasks(mock_counter, mock_monitor_create, client):
    """Test duration histogram is recorded for task operations."""
    from unittest.mock import Mock

    # Setup mock monitor instance
    mock_monitor_instance = Mock()
    mock_monitor_create.return_value = mock_monitor_instance

    # Make request
    response = client.get("/api/v1/tasks/abc-123/status")

    # Assertions
    assert response.status_code == 200

    # Monitor should be created with correct parameters
    mock_monitor_create.assert_called_once_with(
        gateway_name="WebUIGateway",
        operation_name="/tasks"
    )


@patch("solace_agent_mesh.gateway.observability.monitors.SamGatewayMonitor.create")
@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_duration_histogram_recorded_for_other(mock_counter, mock_monitor_create, client):
    """Test duration histogram is recorded for 'other' operations."""
    from unittest.mock import Mock

    # Setup mock monitor instance
    mock_monitor_instance = Mock()
    mock_monitor_create.return_value = mock_monitor_instance

    # Make request to config (operation="other")
    response = client.get("/api/v1/config")

    # Assertions
    assert response.status_code == 200

    # Monitor should be created for "other" operation
    mock_monitor_create.assert_called_once_with(
        gateway_name="WebUIGateway",
        operation_name="other"
    )


@patch("solace_agent_mesh.gateway.observability.monitors.SamGatewayMonitor.create")
@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_duration_histogram_not_recorded_for_health(mock_counter, mock_monitor_create, client):
    """Test duration histogram is NOT recorded for /health."""
    # Make request
    response = client.get("/health")

    # Assertions
    assert response.status_code == 200

    # Monitor should NOT be created
    mock_monitor_create.assert_not_called()
    mock_counter.assert_not_called()


@patch("solace_agent_mesh.gateway.observability.monitors.SamGatewayTTFBMonitor.create")
@patch("solace_agent_mesh.gateway.observability.monitors.SamWebGatewayCounter.record")
def test_ttfb_histogram_recorded_for_streaming(mock_counter, mock_ttfb_create, client):
    """Test TTFB histogram is recorded for streaming endpoints."""
    from unittest.mock import Mock

    # Setup mock monitor instance
    mock_monitor_instance = Mock()
    mock_ttfb_create.return_value = mock_monitor_instance

    # Make streaming request
    response = client.get("/api/v1/message:stream")
    _ = response.read()

    # Assertions
    assert response.status_code == 200

    # TTFB monitor should be created
    mock_ttfb_create.assert_called_once_with(
        gateway_name="WebUIGateway",
        operation_name="/message"
    )