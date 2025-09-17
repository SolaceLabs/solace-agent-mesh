"""
Test support module for dynamic tool discovery tests.
Contains a provider and a standalone tool to test discovery preference.
"""

from typing import List, Optional
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
from google.adk.tools import ToolContext


class MixedDiscoveryTool(DynamicTool):
    """
    This is a standalone DynamicTool. It should NOT be discovered if a
    DynamicToolProvider exists in the same module.
    """

    @property
    def tool_name(self) -> str:
        return "standalone_tool_should_not_be_loaded"

    @property
    def tool_description(self) -> str:
        return "This tool should not be loaded during auto-discovery."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(type=adk_types.Type.OBJECT, properties={})

    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        return {"error": "This tool should not have been executed."}


class MixedDiscoveryProvider(DynamicToolProvider):
    """
    This is the provider in the mixed module. It should be discovered,
    and its tools should be loaded.
    """

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        # Must implement the abstract method.
        return []


@MixedDiscoveryProvider.register_tool
async def preferred_tool_from_provider(self, tool_context: ToolContext = None) -> dict:
    """This tool should be loaded because it's from the provider."""
    return {"status": "ok"}
