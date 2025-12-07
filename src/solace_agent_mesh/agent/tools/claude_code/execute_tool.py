"""
Claude Code Execute Tool.

Primary tool for executing Claude Code in a persistent workspace.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ....common.workspace import BaseWorkspaceService
from ....common.data_parts import AgentProgressUpdateData
from ...utils.context_helpers import get_host_component_from_tool_context
from ..dynamic_tool import DynamicTool
from .utils import (
    ensure_settings_directory,
    generate_claude_md,
    get_settings_path,
    run_claude_code_headless,
)

log = logging.getLogger(__name__)


def get_user_id_from_context(tool_context: Optional[ToolContext]) -> str:
    """Extract user ID from tool context."""
    if tool_context and hasattr(tool_context, "user_id"):
        return tool_context.user_id
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
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service
        self.session_store = session_store
        self.settings_base = settings_base

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
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "prompt": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Instruction for Claude Code",
                ),
                "workspace_id": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Unique workspace identifier",
                ),
                "workspace_type": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="'session' (temporary) or 'app' (persistent)",
                ),
                "environment": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="'node', 'python', or 'go'",
                ),
                "workspace_name": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Display name for workspace",
                ),
                "workspace_description": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Description for CLAUDE.md",
                ),
                "resume_session_id": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Claude Code session ID to resume (from previous response)",
                ),
            },
            required=["prompt", "workspace_id"],
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: Optional[ToolContext] = None,
        credential: Optional[str] = None,
    ) -> dict:
        """Execute Claude Code."""
        user_id = get_user_id_from_context(tool_context)
        workspace_id = args["workspace_id"]
        workspace_type = args.get("workspace_type", "session")
        environment = args.get("environment", "node")
        prompt = args["prompt"]

        log.info(
            f"Executing Claude Code for user {user_id}, "
            f"workspace {workspace_id}, type {workspace_type}"
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
            log.debug(f"Initializing workspace with CLAUDE.md and git")
            await self._initialize_workspace(
                workspace_path,
                environment,
                args.get("workspace_name", workspace_id),
                args.get("workspace_description", ""),
            )
            log.info(f"Workspace initialization complete")
        else:
            log.info(f"Using existing workspace at: {workspace_path}")

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

        # Save session ID for next invocation
        if result.get("session_id"):
            self.session_store[session_key] = result["session_id"]
            log.debug(f"Saved session ID for {session_key}")

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
