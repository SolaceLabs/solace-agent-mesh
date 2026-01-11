"""
Example tool demonstrating streaming status updates from a Lambda function.

This tool sends periodic status updates during processing, which are streamed
back to SAM via NDJSON over the Lambda Function URL connection.
"""

import asyncio
from agent_tools import ToolResult, ToolContextBase


async def slow_process(
    message: str,
    steps: int,
    ctx: ToolContextBase,
) -> ToolResult:
    """
    Process a message with streaming status updates.

    This tool simulates a long-running process that sends status updates
    at each step. Use it to test streaming functionality.

    Args:
        message: The message to process
        steps: Number of processing steps (each takes ~1 second)
        ctx: Tool context for sending status updates

    Returns:
        ToolResult with the processed message and step count
    """
    ctx.send_status(f"Starting to process: {message}")

    for i in range(steps):
        await asyncio.sleep(1)  # Simulate work
        ctx.send_status(f"Step {i + 1}/{steps} complete...")

    return ToolResult.ok(
        message=f"Processed '{message}' in {steps} steps",
        data={"steps_completed": steps, "original_message": message},
    )
