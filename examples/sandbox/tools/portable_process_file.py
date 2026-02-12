"""
Portable version of process_file that works in both python and sam_remote executors.

Uses type annotations for Artifact (input) and ToolContextFacade (context).
The framework detects these and injects objects by parameter name, whether
running in-process or in the sandbox.
"""

from solace_agent_mesh.agent.tools.artifact_types import Artifact
from solace_agent_mesh.agent.tools.tool_result import ToolResult, DataObject
from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade


async def portable_process_file(
    input_file: Artifact,
    ctx: ToolContextFacade,
) -> ToolResult:
    """Process an input file artifact and produce a summary.

    Same logic as the legacy process_file_tool, but using the portable API
    so it works in both executor environments.

    Args:
        input_file: The artifact to process (framework pre-loads content)
        ctx: Tool context for status updates

    Returns:
        ToolResult with summary text and an output artifact
    """
    ctx.send_status("Loading input artifact...")

    content = input_file.as_text()

    ctx.send_status("Processing file content...")

    # Compute basic statistics
    lines = content.split("\n")
    words = content.split()
    char_count = len(content)
    line_count = len(lines)
    word_count = len(words)

    # Build a summary report
    summary_lines = [
        "=== Portable File Processing Summary ===",
        f"Filename: {input_file.filename}",
        f"MIME type: {input_file.mime_type}",
        f"Version: {input_file.version}",
        f"Characters: {char_count}",
        f"Words:      {word_count}",
        f"Lines:      {line_count}",
        "",
        "--- First 5 lines ---",
    ]
    for line in lines[:5]:
        summary_lines.append(f"  {line}")
    if line_count > 5:
        summary_lines.append(f"  ... ({line_count - 5} more lines)")

    summary_text = "\n".join(summary_lines)

    ctx.send_status("Creating summary artifact...")

    return ToolResult.ok(
        message=f"Processed {input_file.filename}: {line_count} lines, {word_count} words",
        data={
            "statistics": {
                "character_count": char_count,
                "word_count": word_count,
                "line_count": line_count,
            },
        },
        data_objects=[
            DataObject(
                name="processing_summary.txt",
                content=summary_text,
                mime_type="text/plain",
                description="File processing summary report",
            ),
        ],
    )
