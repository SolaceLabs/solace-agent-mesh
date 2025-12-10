"""
Claude Code List Workspaces Tool.

List all workspaces for the current user.
"""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ....common.workspace import BaseWorkspaceService
from ..dynamic_tool import DynamicTool

log = logging.getLogger(__name__)


def get_user_id_from_context(tool_context: Optional[ToolContext]) -> str:
    """Extract user ID from tool context."""
    if tool_context:
        # First try tool_context.user_id (ADK standard)
        if hasattr(tool_context, "user_id") and tool_context.user_id:
            return tool_context.user_id

        # Fall back to a2a_context.user_id (SAM pattern)
        if hasattr(tool_context, "state"):
            a2a_context = tool_context.state.get("a2a_context", {})
            user_id = a2a_context.get("user_id")
            if user_id:
                return user_id

    return "default_user"


class ClaudeCodeListWorkspacesTool(DynamicTool):
    """List all workspaces for the current user."""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service

    @property
    def tool_name(self) -> str:
        return "claude_code_list_workspaces"

    @property
    def tool_description(self) -> str:
        return "List all workspaces for the current user with metadata."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "workspace_type": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Optional filter: 'session' or 'app'",
                ),
            },
            required=[],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """List workspaces."""
        user_id = get_user_id_from_context(tool_context)
        workspace_type = args.get("workspace_type")

        log.info(
            f"Listing workspaces for user {user_id}"
            + (f", type {workspace_type}" if workspace_type else "")
        )

        workspaces = await self.workspace_service.list_workspaces(
            user_id, workspace_type
        )

        # Convert Path objects to strings for JSON serialization
        for workspace in workspaces:
            if "path" in workspace:
                workspace["path"] = str(workspace["path"])

        return {
            "status": "success",
            "workspaces": workspaces,
            "count": len(workspaces),
        }
