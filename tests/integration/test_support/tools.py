import logging
from typing import Dict, Any, Optional
from google.adk.tools import ToolContext
from pathlib import Path
from tests.integration.test_support.lifecycle_tracker import track

log = logging.getLogger(__name__)

if "SamAgentComponent" not in globals():
    from solace_agent_mesh.agent.sac.component import SamAgentComponent
if "AnyToolConfig" not in globals():
    from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig


async def get_weather_tool(
    location: str,
    unit: Optional[str] = "celsius",
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    A mock weather tool for testing.
    """
    print(f"[TestTool:get_weather_tool] Called with location: {location}, unit: {unit}")
    if location.lower() == "london":
        return {"temperature": "22", "unit": unit or "celsius", "condition": "sunny"}
    elif location.lower() == "paris":
        return {"temperature": "25", "unit": unit or "celsius", "condition": "lovely"}
    else:
        return {
            "temperature": "unknown",
            "unit": unit or "celsius",
            "condition": "unknown",
        }


# Import hooks to make them available in this module's namespace for the framework
from tests.integration.test_support.dynamic_tools.lifecycle_yaml_hooks import (
    yaml_init_hook,
    yaml_cleanup_hook,
    failing_init_hook,
)
