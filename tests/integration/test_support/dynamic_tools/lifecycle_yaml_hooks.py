"""
A set of simple functions to be used as YAML-configured lifecycle hooks in tests.
"""
from pathlib import Path
from solace_ai_connector.common.log import log

from tests.integration.test_support.lifecycle_tracker import track

if "SamAgentComponent" not in globals():
    from solace_agent_mesh.agent.sac.component import SamAgentComponent
if "AnyToolConfig" not in globals():
    from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig


async def yaml_init_hook(component: "SamAgentComponent", tool_config: "AnyToolConfig"):
    """A simple init hook for YAML configuration tests."""
    log.info("yaml_init_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "yaml_init_called")


async def yaml_cleanup_hook(component: "SamAgentComponent", tool_config: "AnyToolConfig"):
    """A simple cleanup hook for YAML configuration tests."""
    log.info("yaml_cleanup_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "yaml_cleanup_called")


async def mixed_yaml_init(component: "SamAgentComponent", tool_config: "AnyToolConfig"):
    """Init hook for mixed (YAML + DynamicTool) LIFO test."""
    log.info("mixed_yaml_init called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "step_1_yaml_init")


async def mixed_yaml_cleanup(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """Cleanup hook for mixed (YAML + DynamicTool) LIFO test."""
    log.info("mixed_yaml_cleanup called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "step_4_yaml_cleanup")
