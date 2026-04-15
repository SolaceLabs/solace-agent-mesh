"""
SAM-specific observability monitors.

Provides type-safe monitor classes for instrumenting SAM agents and tools.
These extend solace_ai_connector's OperationMonitor with constrained APIs
to prevent accidental metric explosion.
"""

from solace_ai_connector.common.observability.monitors.operation import OperationMonitor
from solace_ai_connector.common.observability.monitors.base import MonitorInstance


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


class RemoteAgentProxyMonitor(OperationMonitor):
    """
    Type-safe monitor for A2A proxy request duration.

    Inherits from OperationMonitor but constrains the API to prevent metric explosion.
    Automatically sets type="a2a_agent" and operation.name="forward_request".

    Maps to: operation.duration histogram
    Labels: type="a2a_agent", component.name=<agent_name>, operation.name="forward_request", error.type

    Usage:
        from solace_agent_mesh.common.observability import RemoteAgentProxyMonitor
        from solace_ai_connector.common.observability import MonitorLatency

        monitor = MonitorLatency(RemoteAgentProxyMonitor.create("MyAgent"))
        monitor.start()
        try:
            # ... forwarding logic ...
            monitor.stop()
        except Exception as e:
            monitor.error(e)
            raise
    """

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """
        Categorize A2A proxy exceptions into error types for observability.

        Maps exceptions to error.type label values:
        - "auth_error": A2AClientHTTPError with status 401 or 403
        - "4xx_error": A2AClientHTTPError with other 4xx status
        - "5xx_error": A2AClientHTTPError with 5xx status
        - "jsonrpc_error": A2AClientJSONRPCError (protocol-level errors)
        - "timeout": httpx.TimeoutException or built-in TimeoutError
        - "connection_error": ConnectionError
        - Exception class name: Fallback for uncategorized errors
        """
        try:
            from a2a.client import A2AClientHTTPError

            if isinstance(exc, A2AClientHTTPError):
                code = exc.status_code
                if code in (401, 403):
                    return "auth_error"
                if 400 <= code < 500:
                    return "4xx_error"
                if 500 <= code < 600:
                    return "5xx_error"
                return f"http_{code}"
        except ImportError:
            pass

        try:
            from a2a.client.errors import A2AClientJSONRPCError

            if isinstance(exc, A2AClientJSONRPCError):
                return "jsonrpc_error"
        except ImportError:
            pass

        try:
            import httpx

            if isinstance(exc, httpx.TimeoutException):
                return "timeout"
        except ImportError:
            pass

        if isinstance(exc, ConnectionError):
            return "connection_error"

        return OperationMonitor.parse_error(exc)

    @classmethod
    def create(cls, name: str) -> MonitorInstance:
        """
        Create monitor instance for a forward_request operation to a remote A2A agent.

        Args:
            name: The name of the downstream agent being called (e.g., "MyRemoteAgent").

        Returns:
            MonitorInstance configured for A2A proxy request tracking.
        """
        instance = super().create(
            component_type="a2a_agent",
            component_name=name,
            operation="forward_request"
        )
        instance.error_parser = cls.parse_error
        return instance