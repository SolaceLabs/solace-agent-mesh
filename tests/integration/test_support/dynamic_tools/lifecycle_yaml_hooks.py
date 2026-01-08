"""
A set of simple functions to be used as YAML-configured lifecycle hooks in tests.
"""
import logging
from pathlib import Path

from tests.integration.test_support.lifecycle_tracker import track

log = logging.getLogger(__name__)

if "SamAgentComponent" not in globals():
    from solace_agent_mesh.agent.sac.component import SamAgentComponent
if "AnyToolConfig" not in globals():
    from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig


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


async def failing_cleanup_hook(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """A cleanup hook that always fails."""
    log.info("failing_cleanup_hook called, will raise ValueError.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "failing_cleanup_hook_started")
    raise ValueError("Simulated non-fatal cleanup failure")


async def succeeding_cleanup_hook(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """A cleanup hook that always succeeds."""
    log.info("succeeding_cleanup_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    track(tracker_file, "succeeding_cleanup_hook_called")


async def arg_inspector_init_hook(
    component: "SamAgentComponent", tool_config: "AnyToolConfig"
):
    """An init hook that inspects its arguments and records them."""
    log.info("arg_inspector_init_hook called.")
    tracker_file = Path(tool_config.tool_config["tracker_file"])
    agent_name = component.agent_name
    my_value = tool_config.tool_config.get("my_value")
    track(tracker_file, f"yaml_init_agent_name:{agent_name}")
    track(tracker_file, f"yaml_init_my_value:{my_value}")
