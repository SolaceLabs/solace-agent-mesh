from typing import Dict, Any, Optional
from google.adk.tools import ToolContext
from pathlib import Path
from solace_ai_connector.common.log import log
from tests.integration.test_support.lifecycle_tracker import track

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


async def yaml_init_hook(component: "SamAgentComponent", tool_config: "AnyToolConfig"):
    """A simple init hook for YAML configuration tests."""
    log.info("yaml_init_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "yaml_init_called")


async def yaml_cleanup_hook(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """A simple cleanup hook for YAML configuration tests."""
    log.info("yaml_cleanup_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "yaml_cleanup_called")


async def failing_init_hook(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """An init hook that always fails."""
    log.info("failing_init_hook called, will raise ValueError.")
    raise ValueError("Simulated fatal init failure")
