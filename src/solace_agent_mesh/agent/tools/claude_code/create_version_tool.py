"""
Claude Code Create Version Tool.

Create a semantic version snapshot using git tags.
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional, Tuple

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ....common.workspace import BaseWorkspaceService
from ..dynamic_tool import DynamicTool
from .context_helpers import (
    resolve_workspace_params,
    should_hide_workspace_params,
)

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


async def get_latest_version_tag(workspace_path: str) -> Optional[str]:
    """
    Get the latest version tag from git repository.

    Args:
        workspace_path: Path to workspace

    Returns:
        Latest version tag (e.g., "v1.2.3") or None if no tags exist
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "tag",
            "-l",
            "v*",
            "--sort=-version:refname",
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode == 0 and stdout:
            tags = stdout.decode().strip().split("\n")
            if tags and tags[0]:
                return tags[0]

    except Exception as e:
        log.warning(f"Failed to get git tags: {e}")

    return None


def parse_version(version_tag: str) -> Tuple[int, int, int]:
    """
    Parse a version tag into (major, minor, patch).

    Args:
        version_tag: Version tag (e.g., "v1.2.3")

    Returns:
        Tuple of (major, minor, patch)
    """
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version_tag)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return 0, 0, 0


def bump_version(
    current_version: Tuple[int, int, int], bump: str
) -> Tuple[int, int, int]:
    """
    Bump version according to semantic versioning.

    Args:
        current_version: Current (major, minor, patch)
        bump: "major", "minor", or "patch"

    Returns:
        New version tuple
    """
    major, minor, patch = current_version

    if bump == "major":
        return major + 1, 0, 0
    elif bump == "minor":
        return major, minor + 1, 0
    elif bump == "patch":
        return major, minor, patch + 1
    else:
        raise ValueError(f"Invalid bump type: {bump}")


class ClaudeCodeCreateVersionTool(DynamicTool):
    """Create a semantic version snapshot using git tags."""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service

    @property
    def tool_name(self) -> str:
        return "claude_code_create_version"

    @property
    def tool_description(self) -> str:
        return "Create a semantic version snapshot using git tags with auto-increment."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        """Build schema dynamically based on app_mode config."""
        properties = {}
        required = []

        # Only include workspace parameters if not in app mode with hidden params
        if not should_hide_workspace_params(self.tool_config):
            properties["workspace_id"] = adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Workspace identifier",
            )
            properties["workspace_type"] = adk_types.Schema(
                type=adk_types.Type.STRING,
                description="'session' or 'app'",
            )
            required.append("workspace_id")

        # Always include other parameters
        properties["bump"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Version bump type",
        )
        properties["description"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Version description",
        )

        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties=properties,
            required=required,
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """Create version snapshot with app_id override if configured."""
        user_id = get_user_id_from_context(tool_context)

        # Resolve workspace_id and workspace_type (applies app_mode overrides)
        try:
            workspace_id, workspace_type = resolve_workspace_params(
                args, tool_context, self.tool_config, default_workspace_type="session"
            )
        except ValueError as e:
            # Return error message to agent so it can adapt
            error_msg = str(e)
            log.warning(f"Workspace parameter resolution failed: {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "message": (
                    f"Claude Code tool is not available in this context: {error_msg}. "
                    "This tool is designed for use in app development workflows."
                )
            }

        bump = args.get("bump", "patch")
        description = args.get("description", "")

        log.info(
            f"Creating {bump} version for workspace {workspace_id} "
            f"(type: {workspace_type})"
        )

        # Get workspace path
        workspace_path = await self.workspace_service.get_workspace_path(
            workspace_id, user_id, workspace_type
        )

        if not workspace_path:
            return {
                "status": "error",
                "error": f"Workspace not found: {workspace_id}",
            }

        workspace_path_str = str(workspace_path)

        # Get latest version
        latest_tag = await get_latest_version_tag(workspace_path_str)

        if latest_tag:
            current_version = parse_version(latest_tag)
            log.debug(f"Current version: {latest_tag}")
        else:
            current_version = (0, 0, 0)
            log.debug("No existing version tags, starting at v0.0.0")

        # Bump version
        try:
            new_version = bump_version(current_version, bump)
            version_tag = f"v{new_version[0]}.{new_version[1]}.{new_version[2]}"
        except ValueError as e:
            log.warning(f"Invalid bump type: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": f"Invalid bump type '{bump}'. Valid options are: major, minor, patch"
            }

        log.info(f"Creating new version: {version_tag}")

        # Ensure everything is committed
        try:
            # Add all changes
            proc = await asyncio.create_subprocess_exec(
                "git",
                "add",
                "-A",
                cwd=workspace_path_str,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Check if there are changes to commit
            proc = await asyncio.create_subprocess_exec(
                "git",
                "diff",
                "--cached",
                "--quiet",
                cwd=workspace_path_str,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()

            # If there are staged changes (returncode != 0), commit them
            if proc.returncode != 0:
                commit_message = f"Version {version_tag}"
                if description:
                    commit_message += f": {description}"

                proc = await asyncio.create_subprocess_exec(
                    "git",
                    "commit",
                    "-m",
                    commit_message,
                    cwd=workspace_path_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

                if proc.returncode != 0:
                    return {
                        "status": "error",
                        "error": "Failed to commit changes before creating version",
                    }

            # Get current commit hash
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "HEAD",
                cwd=workspace_path_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            commit_hash = stdout.decode().strip() if stdout else ""

            # Create tag
            tag_message = description or f"Version {version_tag}"
            proc = await asyncio.create_subprocess_exec(
                "git",
                "tag",
                "-a",
                version_tag,
                "-m",
                tag_message,
                cwd=workspace_path_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return {
                    "status": "error",
                    "error": f"Failed to create git tag: {error_msg}",
                }

            # Get timestamp
            from datetime import datetime

            timestamp = datetime.now().timestamp()

            log.info(f"Successfully created version {version_tag}")

            return {
                "status": "success",
                "version": {
                    "version_number": f"{new_version[0]}.{new_version[1]}.{new_version[2]}",
                    "git_tag": version_tag,
                    "commit_hash": commit_hash,
                    "timestamp": timestamp,
                    "description": description,
                },
            }

        except Exception as e:
            log.exception(f"Failed to create version: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
