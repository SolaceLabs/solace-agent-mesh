"""
Custom MCPToolset that resolves embeds in tool parameters before calling MCP tools.

This module uses dynamic inheritance to support both standard and enterprise MCP tools:
- Standard mode: Inherits from MCPTool and MCPToolset (Google ADK)
- Enterprise mode: Inherits from McpToolWithManifest and McpToolsetWithManifest
  (adds manifest support and tool_config parameter)

The base class is determined at import time based on enterprise package availability.
"""

import logging
import time
from typing import Any

from google.adk.auth.credential_manager import CredentialManager
from google.adk.tools.mcp_tool import MCPTool, MCPToolset
from google.adk.tools.tool_context import ToolContext

from ...common.utils.embeds import (
    EARLY_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_in_string,
)
from ...common.utils.embeds.types import ResolutionMode
from ..utils.context_helpers import get_original_session_id

log = logging.getLogger(__name__)


def _get_base_mcp_toolset_class() -> tuple[type[MCPToolset], bool]:
    """
    Factory function to determine which base MCP toolset class to use for inheritance.

    Tries to import McpToolsetWithManifest from solace_agent_mesh_enterprise.common
    and returns it if available. Falls back to base MCPToolset if not available.

    Returns:
        Tuple of (class, supports_tool_config_flag) where:
        - class: The base MCPToolset class to inherit from
        - supports_tool_config_flag: Whether the class supports tool_config parameter
    """
    try:
        from solace_agent_mesh_enterprise.auth.mcp_toolset_with_manifest import (
            McpToolsetWithManifest,
        )

        return (McpToolsetWithManifest, True)
    except ImportError:
        return (MCPToolset, False)


def _get_base_mcp_tool_class() -> tuple[type[MCPTool], bool]:
    """
    Factory function to determine which base MCP tool class to use for inheritance.

    Tries to import McpToolWithManifest from solace_agent_mesh_enterprise.common
    and returns it if available. Falls back to base MCPTool if not available.

    Returns:
        Tuple of (class, supports_tool_config_flag) where:
        - class: The base MCPTool class to inherit from
        - supports_tool_config_flag: Whether the class supports tool_config parameter
    """
    try:
        from solace_agent_mesh_enterprise.auth.mcp_toolset_with_manifest import (
            McpToolWithManifest,
        )

        return (McpToolWithManifest, True)
    except ImportError:
        return (MCPTool, False)


# Get the base tool class to use for inheritance
_BaseMcpToolClass, _base_supports_tool_config = _get_base_mcp_tool_class()


def _log_mcp_tool_call(userId, agentId, tool_name, session_id):
    """A short log message so that customers can track tool usage per user/agent"""
    log.info(
        "MCP Tool Call - UserID: %s, AgentID: %s, ToolName: %s, SessionID: %s",
        userId,
        agentId,
        tool_name,
        session_id,
        extra={
            "user_id": userId,
            "agent_id": agentId,
            "tool_name": tool_name,
            "session_id": session_id,
        },
    )


def _log_mcp_tool_success(userId, agentId, tool_name, session_id, duration_ms):
    """A short log message so that customers can track successful tool completion per user/agent"""
    log.info(
        "MCP Tool Success - UserID: %s, AgentID: %s, ToolName: %s, SessionID: %s, Duration: %.2fms",
        userId,
        agentId,
        tool_name,
        session_id,
        duration_ms,
        extra={
            "user_id": userId,
            "agent_id": agentId,
            "tool_name": tool_name,
            "session_id": session_id,
            "duration_ms": duration_ms,
        },
    )


def _log_mcp_tool_failure(userId, agentId, tool_name, session_id, duration_ms, error):
    """A short log message so that customers can track tool failures per user/agent"""
    log.error(
        "MCP Tool Failure - UserID: %s, AgentID: %s, ToolName: %s, SessionID: %s, Duration: %.2fms, Error: %s",
        userId,
        agentId,
        tool_name,
        session_id,
        duration_ms,
        str(error),
        extra={
            "user_id": userId,
            "agent_id": agentId,
            "tool_name": tool_name,
            "session_id": session_id,
            "duration_ms": duration_ms,
        },
    )


class EmbedResolvingMCPTool(_BaseMcpToolClass):
    """
    Custom MCPTool that resolves embeds in parameters before calling the actual MCP tool.
    Uses dynamic inheritance to conditionally inherit from McpToolWithManifest when available,
    falling back to the standard MCPTool base class.
    """

    def __init__(
        self,
        original_mcp_tool: MCPTool,
        tool_config: dict | None = None,
        credential_manager: CredentialManager | None = None,
    ):
        # Copy all attributes from the original tool
        if _base_supports_tool_config:
            super().__init__(
                mcp_tool=original_mcp_tool._mcp_tool,
                mcp_session_manager=original_mcp_tool._mcp_session_manager,
                auth_scheme=getattr(original_mcp_tool._mcp_tool, "auth_scheme", None),
                auth_credential=getattr(
                    original_mcp_tool._mcp_tool, "auth_credential", None
                ),
                auth_discovery=getattr(
                    original_mcp_tool._mcp_tool, "auth_discovery", None
                ),
                credential_manager=credential_manager,
            )
        else:
            super().__init__(
                mcp_tool=original_mcp_tool._mcp_tool,
                mcp_session_manager=original_mcp_tool._mcp_session_manager,
                auth_scheme=getattr(original_mcp_tool._mcp_tool, "auth_scheme", None),
                auth_credential=getattr(
                    original_mcp_tool._mcp_tool, "auth_credential", None
                ),
            )
        self._original_mcp_tool: MCPTool = original_mcp_tool
        self._tool_config = tool_config or {}

    async def _resolve_embeds_recursively(
        self,
        data: Any,
        context: Any,
        log_identifier: str,
        current_depth: int = 0,
        max_depth: int = 10,
    ) -> Any:
        """
        Recursively resolve embeds in nested data structures with performance safeguards.

        Args:
            data: The data structure to process (str, list, dict, or other)
            context: Context for embed resolution
            log_identifier: Logging identifier
            current_depth: Current recursion depth
            max_depth: Maximum allowed recursion depth

        Returns:
            Data structure with embeds resolved
        """
        # Depth limit safeguard
        if current_depth >= max_depth:
            log.warning(
                "%s Max recursion depth (%d) reached. Stopping embed resolution.",
                log_identifier,
                max_depth,
            )
            return data

        # Handle None and primitive non-string types
        if data is None or isinstance(data, (int, float, bool)):
            return data

        # Handle strings with embeds
        if isinstance(data, str):
            if EMBED_DELIMITER_OPEN in data:
                try:
                    # Create the resolution context
                    if hasattr(context, "_invocation_context"):
                        # Use the invocation context if available
                        invocation_context = context._invocation_context
                    else:
                        # Error if no invocation context is found
                        log.error(
                            "%s No invocation context found in ToolContext. Cannot resolve embeds.",
                            log_identifier,
                        )
                        return data
                    session_context = invocation_context.session
                    if not session_context:
                        log.error(
                            "%s No session context found in invocation context. Cannot resolve embeds.",
                            log_identifier,
                        )
                        return data

                    resolution_context = {
                        "artifact_service": invocation_context.artifact_service,
                        "session_context": {
                            "session_id": get_original_session_id(invocation_context),
                            "user_id": session_context.user_id,
                            "app_name": session_context.app_name,
                        },
                    }
                    resolved_value, _, _ = await resolve_embeds_in_string(
                        text=data,
                        context=resolution_context,
                        resolver_func=evaluate_embed,
                        types_to_resolve=EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES),
                        resolution_mode=ResolutionMode.TOOL_PARAMETER,
                        log_identifier=log_identifier,
                        config=self._tool_config,
                    )
                    return resolved_value
                except Exception as e:
                    log.error(
                        "%s Failed to resolve embed in string: %s",
                        log_identifier,
                        e,
                    )
                    return data
            return data

        # Handle lists
        if isinstance(data, list):
            resolved_list = []
            for i, item in enumerate(data):
                try:
                    resolved_item = await self._resolve_embeds_recursively(
                        item, context, log_identifier, current_depth + 1, max_depth
                    )
                    resolved_list.append(resolved_item)
                except Exception as e:
                    log.error(
                        "%s Failed to resolve embeds in list item %d: %s",
                        log_identifier,
                        i,
                        e,
                    )
                    resolved_list.append(item)  # Keep original on error
            return resolved_list

        # Handle dictionaries
        if isinstance(data, dict):
            resolved_dict = {}
            for key, value in data.items():
                try:
                    resolved_value = await self._resolve_embeds_recursively(
                        value, context, log_identifier, current_depth + 1, max_depth
                    )
                    resolved_dict[key] = resolved_value
                except Exception as e:
                    log.error(
                        "%s Failed to resolve embeds in dict key '%s': %s",
                        log_identifier,
                        key,
                        e,
                    )
                    resolved_dict[key] = value  # Keep original on error
            return resolved_dict

        # Handle tuples (convert to list, process, convert back)
        if isinstance(data, tuple):
            try:
                resolved_list = await self._resolve_embeds_recursively(
                    list(data), context, log_identifier, current_depth + 1, max_depth
                )
                return tuple(resolved_list)
            except Exception as e:
                log.error(
                    "%s Failed to resolve embeds in tuple: %s",
                    log_identifier,
                    e,
                )
                return data

        # Handle sets (convert to list, process, convert back)
        if isinstance(data, set):
            try:
                resolved_list = await self._resolve_embeds_recursively(
                    list(data), context, log_identifier, current_depth + 1, max_depth
                )
                return set(resolved_list)
            except Exception as e:
                log.error(
                    "%s Failed to resolve embeds in set: %s",
                    log_identifier,
                    e,
                )
                return data

        # For any other type, return as-is
        log.debug(
            "%s Skipping embed resolution for unsupported type: %s",
            log_identifier,
            type(data).__name__,
        )
        return data


    async def _execute_tool_with_audit_logs(self, tool_call, tool_context):
        _log_mcp_tool_call(
            tool_context.session.user_id,
            tool_context.agent_name,
            self.name,
            tool_context.session.id,
        )
        start_time = time.perf_counter()
        try:
            result = await tool_call()
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_mcp_tool_success(
                tool_context.session.user_id,
                tool_context.agent_name,
                self.name,
                tool_context.session.id,
                duration_ms,
            )
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _log_mcp_tool_failure(
                tool_context.session.user_id,
                tool_context.agent_name,
                self.name,
                tool_context.session.id,
                duration_ms,
                e,
            )
            raise

    async def _run_async_impl(
        self, *, args, tool_context: ToolContext, credential
    ) -> Any:
        """
        Override the run implementation to resolve embeds recursively before calling the original tool.
        """
        log_identifier = f"[EmbedResolvingMCPTool:{self.name}]"

        # Get context for embed resolution - pass the tool_context object directly
        context_for_embeds = tool_context
        if context_for_embeds:
            log.debug(
                "%s Starting recursive embed resolution for all parameters. Context type: %s",
                log_identifier,
                type(context_for_embeds).__name__,
            )
            # Log context attributes for debugging
            if hasattr(context_for_embeds, "__dict__"):
                context_attrs = list(context_for_embeds.__dict__.keys())
                log.debug(
                    "%s Context attributes available: %s", log_identifier, context_attrs
                )
            try:
                # Recursively resolve embeds in the entire args structure
                resolved_args = await self._resolve_embeds_recursively(
                    data=args,
                    context=context_for_embeds,
                    log_identifier=log_identifier,
                    current_depth=0,
                    max_depth=10,  # Configurable depth limit
                )
                log.debug("%s Completed recursive embed resolution", log_identifier)
            except Exception as e:
                log.error(
                    "%s Failed during recursive embed resolution: %s. Using original args.",
                    log_identifier,
                    e,
                )
                resolved_args = args  # Fallback to original args
        else:
            log.warning(
                "%s ToolContext not found. Skipping embed resolution for all parameters.",
                log_identifier,
            )
            resolved_args = args
        # Call the original MCP tool with resolved parameters
        return await self._execute_tool_with_audit_logs(
            lambda: self._original_mcp_tool._run_async_impl(
                args=resolved_args, tool_context=tool_context, credential=credential
            ),
            tool_context,
        )

# Get the base toolset class to use for inheritance
_BaseMcpToolsetClass, _base_toolset_supports_tool_config = _get_base_mcp_toolset_class()


class EmbedResolvingMCPToolset(_BaseMcpToolsetClass):
    """
    Custom MCPToolset that creates EmbedResolvingMCPTool instances for embed resolution.
    Uses dynamic inheritance to conditionally inherit from McpToolsetWithManifest when available,
    falling back to the standard MCPToolset base class.
    """

    def __init__(
        self,
        connection_params,
        tool_filter=None,
        tool_name_prefix=None,
        auth_scheme=None,
        auth_credential=None,
        auth_discovery=None,
        tool_config: dict | None = None,
        credential_manager: CredentialManager | None = None,
    ):
        # Store tool_config for later use
        self._tool_config = tool_config or {}

        # Initialize base class with appropriate parameters
        if _base_toolset_supports_tool_config:
            super().__init__(
                connection_params=connection_params,
                tool_filter=tool_filter,
                tool_name_prefix=tool_name_prefix,
                auth_scheme=auth_scheme,
                auth_credential=auth_credential,
                auth_discovery=auth_discovery,
                tool_config=tool_config,
            )
        else:
            # Base MCPToolset doesn't support tool_config parameter
            super().__init__(
                connection_params=connection_params,
                tool_filter=tool_filter,
                tool_name_prefix=tool_name_prefix,
                auth_scheme=auth_scheme,
                auth_credential=auth_credential,
            )

        self._tool_cache = []
        self._credential_manager = credential_manager

    async def get_tools(self, readonly_context=None) -> list[MCPTool]:
        """
        Override get_tools to return EmbedResolvingMCPTool instances.
        """

        if self._tool_cache:
            return self._tool_cache

        # Get the original tools from the parent class
        original_tools = await super().get_tools(readonly_context)

        # Wrap each tool with embed resolution capability
        embed_resolving_tools = []

        for tool in original_tools:
            # Get tool-specific config
            tool_specific_config = self._tool_config.get("tool_configs", {}).get(
                tool.name, self._tool_config.get("config", {})
            )

            embed_resolving_tool = EmbedResolvingMCPTool(
                original_mcp_tool=tool,
                tool_config=tool_specific_config,
                credential_manager=self._credential_manager,
            )
            embed_resolving_tools.append(embed_resolving_tool)

        self._tool_cache = embed_resolving_tools
        return embed_resolving_tools
