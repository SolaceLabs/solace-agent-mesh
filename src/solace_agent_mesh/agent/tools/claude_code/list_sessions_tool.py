"""
Claude Code List Sessions Tool.

Tool for listing available Claude Code sessions that can be resumed.
"""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ..dynamic_tool import DynamicTool

log = logging.getLogger(__name__)


def get_user_id_from_context(tool_context: Optional[ToolContext]) -> str:
    """Extract user ID from tool context."""
    if tool_context and hasattr(tool_context, "user_id"):
        return tool_context.user_id
    return "default_user"


class ClaudeCodeListSessionsTool(DynamicTool):
    """
    List available Claude Code sessions that can be resumed.

    Shows active sessions with their workspace_id and session_id.
    Use this to discover session IDs for resuming conversations.
    """

    def __init__(
        self,
        session_store: Dict[str, str],
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.session_store = session_store

    @property
    def tool_name(self) -> str:
        return "claude_code_list_sessions"

    @property
    def tool_description(self) -> str:
        return """List available Claude Code sessions for the current user.
Shows workspace_id and session_id for each active session.
Use session_id with resume_session_id parameter to continue conversations."""

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={},
            required=[],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """List all Claude Code sessions for the current user."""
        user_id = get_user_id_from_context(tool_context)

        log.info(f"Listing Claude Code sessions for user: {user_id}")

        # Filter sessions for this user
        user_prefix = f"{user_id}/"
        user_sessions = {
            key: session_id
            for key, session_id in self.session_store.items()
            if key.startswith(user_prefix)
        }

        # Format sessions for output
        sessions = []
        for key, session_id in user_sessions.items():
            # Extract workspace_id from key (format: "user_id/workspace_id")
            workspace_id = key[len(user_prefix) :]
            sessions.append(
                {
                    "workspace_id": workspace_id,
                    "session_id": session_id,
                    "user_id": user_id,
                }
            )

        log.info(f"Found {len(sessions)} active sessions for user {user_id}")

        return {
            "status": "success",
            "count": len(sessions),
            "sessions": sessions,
            "message": (
                f"Found {len(sessions)} active Claude Code session(s). "
                "Use resume_session_id parameter to continue a conversation."
                if sessions
                else "No active Claude Code sessions found."
            ),
        }
