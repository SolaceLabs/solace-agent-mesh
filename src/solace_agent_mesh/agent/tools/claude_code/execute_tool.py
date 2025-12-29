"""
Claude Code Execute Tool.

Primary tool for executing Claude Code in a persistent workspace.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ....common.workspace import BaseWorkspaceService
from ....common.data_parts import AgentProgressUpdateData
from ....services.workspace import (
    WorkspaceManager,
    WorkspaceConfig,
    WorkspaceType,
    AppWorkspaceConfig,
)
from ...utils.context_helpers import get_host_component_from_tool_context, get_original_session_id
from ...utils.artifact_helpers import load_artifact_content_or_metadata
from ..dynamic_tool import DynamicTool
from .context_helpers import (
    resolve_workspace_params,
    should_hide_workspace_params,
)
from .utils import (
    ensure_settings_directory,
    generate_claude_md,
    get_settings_path,
    initialize_workspace_if_needed,
    run_claude_code_headless,
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

    # Fallback to a default user ID if context is not available
    return "default_user"


class ClaudeCodeExecuteTool(DynamicTool):
    """
    Execute Claude Code AI assistant in a persistent workspace.

    Claude Code autonomously reads files, writes code, runs tests, and verifies.
    Sessions persist automatically - just keep using the same workspace_id.
    """

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        session_store: Dict[str, str],
        settings_base: str,
        tool_config: Optional[Dict[str, Any]] = None,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service
        self.session_store = session_store
        self.settings_base = settings_base
        self.workspace_manager = workspace_manager

    @property
    def tool_name(self) -> str:
        return "claude_code_execute"

    @property
    def tool_description(self) -> str:
        return """Execute Claude Code AI assistant in a persistent workspace.
Claude Code autonomously reads files, writes code, runs tests, and verifies.
Sessions persist automatically - just keep using the same workspace_id."""

    @property
    def parameters_schema(self) -> adk_types.Schema:
        """Build schema dynamically based on app_mode config."""
        properties = {
            "prompt": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Instruction for Claude Code",
            ),
        }

        required = ["prompt"]

        # Only include workspace parameters if not in app mode with hidden params
        if not should_hide_workspace_params(self.tool_config):
            properties["workspace_id"] = adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Unique workspace identifier",
            )
            properties["workspace_type"] = adk_types.Schema(
                type=adk_types.Type.STRING,
                description="'session' (temporary) or 'app' (persistent)",
            )
            required.append("workspace_id")

        # Always include optional parameters that aren't workspace-related
        properties["environment"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="'node', 'python', or 'go'",
        )
        properties["workspace_name"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Display name for workspace",
        )
        properties["workspace_description"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Description for CLAUDE.md",
        )
        properties["resume_session_id"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Claude Code session ID to resume (from previous response)",
        )
        properties["artifacts"] = adk_types.Schema(
            type=adk_types.Type.ARRAY,
            items=adk_types.Schema(type=adk_types.Type.STRING),
            description="List of artifact filenames to copy to user_input/ directory before execution",
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
        """Execute Claude Code with app_id override if configured."""
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

        # Check for forced environment in tool_config, otherwise use LLM's choice or default
        if self.tool_config and "default_environment" in self.tool_config:
            environment = self.tool_config["default_environment"]
            log.info(f"Using forced environment from config: {environment}")
        else:
            environment = args.get("environment", "node")

        prompt = args["prompt"]

        # Append prompt_suffix from tool_config if configured
        # This allows adding instructions like APP_CONTEXT.md maintenance to every prompt
        if self.tool_config and "prompt_suffix" in self.tool_config:
            prompt_suffix = self.tool_config["prompt_suffix"]
            if prompt_suffix:
                prompt = f"{prompt}\n\n{prompt_suffix}"
                log.debug(f"Appended prompt_suffix from tool_config ({len(prompt_suffix)} chars)")

        log.info(
            f"Executing Claude Code for user {user_id}, "
            f"workspace {workspace_id}, type {workspace_type}, environment {environment}"
        )

        # Get or create workspace
        workspace_path = await self.workspace_service.get_workspace_path(
            workspace_id, user_id, workspace_type
        )

        if not workspace_path:
            # Create new workspace
            log.info(f"Creating new workspace: {workspace_id} (type: {workspace_type})")
            workspace_path = await self.workspace_service.create_workspace(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type,
                metadata={
                    "environment": environment,
                    "name": args.get("workspace_name", workspace_id),
                    "description": args.get("workspace_description", ""),
                },
            )
            log.info(f"Workspace created at: {workspace_path}")

            # Initialize workspace with CLAUDE.md and git
            # Skip for SAM apps - the container template handles this via init-workspace.sh
            if workspace_type != "app":
                log.debug(f"Initializing workspace with CLAUDE.md and git")
                await self._initialize_workspace(
                    workspace_path,
                    environment,
                    args.get("workspace_name", workspace_id),
                    args.get("workspace_description", ""),
                )
                log.info(f"Workspace initialization complete")
            else:
                log.debug(f"Skipping _initialize_workspace for SAM app (handled by container template)")
        else:
            log.info(f"Using existing workspace at: {workspace_path}")

        # Create workspace config for WorkspaceManager (if available)
        workspace_config = None
        if self.workspace_manager:
            # Map workspace_type string to WorkspaceType enum
            ws_type = WorkspaceType.APP if workspace_type == "app" else WorkspaceType.GENERIC
            workspace_config = WorkspaceConfig(
                type=ws_type,
                user_id=user_id,
                workspace_id=workspace_id,
                workspace_name=args.get("workspace_name", workspace_id),
                app_config=AppWorkspaceConfig(sync_dist=True) if ws_type == WorkspaceType.APP else None,
            )

            # Initialize workspace from persistent storage (downloads tarball, copies template)
            try:
                log.info(f"Initializing workspace from persistent storage")
                await self.workspace_manager.initialize(workspace_config, workspace_path)
                log.info(f"Workspace initialization from storage complete")
            except Exception as e:
                log.error(f"Failed to initialize workspace from storage: {e}")
                # Continue anyway - workspace might be usable without tarball

        # Initialize workspace using container init script if needed
        # This is especially important for SAM apps which need the template copied
        # Note: This runs even with WorkspaceManager because the template is inside
        # the container image, not accessible from the host where WorkspaceManager runs
        try:
            was_initialized = await initialize_workspace_if_needed(
                workspace_path=workspace_path,
                workspace_type=workspace_type,
                workspace_id=workspace_id,
                workspace_name=args.get("workspace_name", workspace_id),
                environment=environment,
                tool_config=self.tool_config,
            )
            if was_initialized:
                log.info(f"Workspace initialized from container template")
        except Exception as e:
            log.error(f"Failed to initialize workspace: {e}")
            # Continue anyway - Claude Code might still work without template

        # Copy artifacts to user_input/ directory if provided
        artifacts = args.get("artifacts", [])
        copied_artifacts = []
        if artifacts and tool_context:
            copied_artifacts = await self._copy_artifacts_to_workspace(
                artifacts=artifacts,
                workspace_path=workspace_path,
                tool_context=tool_context,
            )
            if copied_artifacts:
                log.info(f"Copied {len(copied_artifacts)} artifacts to user_input/")

        # Get session ID for this workspace
        # Priority: 1) Explicit resume_session_id from LLM, 2) Stored session_id
        session_key = f"{user_id}/{workspace_id}"
        resume_session_id = args.get("resume_session_id")

        if resume_session_id:
            # LLM explicitly wants to resume this session
            session_id = resume_session_id
            log.info(f"Resuming Claude Code session: {session_id}")
        else:
            # Use stored session for this workspace (if any)
            session_id = self.session_store.get(session_key)
            if session_id:
                log.debug(f"Found stored session for workspace: {session_id}")

        # Ensure settings directory exists
        settings_path = get_settings_path(self.settings_base, user_id, workspace_id)
        ensure_settings_directory(settings_path, self.tool_config, workspace_id)

        # Check if streaming is enabled (from tool config, defaults to True)
        enable_streaming = self.tool_config.get("enable_streaming", True) if self.tool_config else True

        # Create status callback if streaming is enabled
        status_callback = None
        if enable_streaming and tool_context:
            # Get the a2a_context and host_component for status updates
            a2a_context = tool_context.state.get("a2a_context") if hasattr(tool_context, 'state') else None
            host_component = get_host_component_from_tool_context(tool_context)

            def status_callback_impl(event_type: str, event_data: dict):
                """Publish status updates using SAM mechanism if available, otherwise log."""
                # Format message with "Coding tool: " prefix
                message = event_data.get('message', '')
                prefixed_message = f"Coding tool: {message}"

                # Try to publish via SAM status update mechanism
                if a2a_context and host_component:
                    try:
                        progress_data = AgentProgressUpdateData(status_text=prefixed_message)
                        success = host_component.publish_data_signal_from_thread(
                            a2a_context=a2a_context,
                            signal_data=progress_data,
                            skip_buffer_flush=False,
                            log_identifier="[ClaudeCode]",
                        )
                        if success:
                            log.debug(f"[Claude Code] Published status: {prefixed_message}")
                        else:
                            log.info(f"[Claude Code] {prefixed_message} (publish failed)")
                    except Exception as e:
                        log.warning(f"[Claude Code] Failed to publish status update: {e}")
                        log.info(f"[Claude Code] {prefixed_message}")
                else:
                    # Fall back to logging if SAM context not available (e.g., in tests)
                    log.info(f"[Claude Code] {prefixed_message}")

            status_callback = status_callback_impl

        # Execute Claude Code
        try:
            result = await run_claude_code_headless(
                workspace_path=workspace_path,
                settings_path=settings_path,
                prompt=prompt,
                environment=environment,
                tool_config=self.tool_config,
                session_id=session_id,
                resume_session=bool(resume_session_id),  # Only resume if explicitly requested
                stream=enable_streaming,
                status_callback=status_callback,
            )
        except RuntimeError as e:
            # Handle container runtime not found or other runtime errors
            error_msg = str(e)
            log.error(f"Claude Code execution failed: {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "message": f"Failed to execute Claude Code: {error_msg}"
            }
        except Exception as e:
            # Handle any other unexpected errors
            error_msg = str(e)
            log.exception(f"Unexpected error during Claude Code execution: {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "message": f"Claude Code execution failed with unexpected error: {error_msg}"
            }

        # For app-mode workspaces, validate VERSION file and retry once if invalid
        if workspace_type == "app" and result.get("status") != "error":
            is_valid, validation_error = self._validate_version_file(workspace_path)

            if not is_valid:
                log.warning(
                    f"VERSION file validation failed after execution: {validation_error}. "
                    "Retrying with instruction to run build_and_version.sh"
                )

                # Retry once with explicit instruction to run the build script
                retry_prompt = (
                    "IMPORTANT: The VERSION file is missing or invalid. "
                    "You MUST run './build_and_version.sh patch' to create a valid VERSION file. "
                    "Do this now - it will build the app and create the proper VERSION file."
                )

                try:
                    # Use the session from the first run for continuity
                    retry_session_id = result.get("session_id") or session_id

                    retry_result = await run_claude_code_headless(
                        workspace_path=workspace_path,
                        settings_path=settings_path,
                        prompt=retry_prompt,
                        environment=environment,
                        tool_config=self.tool_config,
                        session_id=retry_session_id,
                        resume_session=True,
                        stream=enable_streaming,
                        status_callback=status_callback,
                    )

                    # Check validation again after retry
                    is_valid_after_retry, retry_validation_error = self._validate_version_file(workspace_path)

                    if is_valid_after_retry:
                        log.info("VERSION file is now valid after retry")
                        # Use retry result but keep original output for context
                        result["session_id"] = retry_result.get("session_id", retry_session_id)
                        result["version_retry"] = "success"
                    else:
                        log.warning(
                            f"VERSION file still invalid after retry: {retry_validation_error}"
                        )
                        result["version_warning"] = (
                            f"VERSION file is invalid: {retry_validation_error}. "
                            "Please run './build_and_version.sh patch' manually."
                        )
                        result["version_retry"] = "failed"

                except Exception as retry_error:
                    log.error(f"Retry execution failed: {retry_error}")
                    result["version_warning"] = (
                        f"VERSION file is invalid ({validation_error}) and retry failed. "
                        "Please run './build_and_version.sh patch' manually."
                    )
                    result["version_retry"] = "error"

        # Save session ID for next invocation
        if result.get("session_id"):
            self.session_store[session_key] = result["session_id"]
            log.debug(f"Saved session ID for {session_key}")

        # Finalize workspace: upload tarball and sync dist/ to app storage
        if self.workspace_manager and workspace_config:
            try:
                log.info(f"Finalizing workspace to persistent storage")
                await self.workspace_manager.finalize(workspace_config, workspace_path)
                log.info(f"Workspace finalization complete")
            except Exception as e:
                log.error(f"Failed to finalize workspace to storage: {e}")
                # Don't fail the whole operation - Claude Code already completed

        # Add workspace information to result
        result["workspace_id"] = workspace_id
        result["workspace_path"] = str(workspace_path)
        result["workspace_type"] = workspace_type

        return result

    async def _initialize_workspace(
        self,
        workspace_path: Path,
        environment: str,
        workspace_name: str,
        workspace_description: str,
    ) -> None:
        """
        Initialize a new workspace with CLAUDE.md and git repository.

        Args:
            workspace_path: Path to workspace directory
            environment: Environment name
            workspace_name: Display name
            workspace_description: Description
        """
        import asyncio

        log.info(f"Initializing workspace at {workspace_path}")

        # Create CLAUDE.md
        claude_md_content = generate_claude_md(
            workspace_name, workspace_description, environment
        )
        claude_md_path = workspace_path / "CLAUDE.md"
        claude_md_path.write_text(claude_md_content)
        log.debug(f"Created CLAUDE.md at {claude_md_path}")

        # Initialize git repository
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "init",
                cwd=str(workspace_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                # Configure git
                await asyncio.create_subprocess_exec(
                    "git",
                    "config",
                    "user.name",
                    "Claude Code",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "git",
                    "config",
                    "user.email",
                    "cc@workspace",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "git",
                    "config",
                    "init.defaultBranch",
                    "main",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                # Initial commit
                await asyncio.create_subprocess_exec(
                    "git",
                    "add",
                    "CLAUDE.md",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.create_subprocess_exec(
                    "git",
                    "commit",
                    "-m",
                    "Initial commit: Add CLAUDE.md",
                    cwd=str(workspace_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                log.debug("Initialized git repository")
        except Exception as e:
            log.warning(f"Failed to initialize git repository: {e}")

    async def _copy_artifacts_to_workspace(
        self,
        artifacts: List[str],
        workspace_path: Path,
        tool_context: ToolContext,
    ) -> List[str]:
        """
        Copy artifacts from artifact storage to workspace user_input/ directory.

        Args:
            artifacts: List of artifact filenames to copy
            workspace_path: Path to workspace directory
            tool_context: Tool context for accessing artifact service

        Returns:
            List of successfully copied artifact filenames
        """
        # Create user_input directory
        user_input_dir = workspace_path / "user_input"
        user_input_dir.mkdir(parents=True, exist_ok=True)

        # Get artifact service and context from tool_context
        inv_context = tool_context._invocation_context
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not artifact_service:
            log.warning("No artifact service available, cannot copy artifacts")
            return []

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)

        if not all([app_name, user_id, session_id]):
            log.warning(
                f"Missing context for artifact loading: app_name={app_name}, "
                f"user_id={user_id}, session_id={session_id}"
            )
            return []

        copied_files = []

        for filename in artifacts:
            try:
                log.debug(f"Loading artifact: {filename}")
                result = await load_artifact_content_or_metadata(
                    artifact_service=artifact_service,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    version="latest",
                    return_raw_bytes=True,
                    log_identifier_prefix="[ClaudeCode:artifact]",
                )

                if result.get("status") == "success" and "raw_bytes" in result:
                    file_path = user_input_dir / filename
                    # Ensure parent directories exist for nested filenames
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(result["raw_bytes"])
                    copied_files.append(filename)
                    log.info(
                        f"Copied artifact '{filename}' to {file_path} "
                        f"({result.get('size_bytes', 0)} bytes)"
                    )
                else:
                    error_msg = result.get("message", "Unknown error")
                    log.warning(f"Failed to load artifact '{filename}': {error_msg}")

            except Exception as e:
                log.error(f"Error copying artifact '{filename}': {e}")

        return copied_files

    def _validate_version_file(self, workspace_path: Path) -> Tuple[bool, str]:
        """
        Validate that VERSION file exists and is valid JSON with required fields.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Tuple of (is_valid, error_message)
        """
        version_file = workspace_path / "VERSION"

        if not version_file.exists():
            return False, "VERSION file does not exist"

        try:
            with open(version_file) as f:
                content = f.read().strip()
                if not content:
                    return False, "VERSION file is empty"

                version_data = json.loads(content)

                if not isinstance(version_data, dict):
                    return False, "VERSION file is not a JSON object"

                if "version" not in version_data:
                    return False, "VERSION file missing 'version' field"

                # Check version is a valid semver-like string
                version_str = version_data.get("version", "")
                if not version_str or not isinstance(version_str, str):
                    return False, "VERSION file has invalid 'version' value"

                return True, ""

        except json.JSONDecodeError as e:
            return False, f"VERSION file is not valid JSON: {e}"
        except Exception as e:
            return False, f"Failed to read VERSION file: {e}"
