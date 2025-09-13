"""
A DynamicTool for testing lifecycle hooks.
It uses the lifecycle_tracker to record when its init and cleanup methods are called.
"""
from typing import Optional, Any
from pathlib import Path

from google.adk.tools import ToolContext
from google.genai import types as adk_types
from solace_ai_connector.common.log import log

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig
from tests.integration.test_support.lifecycle_tracker import track

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
