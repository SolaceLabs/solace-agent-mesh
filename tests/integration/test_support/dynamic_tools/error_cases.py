from typing import List, Optional
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
from google.adk.tools import ToolContext

# --- Test Case 1: Empty Provider ---


class EmptyToolProvider(DynamicToolProvider):
    """A provider that correctly provides zero tools."""

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        return []


# --- Test Case 2: Provider with tool missing a docstring ---


class ProviderWithDocstringlessTool(DynamicToolProvider):
    """A provider for testing docstring handling."""

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        # Must implement the abstract method, even if it does nothing.
        return []


@ProviderWithDocstringlessTool.register_tool
async def tool_with_no_docstring(self, some_arg: str, tool_context: ToolContext = None):
    # This tool intentionally lacks a docstring.
    return {"result": f"You passed: {some_arg}"}
