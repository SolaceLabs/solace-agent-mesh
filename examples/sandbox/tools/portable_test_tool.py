"""
Portable tool that works in both python and sam_remote executors.

This tool uses ToolContextFacade type annotations so the framework
handles context injection, whether running in-process or in sandbox.
"""

from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade
from solace_agent_mesh.agent.tools.tool_result import ToolResult, DataObject


async def portable_echo(message: str, ctx: ToolContextFacade) -> ToolResult:
    """Echo a message and create an output artifact. Tests portable tool API."""
    ctx.send_status("Processing message...")

    # Create output artifact via ToolResult/DataObject pattern
    output_content = f"Echoed: {message}\nUser: {ctx.user_id}\nSession: {ctx.session_id}"

    return ToolResult.ok(
        message=f"Echoed: {message}",
        data_objects=[
            DataObject(
                name="echo_output.txt",
                content=output_content,
                mime_type="text/plain",
            ),
        ],
    )
