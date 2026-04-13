"""Tests for MCP connector observability instrumentation.

Tests verify that outbound.request.duration metrics are recorded with
correct labels when MCP tool calls are executed.

Philosophy:
- Test behavior, not implementation details
- Minimize mocking — only mock MetricRegistry (the external boundary)
- Let real code execute (monitors, context managers)
- Verify observable outcomes (metrics recorded, labels correct)
"""

import pytest
from unittest.mock import Mock, patch

from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPTool,
)
from solace_agent_mesh.common.observability import McpRemoteMonitor


def _make_embed_tool():
    """Create an EmbedResolvingMCPTool with minimal mocks."""
    mock_original_tool = Mock()
    mock_original_tool.name = "test_mcp_tool"
    mock_original_tool._mcp_tool = Mock()
    mock_original_tool._mcp_tool.name = "test_mcp_tool"
    mock_original_tool._mcp_tool.auth_scheme = None
    mock_original_tool._mcp_tool.auth_credential = None
    mock_original_tool._mcp_session_manager = Mock()

    return EmbedResolvingMCPTool(
        original_mcp_tool=mock_original_tool,
        tool_config=None,
        credential_manager=None,
    )


def _make_tool_context():
    """Create a mock tool context."""
    mock_session = Mock()
    mock_session.user_id = "user123"
    mock_session.id = "session456"
    mock_tool_context = Mock()
    mock_tool_context.session = mock_session
    mock_tool_context.agent_name = "test-agent"
    return mock_tool_context


def _capture_metrics():
    """Set up MetricRegistry mock and return a list that captures recorded metrics."""
    recorded = []

    def capture_record(duration, labels):
        recorded.append({"duration": duration, "labels": dict(labels)})

    mock_recorder = Mock()
    mock_recorder.record = capture_record

    mock_registry = Mock()
    mock_registry.get_recorder.return_value = mock_recorder

    return recorded, mock_registry


def _find_metric(recorded, **expected_labels):
    """Find first metric matching all expected label values."""
    for m in recorded:
        if all(m["labels"].get(k) == v for k, v in expected_labels.items()):
            return m
    return None


@pytest.mark.asyncio
class TestMcpObservability:
    """Test outbound.request.duration metrics for MCP connector."""

    async def test_successful_call_records_metric(self):
        """Verify metric is recorded with correct labels on successful MCP call."""
        embed_tool = _make_embed_tool()
        tool_context = _make_tool_context()

        async def mock_tool_call():
            return {"result": "success"}

        recorded, mock_registry = _capture_metrics()
        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_reg_cls, patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_call"
        ), patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_success"
        ):
            mock_reg_cls.get_instance.return_value = mock_registry

            result = await embed_tool._execute_tool_with_audit_logs(
                mock_tool_call, tool_context
            )

        assert result == {"result": "success"}
        metric = _find_metric(
            recorded,
            **{
                "service.peer.name": "mcp_server",
                "operation.name": "call_tool",
            },
        )
        assert metric is not None, f"Expected metric not found in {recorded}"
        assert metric["labels"]["error.type"] == "none"
        assert metric["duration"] >= 0

    async def test_failed_call_records_error_metric(self):
        """Verify metric captures error.type when MCP call fails."""
        embed_tool = _make_embed_tool()
        tool_context = _make_tool_context()

        test_error = ValueError("MCP server error")

        async def mock_tool_call():
            raise test_error

        recorded, mock_registry = _capture_metrics()
        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_reg_cls, patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_call"
        ), patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_failure"
        ):
            mock_reg_cls.get_instance.return_value = mock_registry

            with pytest.raises(ValueError):
                await embed_tool._execute_tool_with_audit_logs(
                    mock_tool_call, tool_context
                )

        metric = _find_metric(
            recorded,
            **{
                "service.peer.name": "mcp_server",
                "operation.name": "call_tool",
            },
        )
        assert metric is not None, f"Expected metric not found in {recorded}"
        assert metric["labels"]["error.type"] == "ValueError"

    async def test_timeout_error_categorized(self):
        """Verify httpx.TimeoutException is categorized as 'timeout'."""
        embed_tool = _make_embed_tool()
        tool_context = _make_tool_context()

        try:
            import httpx

            test_error = httpx.ReadTimeout("request timed out")
        except ImportError:
            pytest.skip("httpx not available")

        async def mock_tool_call():
            raise test_error

        recorded, mock_registry = _capture_metrics()
        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_reg_cls, patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_call"
        ), patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_failure"
        ):
            mock_reg_cls.get_instance.return_value = mock_registry

            with pytest.raises(httpx.ReadTimeout):
                await embed_tool._execute_tool_with_audit_logs(
                    mock_tool_call, tool_context
                )

        metric = _find_metric(
            recorded,
            **{
                "service.peer.name": "mcp_server",
                "operation.name": "call_tool",
            },
        )
        assert metric is not None
        assert metric["labels"]["error.type"] == "timeout"


class TestMcpRemoteMonitorParseError:
    """Test error categorization for MCP-specific exceptions."""

    def test_timeout_error(self):
        assert McpRemoteMonitor.parse_error(TimeoutError("test")) == "timeout"

    def test_connection_error(self):
        assert McpRemoteMonitor.parse_error(ConnectionError("test")) == "connection_error"

    def test_httpx_timeout(self):
        try:
            import httpx

            assert McpRemoteMonitor.parse_error(httpx.ReadTimeout("test")) == "timeout"
        except ImportError:
            pytest.skip("httpx not available")

    def test_generic_error(self):
        assert McpRemoteMonitor.parse_error(ValueError("test")) == "ValueError"
