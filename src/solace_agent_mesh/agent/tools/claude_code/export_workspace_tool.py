"""
Claude Code Export Workspace Tool.

Export workspace as tar.gz artifact with metadata.
"""

import asyncio
import hashlib
import json
import logging
import tempfile
from datetime import datetime
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


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class ClaudeCodeExportWorkspaceTool(DynamicTool):
    """Export workspace as tar.gz artifact."""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service

    @property
    def tool_name(self) -> str:
        return "claude_code_export_workspace"

    @property
    def tool_description(self) -> str:
        return "Export workspace as tar.gz artifact with metadata."

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
                "include_git_history": adk_types.Schema(
                    type=adk_types.Type.BOOLEAN,
                    description="Include .git directory in export",
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
        """Export workspace."""
        user_id = get_user_id_from_context(tool_context)
        workspace_id = args["workspace_id"]
        workspace_type = args.get("workspace_type", "session")
        include_git = args.get("include_git_history", True)

        log.info(f"Exporting workspace {workspace_id} (type: {workspace_type})")

        # Get workspace path
        workspace_path = await self.workspace_service.get_workspace_path(
            workspace_id, user_id, workspace_type
        )

        if not workspace_path:
            return {
                "status": "error",
                "error": f"Workspace not found: {workspace_id}",
            }

        # Get workspace metadata
        metadata = await self.workspace_service.get_metadata(
            workspace_id, user_id, workspace_type
        )

        # Create export metadata
        export_metadata = {
            "workspace_id": workspace_id,
            "workspace_type": workspace_type,
            "environment": metadata.get("environment", "node") if metadata else "node",
            "exported_at": datetime.now().timestamp(),
            "exported_by": user_id,
            "include_git_history": include_git,
        }

        # Get latest version if exists
        if include_git:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git",
                    "describe",
                    "--tags",
                    "--always",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    export_metadata["version"] = stdout.decode().strip()
            except Exception as e:
                log.debug(f"Failed to get git version: {e}")

        # Create temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a staging directory with both workspace and metadata
            staging_dir = temp_path / "staging"
            staging_dir.mkdir()

            # Copy metadata into staging directory
            metadata_file = staging_dir / "metadata.json"
            metadata_file.write_text(json.dumps(export_metadata, indent=2))

            # Create symlink to workspace in staging directory
            workspace_link = staging_dir / workspace_path.name
            try:
                workspace_link.symlink_to(workspace_path)
            except Exception as e:
                # If symlink fails (e.g., on Windows), use hard copy
                log.debug(f"Symlink failed, will use direct tar: {e}")

            # Create archive
            archive_name = f"{workspace_id}.tar.gz"
            archive_path = temp_path / archive_name

            # Build tar command to archive both workspace and metadata
            if workspace_link.exists():
                # Use staging directory with symlink (-h to dereference)
                tar_cmd = [
                    "tar",
                    "-czf",
                    str(archive_path),
                    "-h",  # Dereference symlinks
                ]

                # Exclude .git if not including history (must come before -C)
                if not include_git:
                    tar_cmd.extend(["--exclude", f"{workspace_path.name}/.git"])

                tar_cmd.extend([
                    "-C",
                    str(staging_dir),
                    "metadata.json",
                    workspace_path.name,
                ])
            else:
                # Direct archive without symlink
                tar_cmd = [
                    "tar",
                    "-czf",
                    str(archive_path),
                ]

                # Exclude .git if not including history (must come before -C)
                if not include_git:
                    tar_cmd.extend(["--exclude", f"{workspace_path.name}/.git"])

                tar_cmd.extend([
                    "-C",
                    str(staging_dir),
                    "metadata.json",
                    "-C",
                    str(workspace_path.parent),
                    workspace_path.name,
                ])

            log.debug(f"Creating archive: {' '.join(tar_cmd)}")

            proc = await asyncio.create_subprocess_exec(
                *tar_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return {
                    "status": "error",
                    "error": f"Failed to create archive: {error_msg}",
                }

            # Calculate checksum
            checksum = calculate_checksum(archive_path)
            size_bytes = archive_path.stat().st_size

            # Move archive to a more permanent location
            # TODO: Integrate with artifact service
            # For now, move to a local export directory
            export_base = Path(self.tool_config.get("export_base", "/tmp/claude-exports"))
            export_base.mkdir(parents=True, exist_ok=True)
            export_user_dir = export_base / user_id
            export_user_dir.mkdir(parents=True, exist_ok=True)

            final_archive_path = export_user_dir / archive_name
            archive_path.rename(final_archive_path)

            artifact_uri = f"file://{final_archive_path}"

            log.info(
                f"Successfully exported workspace {workspace_id} "
                f"to {final_archive_path} ({size_bytes} bytes)"
            )

            return {
                "status": "success",
                "artifact_uri": artifact_uri,
                "size_bytes": size_bytes,
                "checksum": checksum,
            }
