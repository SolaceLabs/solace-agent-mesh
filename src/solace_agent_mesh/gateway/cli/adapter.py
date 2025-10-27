"""
CLI Gateway Adapter for the Generic Gateway Framework.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from ..adapter.base import GatewayAdapter
from ..adapter.types import (
    AuthClaims,
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFilePart,
    SamTask,
    SamTextPart,
    SamUpdate,
)
from . import utils
from .repl import CliRepl

log = logging.getLogger(__name__)


class CliAdapterConfig(BaseModel):
    """Configuration model for the CLI adapter."""

    default_agent_name: str = Field(
        default="default", description="Default agent to send requests to."
    )
    prompt_style: str = Field(
        default="sam> ", description="The prompt string to display to the user."
    )
    auto_save_artifacts: bool = Field(
        default=True, description="Automatically save artifacts as they are created."
    )
    artifact_download_dir: Optional[str] = Field(
        default=None,
        description="Directory to save artifacts (defaults to current directory).",
    )


class CliAdapter(GatewayAdapter):
    """
    A simple CLI gateway adapter using a REPL interface with improved UX.

    Features:
    - Interactive REPL with prompt_toolkit
    - Separate input prompt from streaming output
    - Single-line status bar that updates in place (only shown when active)
    - Auto-save artifacts with compact notifications
    - Rich terminal UI with markdown rendering
    """

    ConfigModel = CliAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.repl: Optional[CliRepl] = None
        self.repl_task: Optional[asyncio.Task] = None
        self.console = Console()

        # State management
        self.current_task_id: Optional[str] = None
        self.content_lines: list[str] = []  # Accumulated content to display
        self.current_status: str = ""  # Current status message (empty when idle)
        self.current_text_buffer: str = ""  # Accumulate streaming text
        self.live_display: Optional[Live] = None
        self.user_id: str = "cli_user"  # Simple default user

        # Artifact tracking
        self.artifacts_in_progress: Dict[str, Dict[str, Any]] = {}

    async def init(self, context: GatewayContext) -> None:
        """Initialize the CLI adapter and start the REPL."""
        self.context = context
        adapter_config: CliAdapterConfig = context.adapter_config

        log.info("Initializing CLI Gateway Adapter...")

        # Create and start the REPL
        self.repl = CliRepl(adapter=self, prompt=adapter_config.prompt_style)

        # Start the REPL in a background task
        self.repl_task = asyncio.create_task(self.repl.start())

        log.info("CLI Gateway Adapter initialized and REPL started.")

    async def cleanup(self) -> None:
        """Stop the REPL and clean up resources."""
        log.info("Stopping CLI Gateway Adapter...")

        if self.repl:
            await self.repl.stop()

        if self.repl_task:
            try:
                await asyncio.wait_for(self.repl_task, timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("REPL task did not stop within timeout, cancelling...")
                self.repl_task.cancel()
                try:
                    await self.repl_task
                except asyncio.CancelledError:
                    pass

        if self.live_display:
            self.live_display.stop()

        log.info("CLI Gateway Adapter stopped.")

    async def extract_auth_claims(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """
        Extract authentication claims.

        For the CLI gateway, we use a simple default user.
        """
        return AuthClaims(
            id=self.user_id,
            source="cli",
            raw_context={"session_id": external_input.get("session_id")},
        )

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """
        Convert CLI input into a SamTask.

        Args:
            external_input: Dictionary with 'text' and 'session_id' keys

        Returns:
            SamTask ready for submission to the agent
        """
        text = external_input.get("text", "")
        session_id = external_input.get("session_id")

        if not text.strip():
            raise ValueError("No text content to send to agent")

        # Create a simple text task
        parts = [self.context.create_text_part(text)]

        adapter_config: CliAdapterConfig = self.context.adapter_config

        return SamTask(
            parts=parts,
            session_id=session_id,
            target_agent=adapter_config.default_agent_name,
            is_streaming=True,
            platform_context={
                "session_id": session_id,
            },
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle updates from the agent.

        We override this to batch text updates and manage the live display.
        """
        # Track the current task
        if self.current_task_id != context.task_id:
            self._reset_task_state(context.task_id)

        for part in update.parts:
            if isinstance(part, SamTextPart):
                await self.handle_text_chunk(part.text, context)
            elif isinstance(part, SamFilePart):
                await self.handle_file(part, context)
            elif isinstance(part, SamDataPart):
                # Check for special data part types
                if part.data.get("type") == "agent_progress_update":
                    status_text = part.data.get("status_text")
                    if status_text:
                        await self.handle_status_update(status_text, context)
                elif part.data.get("type") == "artifact_creation_progress":
                    await self._handle_artifact_progress(part, context)
                else:
                    await self.handle_data_part(part, context)

    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """
        Handle streaming text from the agent.

        Accumulates text and updates the live display.
        """
        self.current_text_buffer += text
        self._refresh_display()

    async def handle_file(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> None:
        """
        Handle file/artifact from the agent.

        Auto-saves the file if configured.
        """
        adapter_config: CliAdapterConfig = self.context.adapter_config

        if file_part.content_bytes and adapter_config.auto_save_artifacts:
            # Auto-save the file
            output_dir = (
                Path(adapter_config.artifact_download_dir)
                if adapter_config.artifact_download_dir
                else Path.cwd()
            )

            summary = await utils.auto_save_artifact(
                adapter=self,
                context=context,
                filename=file_part.name,
                content_bytes=file_part.content_bytes,
                version=1,  # File parts don't have versions
                output_dir=output_dir,
            )

            if summary:
                # Add summary to content
                self.content_lines.append(summary)
                self._refresh_display()
        else:
            # Just log that we received it
            log.debug(f"Received file part: {file_part.name} (not auto-saved)")

    async def handle_data_part(
        self, data_part: SamDataPart, context: ResponseContext
    ) -> None:
        """Handle structured data part from the agent."""
        # For the CLI, we can log unknown data parts
        log.debug(f"Received data part: {data_part.data.get('type', 'unknown')}")

    async def handle_status_update(
        self, status_text: str, context: ResponseContext
    ) -> None:
        """Handle agent status updates - shown in status bar."""
        self.current_status = f"⏳ {status_text}"
        self._refresh_display()

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Handle task completion."""
        # Flush any remaining text buffer to content
        if self.current_text_buffer.strip():
            self.content_lines.append(self.current_text_buffer)
            self.current_text_buffer = ""

        # Clear status
        self.current_status = ""

        # Add completion indicator
        self.content_lines.append("\n[green]✅ Task complete.[/green]\n")

        # Final refresh and stop live display
        self._refresh_display()
        if self.live_display and self.live_display.is_started:
            self.live_display.stop()
            self.live_display = None

        # Reset state
        self._reset_task_state(None)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Handle errors from the agent or gateway."""
        # Flush any remaining text buffer to content
        if self.current_text_buffer.strip():
            self.content_lines.append(self.current_text_buffer)
            self.current_text_buffer = ""

        # Clear status
        self.current_status = ""

        # Display error based on category
        if error.category == "CANCELED":
            self.content_lines.append("\n[yellow]🛑 Task canceled.[/yellow]\n")
        else:
            self.content_lines.append(f"\n[red]❌ Error: {error.message}[/red]\n")

        # Final refresh and stop live display
        self._refresh_display()
        if self.live_display and self.live_display.is_started:
            self.live_display.stop()
            self.live_display = None

        # Reset state
        self._reset_task_state(None)

    async def _handle_artifact_progress(
        self, part: SamDataPart, context: ResponseContext
    ) -> None:
        """Handle artifact creation progress updates."""
        status = part.data.get("status")
        filename = part.data.get("filename", "unknown file")
        adapter_config: CliAdapterConfig = self.context.adapter_config

        if status == "in-progress":
            bytes_transferred = part.data.get("bytes_transferred", 0)
            size_str = (
                utils.format_artifact_size(bytes_transferred)
                if bytes_transferred > 0
                else ""
            )

            # Update status bar
            if size_str:
                self.current_status = f"📄 Creating {filename} ({size_str})..."
            else:
                self.current_status = f"📄 Creating {filename}..."

            # Track this artifact
            self.artifacts_in_progress[filename] = {
                "version": part.data.get("version", 1),
                "description": part.data.get("description"),
            }

            self._refresh_display()

        elif status == "completed":
            version = part.data.get("version", 1)
            description = part.data.get("description")

            # Clear this from in-progress
            self.artifacts_in_progress.pop(filename, None)

            # Auto-save if enabled
            if adapter_config.auto_save_artifacts:
                try:
                    # Load the artifact content
                    content_bytes = await self.context.load_artifact_content(
                        context=context, filename=filename, version=version
                    )

                    if content_bytes:
                        output_dir = (
                            Path(adapter_config.artifact_download_dir)
                            if adapter_config.artifact_download_dir
                            else Path.cwd()
                        )

                        summary = await utils.auto_save_artifact(
                            adapter=self,
                            context=context,
                            filename=filename,
                            content_bytes=content_bytes,
                            version=version,
                            description=description,
                            output_dir=output_dir,
                        )

                        if summary:
                            # Flush text buffer if needed
                            if self.current_text_buffer.strip():
                                self.content_lines.append(self.current_text_buffer)
                                self.current_text_buffer = ""

                            # Add artifact summary to content
                            self.content_lines.append(summary)

                            # Clear status
                            self.current_status = ""

                            self._refresh_display()
                    else:
                        log.error(f"Failed to load content for artifact: {filename}")
                        self.content_lines.append(f"❌ Failed to load {filename}")
                        self._refresh_display()

                except Exception as e:
                    log.exception(f"Error auto-saving artifact {filename}: {e}")
                    self.content_lines.append(f"❌ Failed to save {filename}: {e}")
                    self._refresh_display()
            else:
                # Not auto-saving, just note completion
                self.content_lines.append(
                    f"✅ Artifact created: {filename} (v{version})"
                )
                self._refresh_display()

        elif status == "failed":
            self.artifacts_in_progress.pop(filename, None)
            self.content_lines.append(f"❌ Failed to create artifact: {filename}")
            self.current_status = ""
            self._refresh_display()

    def _reset_task_state(self, task_id: Optional[str]) -> None:
        """Reset state for a new task."""
        self.current_task_id = task_id
        self.content_lines = []
        self.current_text_buffer = ""
        self.current_status = ""
        self.artifacts_in_progress.clear()

    def _refresh_display(self) -> None:
        """Refresh the live display with current content and status."""
        # Build the renderable
        renderables = []

        # Add accumulated content lines
        if self.content_lines:
            for line in self.content_lines:
                if line.startswith("[") and "]" in line:
                    # It's a Rich markup line
                    renderables.append(Text.from_markup(line))
                else:
                    # Regular text
                    renderables.append(Text(line))

        # Add streaming text buffer (as markdown if not empty)
        if self.current_text_buffer.strip():
            try:
                renderables.append(Markdown(self.current_text_buffer))
            except Exception as e:
                # Fallback to plain text
                log.warning(f"Failed to render markdown: {e}")
                renderables.append(Text(self.current_text_buffer))

        # Add status bar if there's active status
        if self.current_status:
            renderables.append(Text())  # Blank line
            renderables.append(
                Panel(
                    Text(self.current_status, style="dim"),
                    border_style="dim",
                    padding=(0, 1),
                )
            )

        # Combine into a group
        display_group = Group(*renderables)

        # Start or update live display
        if not self.live_display or not self.live_display.is_started:
            self.live_display = Live(
                display_group,
                console=self.console,
                refresh_per_second=4,
                auto_refresh=True,
            )
            self.live_display.start()
        else:
            self.live_display.update(display_group)
