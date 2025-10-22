"""
A DynamicTool for testing lifecycle hooks.
It uses the lifecycle_tracker to record when its init and cleanup methods are called.
"""
import logging
from typing import Optional, Any
from pathlib import Path

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig
from tests.integration.test_support.lifecycle_tracker import track

log = logging.getLogger(__name__)

if "SamAgentComponent" not in globals():
    from solace_agent_mesh.agent.sac.component import SamAgentComponent


class LifecycleTestTool(DynamicTool):
    """A test tool that tracks its own lifecycle."""

    @property
    def tool_name(self) -> str:
        return "lifecycle_test_tool"

    @property
    def tool_description(self) -> str:
        return "A tool to verify lifecycle hooks are called. It returns its input."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "test_input": adk_types.Schema(
                    type=adk_types.Type.STRING, description="Some test input."
                )
            },
            required=["test_input"],
        )

    async def init(self, component: "SamAgentComponent", tool_config: "AnyToolConfig"):
        """On init, write to the tracker file."""
        log.info("LifecycleTestTool: init() called.")
        tracker_file = Path(self.tool_config["tracker_file"])

        # Check for argument injection test mode
        if self.tool_config.get("test_mode") == "arg_injection":
            agent_name = component.agent_name
            my_value = self.tool_config.get("my_value")
            track(tracker_file, f"dynamic_init_agent_name:{agent_name}")
            track(tracker_file, f"dynamic_init_my_value:{my_value}")
            return  # Exit early to not interfere with other tests

        # Check if we are in the mixed test by seeing if a YAML hook is also configured
        if tool_config.init_function:
            track(tracker_file, "step_2_dynamic_init")
        else:
            track(tracker_file, "dynamic_init_called")

    async def cleanup(
        self, component: "SamAgentComponent", tool_config: "AnyToolConfig"
    ):
        """On cleanup, write to the tracker file."""
        log.info("LifecycleTestTool: cleanup() called.")
        tracker_file = Path(self.tool_config["tracker_file"])

        # Check for non-fatal failure test mode
        if self.tool_config.get("test_mode") == "cleanup_failure":
            track(tracker_file, "dynamic_cleanup_started_and_will_fail")
            raise ValueError("Simulated non-fatal cleanup failure")

        # Check for argument injection test mode
        if self.tool_config.get("test_mode") == "arg_injection":
            return  # Not needed for this test

        # Check if we are in the mixed test by seeing if a YAML hook is also configured
        if tool_config.cleanup_function:
            track(tracker_file, "step_3_dynamic_cleanup")
        else:
            track(tracker_file, "dynamic_cleanup_called")

    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        """Returns the input it received."""
        return {"result": f"Tool received: {args.get('test_input')}"}


# Import hooks to make them available in this module's namespace for the framework
from .lifecycle_yaml_hooks import (
    mixed_yaml_init,
    mixed_yaml_cleanup,
    succeeding_cleanup_hook,
    arg_inspector_init_hook,
)
