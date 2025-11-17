"""
Helper functions for working with invocation contexts in the A2A agent tools.
"""

from typing import Any
from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions import Session


def get_session_from_callback_context(
    callback_context: CallbackContext,
) -> Session:
    """
    Safely retrieves the persistent Session object from a CallbackContext.

    This encapsulates the access to the internal '_invocation_context' attribute,
    providing a stable way to get the session if the underlying ADK structure
    changes in the future.

    Args:
        callback_context: The callback context provided by the ADK.

    Returns:
        The ADK Session object.

    Raises:
        AttributeError: If the session cannot be found in the context.
    """
    if hasattr(callback_context, "_invocation_context") and hasattr(
        callback_context._invocation_context, "session"
    ):
        return callback_context._invocation_context.session
    raise AttributeError("Could not find 'session' in the provided callback_context.")


def get_original_session_id(invocation_context: Any) -> str:
    """
    Extract the original session ID from an invocation context.

    When session IDs contain a colon, this function returns only the part before
    the first colon, which is the original session ID.

    Args:
        invocation_context: The invocation context object from tool_context.
                            Typically accessed via `tool_context._invocation_context`.

    Returns:
        str: The original session ID (part before the first colon if present).
             Returns the raw ID if no colon is found.
    """
    if not hasattr(invocation_context, "session") or not hasattr(
        invocation_context.session, "id"
    ):
        if isinstance(invocation_context, str):
            raw_session_id = invocation_context
        else:
            return ""
    else:
        raw_session_id = invocation_context.session.id
    return raw_session_id.split(":", 1)[0] if ":" in raw_session_id else raw_session_id


def get_user_timezone(invocation_context: Any) -> str:
    """
    Extract the user's timezone from an invocation context.

    Args:
        invocation_context: The invocation context object from tool_context.
                            Typically accessed via `tool_context._invocation_context`.

    Returns:
        str: The user's timezone (e.g., "America/Toronto").
             Returns "UTC" if timezone is not available in the context.
    """
    if hasattr(invocation_context, "user_timezone"):
        return invocation_context.user_timezone or "UTC"
    return "UTC"
