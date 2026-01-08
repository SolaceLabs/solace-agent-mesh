"""
Test support module for dynamic tools with complex function signatures.
"""
from typing import List, Optional, Dict, Any
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
from google.adk.tools import ToolContext


class ComplexSignatureProvider(DynamicToolProvider):
    """A provider for testing complex function signature parsing."""

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        return []


@ComplexSignatureProvider.register_tool
async def handle_optional_param(
    self, name: Optional[str] = None, tool_context: ToolContext = None
) -> dict:
    """Handles an optional string parameter."""
    if name is None:
        return {"result": "Name was not provided."}
    return {"result": f"Name is {name}."}


@ComplexSignatureProvider.register_tool
async def process_complex_types(
    self, items: List[int], config: Dict[str, Any], tool_context: ToolContext = None
) -> dict:
    """Processes list and dict types."""
    return {
        "item_sum": sum(items),
        "config_keys": sorted(list(config.keys())),
    }


@ComplexSignatureProvider.register_tool
async def use_default_values(
    self, count: int = 10, is_enabled: bool = True, tool_context: ToolContext = None
) -> dict:
    """Uses default values for its parameters."""
    return {"count": count, "is_enabled": is_enabled}


@ComplexSignatureProvider.register_tool
async def accept_extra_args(
    self, required_arg: str, tool_context: ToolContext = None, **kwargs
) -> dict:
    """Accepts a required argument and dynamic kwargs."""
    return {"required": required_arg, "extras": sorted(list(kwargs.keys()))}


@ComplexSignatureProvider.register_tool
async def handle_unsupported_type(
    self, data: Any, tool_context: ToolContext = None
) -> dict:
    """Handles a parameter with an unsupported type hint (Any)."""
    # The schema should default to STRING for 'Any'
    return {"data_type": str(type(data)), "data_value": data}
