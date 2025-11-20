"""
Collection of Python tools for time and date operations.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from .tool_definition import BuiltinTool
from .registry import tool_registry
from ...agent.utils.context_helpers import get_user_timezone

log = logging.getLogger(__name__)

CATEGORY_NAME = "Time & Date"
CATEGORY_DESCRIPTION = "Get current time and date information in the user's timezone."


async def get_current_time(
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Gets the current date and time in the user's local timezone.

    Args:
        tool_context: The context provided by the ADK framework.
        tool_config: Optional. Configuration passed by the ADK, generally not used by this tool.

    Returns:
        A dictionary with status, current time information, and timezone details.
    """
    log_identifier = "[TimeTools:get_current_time]"
    
    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        # Get user's timezone from context
        user_timezone_str = get_user_timezone(inv_context)
        log.info(f"{log_identifier} Retrieved timezone: {user_timezone_str}")

        # Create timezone object
        try:
            user_tz = ZoneInfo(user_timezone_str)
        except Exception as tz_error:
            log.warning(
                f"{log_identifier} Invalid timezone '{user_timezone_str}', falling back to UTC: {tz_error}"
            )
            user_tz = ZoneInfo("UTC")
            user_timezone_str = "UTC"

        # Get current time in user's timezone
        current_time = datetime.now(user_tz)

        # Calculate timezone offset
        offset = current_time.strftime("%z")
        # Format offset as "+HH:MM" or "-HH:MM"
        if len(offset) == 5:  # Format: +HHMM or -HHMM
            timezone_offset = f"{offset[:3]}:{offset[3:]}"
        else:
            timezone_offset = "+00:00"

        # Get timezone abbreviation (e.g., EST, PST)
        tz_abbrev = current_time.strftime("%Z")

        # Format various time representations
        iso_format = current_time.isoformat()
        formatted_time = current_time.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbrev}")
        date_only = current_time.strftime("%Y-%m-%d")
        time_only = current_time.strftime("%H:%M:%S")
        day_of_week = current_time.strftime("%A")
        timestamp = int(current_time.timestamp())

        log.info(
            f"{log_identifier} Successfully retrieved time for timezone {user_timezone_str}: {formatted_time}"
        )

        return {
            "status": "success",
            "current_time": iso_format,
            "timezone": user_timezone_str,
            "timezone_offset": timezone_offset,
            "timezone_abbreviation": tz_abbrev,
            "formatted_time": formatted_time,
            "timestamp": timestamp,
            "date": date_only,
            "time": time_only,
            "day_of_week": day_of_week,
            "message": f"Current time in {user_timezone_str}: {formatted_time}",
        }

    except ValueError as ve:
        log.error(f"{log_identifier} Value error: {ve}", exc_info=True)
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        log.exception(f"{log_identifier} Unexpected error in get_current_time: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


get_current_time_tool_def = BuiltinTool(
    name="get_current_time",
    implementation=get_current_time,
    description="Gets the current date and time in the user's local timezone. Returns comprehensive time information including formatted timestamps, timezone details, and date components. Use this tool when you need to know what time it is for the user.",
    category="time",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:time:read"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={},
        required=[],
    ),
    examples=[],
)

tool_registry.register(get_current_time_tool_def)