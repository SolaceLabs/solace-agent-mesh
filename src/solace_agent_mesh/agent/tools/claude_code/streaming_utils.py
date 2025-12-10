"""
Streaming utilities for Claude Code.

Handles parsing and processing of Claude Code's stream-json output format.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional, Set

log = logging.getLogger(__name__)


async def process_claude_stream(
    stdout: asyncio.StreamReader,
    status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Process Claude Code stream-json output.

    Claude Code CLI uses a different streaming format than the Anthropic API.
    Events have structure:
    - {"type": "stream_event", "data": {...}} - Low-level API events (ignored)
    - {"type": "assistant", "message": {"content": [...]}} - Complete assistant messages with tool uses
    - {"type": "user", ...} - User messages
    - {"type": "system", ...} - System messages
    - {"type": "result", ...} - Final result

    Args:
        stdout: Async stream reader
        status_callback: Optional callback for status updates
                        Called with (event_type, event_data)

    Returns:
        Final result dict with collected output
    """
    result_text = []
    all_tools_used = []
    seen_tool_ids: Set[str] = set()  # Track tools we've reported
    session_id = ""

    while True:
        # Read line with increased buffer limit to handle long lines
        # Default is 2**16 (64KB), we increase to 10MB to handle large prompts/outputs
        try:
            line_bytes = await stdout.readline()
        except ValueError as e:
            # If we hit buffer limit, log and try to recover
            if "chunk is longer than limit" in str(e):
                log.error(f"Buffer overflow in stream reading: {e}")
                log.error("Line exceeds asyncio StreamReader buffer limit")
                # Try to read remaining data and skip this line
                try:
                    # Read and discard up to the next newline
                    await stdout.readuntil(b'\n')
                except Exception:
                    pass
                continue
            raise
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8").strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse streaming event: {line[:100]}")
            continue

        event_type = event.get("type")

        if event_type == "assistant":
            # Assistant message with content (including tool uses)
            message = event.get("message", {})
            content = message.get("content", [])

            for item in content:
                if item.get("type") == "tool_use":
                    tool_name = item.get("name")
                    tool_id = item.get("id")
                    tool_input = item.get("input", {})

                    # Record tool use
                    all_tools_used.append({
                        "name": tool_name,
                        "id": tool_id,
                        "input": tool_input,
                    })

                    # Send status update (only once per tool_id)
                    if status_callback and should_report_tool(tool_name) and tool_id not in seen_tool_ids:
                        seen_tool_ids.add(tool_id)

                        # Send tool start notification
                        status_callback(
                            "tool_start",
                            {
                                "tool": tool_name,
                                "tool_id": tool_id,
                                "message": f"Using {tool_name}...",
                            },
                        )

                        # Send tool completion notification with details
                        status_callback(
                            "tool_complete",
                            {
                                "tool": tool_name,
                                "tool_id": tool_id,
                                "input": tool_input,
                                "message": format_tool_completion(tool_name, tool_input),
                            },
                        )

                elif item.get("type") == "text":
                    # Collect text content
                    text = item.get("text", "")
                    if text:
                        result_text.append(text)

        elif event_type == "result":
            # Final result event
            session_id = event.get("session_id", "")
            # Could also extract other metadata here if needed
            break

    # Assemble final result
    result = {
        "text": "".join(result_text),
        "tools_used": all_tools_used,
        "session_id": session_id,
    }

    return result


def should_report_tool(tool_name: str) -> bool:
    """
    Determine if a tool use should be reported to the user.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool use should be reported
    """
    # Report file operations and commands
    reportable_tools = {
        "Write",
        "Edit",
        "Bash",
        "Read",
        "Glob",
        "Grep",
    }
    return tool_name in reportable_tools


def format_tool_completion(tool_name: str, input_data: Dict[str, Any]) -> str:
    """
    Format a friendly message for tool completion.

    Args:
        tool_name: Name of the tool
        input_data: Tool input parameters

    Returns:
        Formatted message string
    """
    if tool_name == "Write":
        file_path = input_data.get("file_path", "unknown")
        return f"Created/updated {file_path}"

    elif tool_name == "Edit":
        file_path = input_data.get("file_path", "unknown")
        return f"Edited {file_path}"

    elif tool_name == "Bash":
        command = input_data.get("command", "")
        # Truncate long commands
        if len(command) > 50:
            command = command[:50] + "..."
        return f"Ran: {command}"

    elif tool_name == "Read":
        file_path = input_data.get("file_path", "unknown")
        return f"Read {file_path}"

    elif tool_name in ["Glob", "Grep"]:
        pattern = input_data.get("pattern", "")
        return f"{tool_name}: {pattern}"

    else:
        return f"Used {tool_name}"
