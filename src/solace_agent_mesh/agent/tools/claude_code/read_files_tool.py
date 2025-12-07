"""
Claude Code Read Files Tool.

Read files from a workspace using glob patterns.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ....common.workspace import BaseWorkspaceService
from ..dynamic_tool import DynamicTool

log = logging.getLogger(__name__)


def get_user_id_from_context(tool_context: Optional[ToolContext]) -> str:
    """Extract user ID from tool context."""
    if tool_context and hasattr(tool_context, "user_id"):
        return tool_context.user_id
    return "default_user"


def generate_tree(workspace_path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> str:
    """
    Generate a directory tree visualization.

    Args:
        workspace_path: Path to workspace
        prefix: Prefix for indentation
        max_depth: Maximum depth to traverse
        current_depth: Current depth in traversal

    Returns:
        Tree visualization string
    """
    if current_depth >= max_depth:
        return ""

    tree_lines = []
    try:
        items = sorted(workspace_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

        for i, item in enumerate(items):
            # Skip hidden files except .git
            if item.name.startswith(".") and item.name not in [".git", ".gitignore"]:
                continue

            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{item.name}")

            if item.is_dir():
                extension = "    " if is_last else "│   "
                tree_lines.append(
                    generate_tree(item, prefix + extension, max_depth, current_depth + 1)
                )

    except PermissionError:
        pass

    return "\n".join(filter(None, tree_lines))


class ClaudeCodeReadFilesTool(DynamicTool):
    """Read files from a workspace."""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service

    @property
    def tool_name(self) -> str:
        return "claude_code_read_files"

    @property
    def tool_description(self) -> str:
        return "Read files from a workspace using glob patterns."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "workspace_id": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Workspace identifier",
                ),
                "workspace_type": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="'session' or 'app'",
                ),
                "file_pattern": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Glob pattern for files (e.g., '**/*.ts')",
                ),
            },
            required=["workspace_id"],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """Read files from workspace."""
        user_id = get_user_id_from_context(tool_context)
        workspace_id = args["workspace_id"]
        workspace_type = args.get("workspace_type", "session")
        file_pattern = args.get("file_pattern", "**/*")

        log.info(
            f"Reading files from workspace {workspace_id} "
            f"(type: {workspace_type}, pattern: {file_pattern})"
        )

        # Get workspace path
        workspace_path = await self.workspace_service.get_workspace_path(
            workspace_id, user_id, workspace_type
        )

        if not workspace_path:
            return {
                "status": "error",
                "error": f"Workspace not found: {workspace_id}",
                "files": {},
                "tree": "",
            }

        # Read files matching pattern
        files = {}
        for file_path in workspace_path.glob(file_pattern):
            if file_path.is_file():
                try:
                    relative_path = file_path.relative_to(workspace_path)
                    # Skip binary files and metadata
                    if file_path.suffix in [".pyc", ".so", ".dll", ".exe"]:
                        continue
                    if file_path.name == ".workspace-metadata.json":
                        continue

                    content = file_path.read_text(errors="ignore")
                    files[str(relative_path)] = content
                except Exception as e:
                    log.warning(f"Failed to read file {file_path}: {e}")

        # Generate tree
        tree = generate_tree(workspace_path)

        log.info(f"Read {len(files)} files from workspace {workspace_id}")

        return {
            "status": "success",
            "files": files,
            "tree": tree,
        }
