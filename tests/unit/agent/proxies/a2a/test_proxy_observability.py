"""Tests for A2A proxy observability instrumentation.

Tests verify that RemoteAgentProxyMonitor correctly classifies errors and
records metrics with proper labels, following the same testing philosophy
as test_artifact_observability.py:
- Test behavior, not implementation details
- Minimize mocking — only mock at true external boundaries (MetricRegistry)
- Let real code execute (monitors, context managers)
- Verify observable outcomes (metrics recorded, labels correct)
"""

import pytest
from typing import Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

from a2a.client import A2AClientHTTPError
from a2a.client.errors import A2AClientJSONRPCError
import httpx

from solace_ai_connector.common.observability import MonitorLatency
from solace_agent_mesh.common.observability import RemoteAgentProxyMonitor


def find_metric(
    recorded_metrics: List[Tuple[float, Dict[str, str]]],
    **expected_labels: str,
) -> Optional[Tuple[float, Dict[str, str]]]:
    """Find first metric matching all expected labels."""
    for duration, labels in recorded_metrics:
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            return duration, labels
    return None


@pytest.fixture
def metric_capture():
    """Set up metric capture via MetricRegistry mock. Returns recorded_metrics list."""
    recorded_metrics = []

    def capture_record(duration, labels):
        recorded_metrics.append((duration, labels))

    return recorded_metrics, capture_record


def _make_jsonrpc_error(code: int = -32000, message: str = "error"):
    """Create a mock A2AClientJSONRPCError."""
    mock_response = Mock()
    mock_response.error = Mock()
    mock_response.error.code = code
    mock_response.error.message = message
    mock_response.error.__str__ = Mock(return_value=f"code={code}, message={message}")
    return A2AClientJSONRPCError(mock_response)


class TestRemoteAgentProxyMonitorParseError:
    """Test that parse_error correctly classifies A2A-specific exceptions."""

    def test_a2a_http_401_returns_auth_error(self):
        exc = A2AClientHTTPError(401, "Unauthorized")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "auth_error"

    def test_a2a_http_403_returns_auth_error(self):
        exc = A2AClientHTTPError(403, "Forbidden")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "auth_error"

    def test_a2a_http_400_returns_4xx_error(self):
        exc = A2AClientHTTPError(400, "Bad Request")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "4xx_error"

    def test_a2a_http_404_returns_4xx_error(self):
        exc = A2AClientHTTPError(404, "Not Found")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "4xx_error"

    def test_a2a_http_500_returns_5xx_error(self):
        exc = A2AClientHTTPError(500, "Internal Server Error")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "5xx_error"

    def test_a2a_http_503_returns_5xx_error(self):
        exc = A2AClientHTTPError(503, "Service Unavailable")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "5xx_error"

    def test_a2a_jsonrpc_error_returns_jsonrpc_error(self):
        exc = _make_jsonrpc_error(code=-32000, message="Server error")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "jsonrpc_error"

    def test_connection_error_returns_connection_error(self):
        exc = ConnectionError("Connection refused")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "connection_error"

    def test_timeout_error_returns_timeout(self):
        exc = TimeoutError("timed out")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "timeout"

    def test_httpx_timeout_returns_timeout(self):
        exc = httpx.ReadTimeout("read timeout")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "timeout"

    def test_unknown_exception_returns_class_name(self):
        exc = RuntimeError("something unexpected")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "RuntimeError"

    def test_value_error_returns_validation_error(self):
        exc = ValueError("invalid config")
        assert RemoteAgentProxyMonitor.parse_error(exc) == "validation_error"


class TestRemoteAgentProxyMonitorFactory:
    """Test that factory method produces correctly configured MonitorInstance."""

    def test_create_returns_correct_monitor_type(self):
        instance = RemoteAgentProxyMonitor.create("TestAgent")
        assert instance.monitor_type == "operation.duration"

    def test_create_sets_component_type_label(self):
        instance = RemoteAgentProxyMonitor.create("TestAgent")
        assert instance.labels["type"] == "a2a_agent"

    def test_create_sets_agent_name_label(self):
        instance = RemoteAgentProxyMonitor.create("MyRemoteAgent")
        assert instance.labels["component.name"] == "MyRemoteAgent"

    def test_create_sets_operation_name_label(self):
        instance = RemoteAgentProxyMonitor.create("TestAgent")
        assert instance.labels["operation.name"] == "forward_request"

    def test_create_sets_error_parser(self):
        instance = RemoteAgentProxyMonitor.create("TestAgent")
        assert instance.error_parser is RemoteAgentProxyMonitor.parse_error


class TestRemoteAgentProxyMonitorIntegration:
    """End-to-end tests with MetricRegistry mock verifying metric recording."""

    def test_success_records_metric_with_none_error_type(self, metric_capture):
        """Manual start/stop should record metric with error.type='none'."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            monitor = MonitorLatency(
                RemoteAgentProxyMonitor.create("SuccessAgent")
            )
            monitor.start()
            # Simulate successful operation
            monitor.stop()

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "SuccessAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None, (
                f"Expected forward_request metric not found in {recorded_metrics}"
            )
            duration, labels = metric
            assert labels["error.type"] == "none"
            assert duration >= 0

    def test_error_records_metric_with_connection_error_type(self, metric_capture):
        """Manual start/error should record metric with correct error.type."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            monitor = MonitorLatency(
                RemoteAgentProxyMonitor.create("FailAgent")
            )
            monitor.start()
            monitor.error(ConnectionError("agent disconnected"))

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "FailAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None, (
                f"Expected forward_request metric not found in {recorded_metrics}"
            )
            duration, labels = metric
            assert labels["error.type"] == "connection_error"
            assert duration >= 0

    def test_error_records_metric_with_auth_error_type(self, metric_capture):
        """A2AClientHTTPError(401) should record error.type='auth_error'."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            monitor = MonitorLatency(
                RemoteAgentProxyMonitor.create("AuthFailAgent")
            )
            monitor.start()
            monitor.error(A2AClientHTTPError(401, "Unauthorized"))

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "AuthFailAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "auth_error"

    def test_context_manager_success(self, metric_capture):
        """Context manager should record success metric when no exception."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            with MonitorLatency(
                RemoteAgentProxyMonitor.create("CtxAgent")
            ):
                pass  # Simulate successful operation

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "CtxAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "none"

    def test_context_manager_exception(self, metric_capture):
        """Context manager should record error metric when exception is raised."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            with pytest.raises(A2AClientHTTPError):
                with MonitorLatency(
                    RemoteAgentProxyMonitor.create("ErrorCtxAgent")
                ):
                    raise A2AClientHTTPError(500, "Internal Server Error")

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "ErrorCtxAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "5xx_error"

    def test_jsonrpc_error_records_correct_type(self, metric_capture):
        """A2AClientJSONRPCError should record error.type='jsonrpc_error'."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            monitor = MonitorLatency(
                RemoteAgentProxyMonitor.create("RPCFailAgent")
            )
            monitor.start()
            monitor.error(_make_jsonrpc_error(-32000, "Server error"))

            metric = find_metric(
                recorded_metrics,
                **{
                    "component.name": "RPCFailAgent",
                    "operation.name": "forward_request",
                },
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "jsonrpc_error"
