"""
Custom MCPToolset that resolves embeds in tool parameters before calling MCP tools.
"""

import asyncio
from typing import Dict, List, Optional, Any

from google.adk.tools.mcp_tool import MCPToolset, MCPTool
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseConnectionParams,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.tool_context import ToolContext
from solace_ai_connector.common.log import log

from ..utils.context_helpers import get_original_session_id
from ...common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)


class EmbedResolvingMCPTool(MCPTool):
    """
    Custom MCPTool that resolves embeds in parameters before calling the actual MCP tool.
    """

    def __init__(self, original_mcp_tool: MCPTool, tool_config: Optional[Dict] = None):
        # Copy all attributes from the original tool
        super().__init__(
            mcp_tool=original_mcp_tool._mcp_tool,
            mcp_session_manager=original_mcp_tool._mcp_session_manager,
            auth_scheme=getattr(original_mcp_tool, "_auth_scheme", None),
            auth_credential=getattr(original_mcp_tool, "_auth_credential", None),
        )
        self._original_mcp_tool = original_mcp_tool
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
        return await self._original_mcp_tool._run_async_impl(
            args=resolved_args, tool_context=tool_context, credential=credential
        )


class EmbedResolvingMCPToolset(MCPToolset):
    """
    Custom MCPToolset that creates EmbedResolvingMCPTool instances for embed resolution.
    """

    def __init__(
        self,
        connection_params,
        tool_filter=None,
        auth_scheme=None,
        auth_credential=None,
        tool_config: Optional[Dict] = None,
    ):
        super().__init__(
            connection_params=connection_params,
            tool_filter=tool_filter,
            auth_scheme=auth_scheme,
            auth_credential=auth_credential,
        )
        self._tool_config = tool_config or {}

    async def get_tools(self, readonly_context=None) -> List[MCPTool]:
        """
        Override get_tools to return EmbedResolvingMCPTool instances.
        """
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
            )
            embed_resolving_tools.append(embed_resolving_tool)

        return embed_resolving_tools
