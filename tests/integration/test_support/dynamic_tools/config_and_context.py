"""
Test support module for dynamic tools testing config and context features.
"""

from typing import List, Optional, Dict, Any, Literal

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider


class RawStringTool(DynamicTool):
    """A tool to test raw_string_args functionality."""

    @property
    def tool_name(self) -> str:
        return "handle_raw_string"

    @property
    def tool_description(self) -> str:
        return "Accepts a raw string argument without resolving embeds."

    @property
    def raw_string_args(self) -> List[str]:
        return ["raw_arg"]

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "raw_arg": adk_types.Schema(type=adk_types.Type.STRING),
            },
            required=["raw_arg"],
        )

    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        return {"result": args.get("raw_arg")}


class LateResolutionTool(DynamicTool):
    """A tool to test late (all) embed resolution."""

    @property
    def tool_name(self) -> str:
        return "resolve_late_embed"

    @property
    def tool_description(self) -> str:
        return (
            "Accepts an argument and resolves all embeds, including artifact_content."
        )

    @property
    def resolution_type(self) -> Literal["early", "all"]:
        return "all"

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "late_arg": adk_types.Schema(type=adk_types.Type.STRING),
            },
            required=["late_arg"],
        )

    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        return {"result": args.get("late_arg")}


class ConfigAndContextProvider(DynamicToolProvider):
    """
    A provider for testing tool_config injection and embed resolution contexts.
    """

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        # Return tool instances that need custom properties
        return [
            RawStringTool(tool_config=tool_config),
            LateResolutionTool(tool_config=tool_config),
        ]


@ConfigAndContextProvider.register_tool
async def inspect_tool_config(
    tool_context: ToolContext = None, tool_config: Optional[dict] = None
) -> dict:
    """Returns the tool_config that was injected into the provider."""
    return {"config_received": tool_config}


@ConfigAndContextProvider.register_tool
async def resolve_early_embed(my_arg: str, tool_context: ToolContext = None) -> dict:
    """Accepts an argument and resolves early embeds (the default)."""
    return {"result": my_arg}
