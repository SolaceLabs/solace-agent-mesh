"""
SAM-specific observability monitors.

Provides type-safe monitor classes for instrumenting SAM agents and tools.
These extend solace_ai_connector's OperationMonitor with constrained APIs
to prevent accidental metric explosion.
"""

from solace_ai_connector.common.observability.monitors.base import MonitorInstance
from solace_ai_connector.common.observability.monitors.operation import OperationMonitor
from solace_ai_connector.common.observability.monitors.remote import (
    RemoteRequestMonitor,
)


class AgentMonitor(OperationMonitor):
    """
    Type-safe monitor for agent execution duration.

    Inherits from OperationMonitor but constrains the API to prevent metric explosion.
    Automatically sets type="agent" and operation.name="execute".

    Maps to: operation.duration histogram
    Labels: type="agent", component.name=<agent_name>, operation.name="execute", error.type

    Usage:
        from solace_agent_mesh.common.observability import AgentMonitor
        from solace_ai_connector.common.observability import MonitorLatency

        monitor = MonitorLatency(AgentMonitor.create(name="ResearchAgent"))
        with monitor:
            # agent execution code
    """

    @classmethod
    def create(cls, name: str) -> MonitorInstance:
        """
        Create agent monitor instance.

        Args:
            name: The agent name (e.g., "ResearchAgent", "WebAgent")

        Returns:
            MonitorInstance configured for agent execution tracking
        """
        return super().create(
            component_type="agent",
            component_name=name,
            operation="execute"
        )


class ToolMonitor(OperationMonitor):
    """
    Type-safe monitor for tool execution duration (aggregated across all agents).

    Inherits from OperationMonitor but constrains the API to prevent metric explosion.
    Automatically sets type="tool" and operation.name="execute".

    Maps to: operation.duration histogram
    Labels: type="tool", component.name=<tool_name>, operation.name="execute", error.type

    Usage:
        from solace_agent_mesh.common.observability import ToolMonitor
        from solace_ai_connector.common.observability import MonitorLatency

        monitor = MonitorLatency(ToolMonitor.create(name="web_search"))
        with monitor:
            # tool execution code
    """

    @classmethod
    def create(cls, name: str) -> MonitorInstance:
        """
        Create tool monitor instance.

        Args:
            name: The tool name (e.g., "web_search", "deep_research", "query_data_with_sql")

        Returns:
            MonitorInstance configured for tool execution tracking (aggregated across agents)
        """
        return super().create(
            component_type="tool",
            component_name=name,
            operation="execute"
        )


class McpRemoteMonitor(RemoteRequestMonitor):
    """Monitor for outbound MCP server calls.

    Maps to: outbound.request.duration histogram
    Labels: service.peer.name="mcp_server", operation.name, error.type
    """

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Map MCP/httpx-specific exceptions to error categories."""
        try:
            import httpx

            if isinstance(exc, httpx.TimeoutException):
                return "timeout"
        except ImportError:
            pass
        return RemoteRequestMonitor.parse_error(exc)

    @classmethod
    def call_tool(cls) -> MonitorInstance:
        """Create monitor instance for MCP tool call execution."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "service.peer.name": "mcp_server",
                "operation.name": "call_tool",
            },
            error_parser=cls.parse_error,
        )