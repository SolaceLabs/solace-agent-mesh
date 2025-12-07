"""
Claude Code Import Workspace Tool.

Import workspace from tar.gz artifact.
"""

import asyncio
import json
import logging
import tempfile
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


class ClaudeCodeImportWorkspaceTool(DynamicTool):
    """Import workspace from tar.gz artifact."""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        tool_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service

    @property
    def tool_name(self) -> str:
        return "claude_code_import_workspace"

    @property
    def tool_description(self) -> str:
        return "Import workspace from tar.gz artifact, optionally renaming it."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "artifact_uri": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="URI to workspace archive (file:// or artifact://)",
                ),
                "new_workspace_id": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Optional new workspace ID (renames on import)",
                ),
            },
            required=["artifact_uri"],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """Import workspace."""
        user_id = get_user_id_from_context(tool_context)
        artifact_uri = args["artifact_uri"]
        new_workspace_id = args.get("new_workspace_id")

        log.info(f"Importing workspace from {artifact_uri}")

        # Parse artifact URI
        if artifact_uri.startswith("file://"):
            archive_path = Path(artifact_uri[7:])
        else:
            # TODO: Support artifact:// URIs via artifact service
            return {
                "status": "error",
                "error": f"Unsupported artifact URI scheme: {artifact_uri}",
            }

        if not archive_path.exists():
            return {
                "status": "error",
                "error": f"Archive not found: {archive_path}",
            }

        # Extract to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            log.debug(f"Extracting archive to {temp_path}")

            # Extract archive
            proc = await asyncio.create_subprocess_exec(
                "tar",
                "-xzf",
                str(archive_path),
                "-C",
                str(temp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return {
                    "status": "error",
                    "error": f"Failed to extract archive: {error_msg}",
                }

            # Read metadata
            metadata_file = temp_path / "metadata.json"
            if not metadata_file.exists():
                return {
                    "status": "error",
                    "error": "Archive does not contain metadata.json",
                }

            try:
                original_metadata = json.loads(metadata_file.read_text())
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "error": f"Failed to parse metadata.json: {e}",
                }

            # Determine workspace ID and type
            workspace_id = new_workspace_id or original_metadata.get("workspace_id")
            workspace_type = original_metadata.get("workspace_type", "session")

            if not workspace_id:
                return {
                    "status": "error",
                    "error": "Could not determine workspace_id from archive or parameters",
                }

            log.info(
                f"Importing as workspace {workspace_id} (type: {workspace_type})"
            )

            # Check if workspace already exists
            existing_path = await self.workspace_service.get_workspace_path(
                workspace_id, user_id, workspace_type
            )

            if existing_path:
                return {
                    "status": "error",
                    "error": f"Workspace already exists: {workspace_id}",
                }

            # Find the extracted workspace directory
            # The archive contains workspace_name directory and metadata.json
            extracted_workspace = None
            for item in temp_path.iterdir():
                if item.is_dir() and item.name != "__MACOSX":
                    extracted_workspace = item
                    break

            if not extracted_workspace:
                return {
                    "status": "error",
                    "error": "Could not find workspace directory in archive",
                }

            # Create workspace via service
            workspace_path = await self.workspace_service.create_workspace(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type,
                metadata={
                    "environment": original_metadata.get("environment", "node"),
                    "name": workspace_id,
                    "description": f"Imported from {artifact_uri}",
                    "imported_at": original_metadata.get("exported_at"),
                    "original_workspace_id": original_metadata.get("workspace_id"),
                },
            )

            # Move extracted files to workspace
            import shutil

            try:
                # Remove the empty workspace directory created by create_workspace
                workspace_path.rmdir()

                # Move extracted workspace to final location
                shutil.move(str(extracted_workspace), str(workspace_path))

                log.info(
                    f"Successfully imported workspace {workspace_id} to {workspace_path}"
                )

                return {
                    "status": "success",
                    "workspace_id": workspace_id,
                    "workspace_type": workspace_type,
                    "workspace_path": str(workspace_path),
                    "original_metadata": original_metadata,
                }

            except Exception as e:
                # Clean up on failure
                try:
                    await self.workspace_service.delete_workspace(
                        workspace_id, user_id, workspace_type
                    )
                except Exception:
                    pass

                log.exception(f"Failed to import workspace: {e}")
                return {
                    "status": "error",
                    "error": f"Failed to import workspace: {e}",
                }
