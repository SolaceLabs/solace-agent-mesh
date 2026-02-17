"""
DynamicTool that enriches its description during init().

This tool tests the sandbox init protocol by providing a static description
initially, then enriching it in init() with runtime-discovered information.
When the init protocol works correctly, the agent will see the enriched
description instead of the static YAML one.

Works both as a sam_remote tool (via sandbox worker) and as a python tool
(via in-process execution).
"""

import platform
import sys
from typing import Dict, Optional

from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from google.adk.tools import ToolContext


class DynamicTestTool(DynamicTool):
    """A DynamicTool that enriches its description during init().

    Before init(): description is a generic placeholder.
    After init(): description includes runtime info (Python version, platform)
    simulating what a real tool would do (e.g., discover a DB schema).
    """

    def __init__(self, tool_config: Optional[dict] = None):
        super().__init__(tool_config=tool_config)
        self._enriched_description = None
        self._greeting_prefix = (tool_config or {}).get(
            "greeting_prefix", "Hello from sandbox"
        )

    @property
    def tool_name(self) -> str:
        return "dynamic_test"

    @property
    def tool_description(self) -> str:
        if self._enriched_description:
            return self._enriched_description
        return "A dynamic test tool (description not yet enriched by init)."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "name": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="A name to greet",
                ),
                "include_details": adk_types.Schema(
                    type=adk_types.Type.BOOLEAN,
                    description="Whether to include runtime details in the response",
                    nullable=True,
                ),
            },
            required=["name"],
        )

    async def init(self, component, tool_config) -> None:
        """Enrich the description with runtime information.

        In a real tool this might query a database for its schema,
        call an API to discover endpoints, etc. Here we use Python
        and platform info as a stand-in.
        """
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        plat = platform.system()

        self._enriched_description = (
            f"A dynamic test tool running on Python {py_version} ({plat}). "
            f"Greets the user with a configurable prefix (currently: '{self._greeting_prefix}'). "
            f"Pass include_details=true to see runtime environment info in the response."
        )

    async def cleanup(self, component, tool_config) -> None:
        pass

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        name = args.get("name", "World")
        include_details = args.get("include_details", False)

        greeting = f"{self._greeting_prefix}, {name}!"

        result = {"greeting": greeting}

        if include_details:
            result["details"] = {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.system(),
                "platform_version": platform.version(),
                "tool_config": self.tool_config,
            }

        return result
