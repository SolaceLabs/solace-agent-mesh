"""
SAM-specific observability monitors.

Provides type-safe monitor classes for instrumenting SAM agents and tools.
These extend solace_ai_connector's OperationMonitor with constrained APIs
to prevent accidental metric explosion.
"""

from solace_ai_connector.common.observability.monitors.operation import OperationMonitor
from solace_ai_connector.common.observability.monitors.remote import RemoteRequestMonitor
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


class ArtifactMonitor(RemoteRequestMonitor):
    """
    Type-safe monitor for artifact service operation duration.

    Uses RemoteRequestMonitor since artifacts are a single external service,
    not a group of equivalent components. Constrains the API via named factory
    methods to prevent metric explosion.

    Maps to: outbound.request.duration histogram
    Labels: service.peer.name="artifact_service",
            operation.name=<operation>, error.type

    Usage:
        from solace_agent_mesh.common.observability import ArtifactMonitor
        from solace_ai_connector.common.observability import MonitorLatency

        with MonitorLatency(ArtifactMonitor.save()):
            result = await service.save_artifact(...)
    """

    @classmethod
    def _create(cls, operation: str) -> MonitorInstance:
        """Internal factory — all public methods delegate here."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "service.peer.name": "artifact_service",
                "operation.name": operation,
            },
            error_parser=cls.parse_error,
        )

    @classmethod
    def save(cls) -> MonitorInstance:
        """Create monitor instance for save_artifact operation."""
        return cls._create("save")

    @classmethod
    def load(cls) -> MonitorInstance:
        """Create monitor instance for load_artifact and get_artifact_version operations."""
        return cls._create("load")

    @classmethod
    def delete(cls) -> MonitorInstance:
        """Create monitor instance for delete_artifact operation."""
        return cls._create("delete")

    @classmethod
    def list(cls) -> MonitorInstance:
        """Create monitor instance for all list operations (keys, versions, artifact_versions)."""
        return cls._create("list")