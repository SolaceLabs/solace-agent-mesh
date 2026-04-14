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


class ArtifactMonitor(OperationMonitor):
    """
    Type-safe monitor for artifact service operation duration.

    Inherits from OperationMonitor but constrains the API via named factory
    methods to prevent metric explosion. Automatically sets type="artifact"
    and component.name="artifact_service".

    Maps to: operation.duration histogram
    Labels: type="artifact", component.name="artifact_service",
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
        return super().create(
            component_type="artifact",
            component_name="artifact_service",
            operation=operation,
        )

    @classmethod
    def save(cls) -> MonitorInstance:
        """Create monitor instance for save_artifact operation."""
        return cls._create("save")

    @classmethod
    def load(cls) -> MonitorInstance:
        """Create monitor instance for load_artifact operation."""
        return cls._create("load")

    @classmethod
    def delete(cls) -> MonitorInstance:
        """Create monitor instance for delete_artifact operation."""
        return cls._create("delete")

    @classmethod
    def list_keys(cls) -> MonitorInstance:
        """Create monitor instance for list_artifact_keys operation."""
        return cls._create("list_keys")

    @classmethod
    def list_versions(cls) -> MonitorInstance:
        """Create monitor instance for list_versions operation."""
        return cls._create("list_versions")

    @classmethod
    def list_artifact_versions(cls) -> MonitorInstance:
        """Create monitor instance for list_artifact_versions operation."""
        return cls._create("list_artifact_versions")

    @classmethod
    def get_version(cls) -> MonitorInstance:
        """Create monitor instance for get_artifact_version operation."""
        return cls._create("get_version")