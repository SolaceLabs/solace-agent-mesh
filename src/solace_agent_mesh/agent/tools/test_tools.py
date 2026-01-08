"""
Test-specific ADK Tools.
"""

import logging
import asyncio
from typing import Dict, Optional, Any

from google.adk.tools import ToolContext

from google.genai import types as adk_types
from .tool_definition import BuiltinTool
from .registry import tool_registry

log = logging.getLogger(__name__)

async def time_delay(
    seconds: float,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, any]:
    """
    Pauses execution for a specified number of seconds.
    Useful for testing timeouts and asynchronous behavior.

    Args:
        seconds: The duration of the delay in seconds.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary indicating the status and duration of the delay.
    """
    log_identifier = "[TestTool:time_delay]"
    log.info("%s Requesting delay for %.2f seconds.", log_identifier, seconds)

    if not tool_context:
        log.warning("%s ToolContext is missing.", log_identifier)

    try:
        if not isinstance(seconds, (int, float)) or seconds < 0:
            log.error(
                "%s Invalid 'seconds' argument: %s. Must be a non-negative number.",
                log_identifier,
                seconds,
            )
            return {
                "status": "error",
                "message": f"Invalid 'seconds' argument: {seconds}. Must be a non-negative number.",
            }

        await asyncio.sleep(float(seconds))
        log.info("%s Successfully delayed for %.2f seconds.", log_identifier, seconds)
        return {
            "status": "success",
            "message": f"Delayed for {seconds} seconds.",
            "delayed_seconds": seconds,
        }
    except Exception as e:
        log.exception("%s Error during time_delay: %s", log_identifier, e)
        return {
            "status": "error",
            "message": f"Error during delay: {e}",
            "requested_seconds": seconds,
        }


time_delay_tool_def = BuiltinTool(
    name="time_delay",
    implementation=time_delay,
    description="Pauses execution for a specified number of seconds. Useful for testing timeouts and asynchronous behavior.",
    category="test",
    required_scopes=["tool:test:delay"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "seconds": adk_types.Schema(
                type=adk_types.Type.NUMBER,
                description="The duration of the delay in seconds.",
            ),
        },
        required=["seconds"],
    ),
    examples=[],
)


def always_fail_tool() -> dict:
    """This tool is designed to always raise an exception for testing error handling."""
    raise ValueError("This tool is designed to fail.")


def dangling_tool_call_test_tool() -> None:
    """
    This tool is designed to return None, which simulates a silent failure
    where the ADK does not create a function_response, leaving a dangling
    function_call in the history. This is used to test the proactive
    history repair callback ("the suspenders").
    """
    log.info(
        "[TestTool:dangling_tool_call] Executing and returning None to create a dangling tool call."
    )
    return None


always_fail_tool_def = BuiltinTool(
    name="always_fail_tool",
    implementation=always_fail_tool,
    description="This tool is designed to always raise an exception for testing error handling.",
    category="test",
    required_scopes=["tool:test:fail"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={},
        required=[],
    ),
    examples=[],
)

dangling_tool_call_test_tool_def = BuiltinTool(
    name="dangling_tool_call_test_tool",
    implementation=dangling_tool_call_test_tool,
    description="A test tool that returns None to create a dangling tool call in the history.",
    category="test",
    required_scopes=["tool:test:dangle"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={},
        required=[],
    ),
    examples=[],
)


tool_registry.register(time_delay_tool_def)
tool_registry.register(always_fail_tool_def)
tool_registry.register(dangling_tool_call_test_tool_def)
