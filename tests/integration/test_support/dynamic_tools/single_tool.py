from typing import Optional
from google.genai import types as adk_types
from google.adk.tools import ToolContext
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool

class MySimpleDynamicTool(DynamicTool):
    """A simple, class-based dynamic tool for integration testing."""

    @property
    def tool_name(self) -> str:
        return "get_dynamic_greeting"

    @property
    def tool_description(self) -> str:
        return "Returns a simple, dynamically-configured greeting."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "name": adk_types.Schema(type=adk_types.Type.STRING, description="The name to greet.")
            },
            required=["name"],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None
    ) -> dict:
        name = args.get("name", "World")
        greeting_prefix = self.tool_config.get("greeting_prefix", "Hello")
        return {"greeting": f"{greeting_prefix}, {name}!"}
