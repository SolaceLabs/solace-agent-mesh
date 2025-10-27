"""
CLI Gateway Adapter using pure prompt_toolkit.

This version uses only prompt_toolkit for all terminal I/O,
providing better compatibility with VS Code and other terminals.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import clear
from pydantic import BaseModel, Field
from rich.table import Table

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

log = logging.getLogger(__name__)


class CliPtAdapterConfig(BaseModel):
    """Configuration model for the CLI prompt_toolkit adapter."""

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


class CliPtAdapter(GatewayAdapter):
    """
    A CLI gateway adapter using pure prompt_toolkit.

    Features:
    - Interactive REPL with bottom toolbar for status
    - Clean separation of output and input
    - Streaming responses with proper formatting
    - Auto-save artifacts with compact notifications
    - Works perfectly in VS Code terminal
    """

    ConfigModel = CliPtAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.prompt_session: Optional[PromptSession] = None
        self.repl_task: Optional[asyncio.Task] = None
        self.user_id: str = "cli_user"
        self.session_id: str = utils.create_cli_session_id()

        # State management
        self.current_task_id: Optional[str] = None
        self.current_status: str = ""  # For bottom toolbar
        self.running: bool = False

        # Command registry
        self.commands: Dict[str, Callable] = {}

    async def init(self, context: GatewayContext) -> None:
        """Initialize the CLI adapter and start the REPL."""
        self.context = context
        adapter_config: CliPtAdapterConfig = context.adapter_config

        log.info("Initializing CLI Gateway Adapter (prompt_toolkit)...")

        # Register commands
        self._register_commands()

        # Create prompt session with bottom toolbar
        self.prompt_session = PromptSession(
            message=adapter_config.prompt_style,
            bottom_toolbar=self._get_toolbar,
        )

        # Start the REPL in a background task
        self.repl_task = asyncio.create_task(self._run_repl())

        log.info("CLI Gateway Adapter initialized and REPL started.")

    async def cleanup(self) -> None:
        """Stop the REPL and clean up resources."""
        log.info("Stopping CLI Gateway Adapter...")

        self.running = False

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

        log.info("CLI Gateway Adapter stopped.")

    def _get_toolbar(self) -> FormattedText:
        """Get the bottom toolbar content (status bar)."""
        if self.current_status:
            return HTML(f"<ansiblue>{self.current_status}</ansiblue>")
        return FormattedText("")

    def _register_commands(self):
        """Register slash commands."""
        self.commands = {
            "help": self._cmd_help,
            "artifacts": self._cmd_artifacts,
            "download": self._cmd_download,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }

    async def _run_repl(self):
        """Main REPL loop."""
        self.running = True
        self.processing = False  # Track if we're processing a task
        utils.print_welcome()

        try:
            while self.running:
                try:
                    # Only prompt when NOT processing
                    if not self.processing:
                        with patch_stdout():
                            # Read user input
                            user_input = await self.prompt_session.prompt_async()

                        if not user_input:
                            continue

                        user_input = user_input.strip()

                        if not user_input:
                            continue

                        # Check if it's a slash command
                        if user_input.startswith("/"):
                            await self._handle_command(user_input)
                        else:
                            # Regular message - mark as processing
                            self.processing = True
                            # Send to agent (this will trigger callbacks)
                            await self._handle_message(user_input)
                            # Processing flag will be cleared by handle_task_complete or handle_error
                    else:
                        # If we're processing, just wait a bit
                        await asyncio.sleep(0.1)

                except KeyboardInterrupt:
                    # Ctrl+C - just print newline and continue
                    print_formatted_text()
                    continue
                except EOFError:
                    # Ctrl+D
                    break
                except Exception as e:
                    log.exception(f"Error in REPL loop: {e}")
                    utils.print_error(f"An unexpected error occurred: {e}")
                    self.processing = False  # Reset on error

        finally:
            utils.print_goodbye()

    async def _handle_command(self, command_line: str):
        """Handle a slash command."""
        parts = command_line[1:].split(maxsplit=1)
        command_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command_name in self.commands:
            handler = self.commands[command_name]
            try:
                await handler(args)
            except Exception as e:
                log.exception(f"Error executing command '{command_name}': {e}")
                utils.print_error(f"Command failed: {e}")
        else:
            utils.print_error(
                f"Unknown command: /{command_name}. Type /help for available commands."
            )

    async def _handle_message(self, message: str):
        """Handle a regular message by sending it to the agent."""
        try:
            external_input = {
                "text": message,
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await self.context.handle_external_input(external_input)
        except Exception as e:
            log.exception(f"Error handling message: {e}")
            utils.print_error(f"Failed to process message: {e}")

    # --- Command Handlers ---

    async def _cmd_help(self, args: str):
        """Display help information."""
        print_formatted_text(HTML(
            "\n<b>Available Commands:</b>\n\n"
            "- <b>/help</b> - Show this help message\n"
            "- <b>/artifacts</b> - List artifacts in the current session\n"
            "- <b>/download &lt;filename&gt;</b> - Download an artifact\n"
            "- <b>/exit</b> or <b>/quit</b> - Exit the CLI gateway\n\n"
            "<b>Usage:</b>\n\n"
            "Type any message to send it to the agent. Artifacts are\n"
            "automatically saved to the current directory.\n"
        ))

    async def _cmd_artifacts(self, args: str):
        """List all artifacts in the current session."""
        try:
            context = ResponseContext(
                task_id=f"cli-list-artifacts-{datetime.utcnow().timestamp()}",
                session_id=self.session_id,
                user_id=self.user_id,
                platform_context={},
            )

            artifacts = await self.context.list_artifacts(context)

            if not artifacts:
                print_formatted_text(HTML("\n<ansiyellow>No artifacts found in this session.</ansiyellow>\n"))
                return

            # Use Rich table for nice formatting
            from rich.console import Console
            table = Table(title=f"Artifacts ({len(artifacts)} found)")
            table.add_column("Filename", style="cyan", no_wrap=True)
            table.add_column("Version", style="magenta")
            table.add_column("Description", style="white")
            table.add_column("Modified", style="dim")

            for artifact in artifacts:
                modified_str = "N/A"
                if artifact.last_modified:
                    try:
                        dt_obj = datetime.fromisoformat(
                            artifact.last_modified.replace("Z", "+00:00")
                        )
                        modified_str = dt_obj.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        modified_str = artifact.last_modified

                description = artifact.description or "No description"
                if len(description) > 60:
                    description = description[:57] + "..."

                table.add_row(
                    artifact.filename,
                    str(artifact.version),
                    description,
                    modified_str,
                )

            console = Console()
            console.print()
            console.print(table)
            console.print()

        except Exception as e:
            log.exception(f"Error listing artifacts: {e}")
            utils.print_error(f"Failed to list artifacts: {e}")

    async def _cmd_download(self, args: str):
        """Download an artifact to the current directory."""
        if not args:
            utils.print_error("Usage: /download <filename> [version]")
            return

        parts = args.split()
        filename = parts[0]
        version = parts[1] if len(parts) > 1 else "latest"

        try:
            context = ResponseContext(
                task_id=f"cli-download-{datetime.utcnow().timestamp()}",
                session_id=self.session_id,
                user_id=self.user_id,
                platform_context={},
            )

            content_bytes = await self.context.load_artifact_content(
                context=context, filename=filename, version=version
            )

            if not content_bytes:
                utils.print_error(f"Could not retrieve content for: {filename}")
                return

            output_path = Path.cwd() / filename
            output_path.write_bytes(content_bytes)

            size_str = utils.format_artifact_size(len(content_bytes))
            print_formatted_text(HTML(
                f"<ansigreen>✅ Downloaded {filename} ({size_str}) to {output_path}</ansigreen>"
            ))

        except Exception as e:
            log.exception(f"Error downloading artifact: {e}")
            utils.print_error(f"Failed to download artifact: {e}")

    async def _cmd_exit(self, args: str):
        """Exit the CLI gateway."""
        self.running = False

    # --- GatewayAdapter Implementation ---

    async def extract_auth_claims(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """Extract authentication claims (simple default user for CLI)."""
        return AuthClaims(
            id=self.user_id,
            source="cli",
            raw_context={"session_id": external_input.get("session_id")},
        )

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """Convert CLI input into a SamTask."""
        text = external_input.get("text", "")
        session_id = external_input.get("session_id")

        if not text.strip():
            raise ValueError("No text content to send to agent")

        parts = [self.context.create_text_part(text)]
        adapter_config: CliPtAdapterConfig = self.context.adapter_config

        return SamTask(
            parts=parts,
            session_id=session_id,
            target_agent=adapter_config.default_agent_name,
            is_streaming=True,
            platform_context={"session_id": session_id},
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """Handle updates from the agent."""
        if self.current_task_id != context.task_id:
            self.current_task_id = context.task_id

        for part in update.parts:
            if isinstance(part, SamTextPart):
                await self.handle_text_chunk(part.text, context)
            elif isinstance(part, SamFilePart):
                await self.handle_file(part, context)
            elif isinstance(part, SamDataPart):
                if part.data.get("type") == "agent_progress_update":
                    status_text = part.data.get("status_text")
                    if status_text:
                        await self.handle_status_update(status_text, context)
                elif part.data.get("type") == "artifact_creation_progress":
                    await self._handle_artifact_progress(part, context)

    async def handle_text_chunk(self, text: str, context: ResponseContext) -> None:
        """Handle streaming text from the agent."""
        # Use sys.stdout directly with flush for better streaming compatibility
        import sys
        sys.stdout.write(text)
        sys.stdout.flush()

    async def handle_file(self, file_part: SamFilePart, context: ResponseContext) -> None:
        """Handle file/artifact from the agent."""
        adapter_config: CliPtAdapterConfig = self.context.adapter_config

        if file_part.content_bytes and adapter_config.auto_save_artifacts:
            output_dir = (
                Path(adapter_config.artifact_download_dir)
                if adapter_config.artifact_download_dir
                else Path.cwd()
            )

            summary = await utils.auto_save_artifact(
                context=context,
                filename=file_part.name,
                content_bytes=file_part.content_bytes,
                version=1,
                output_dir=output_dir,
            )

            if summary:
                print_formatted_text(HTML(f"<ansigreen>{summary}</ansigreen>"))

    async def handle_status_update(self, status_text: str, context: ResponseContext) -> None:
        """Handle agent status updates - shown in bottom toolbar."""
        self.current_status = f"⏳ {status_text}"
        # The toolbar will update automatically

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """Handle task completion."""
        self.current_status = ""  # Clear status
        print_formatted_text(HTML("\n<ansigreen><b>✅ Task complete.</b></ansigreen>\n"))
        self.current_task_id = None
        self.processing = False  # Allow prompt to show again

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """Handle errors from the agent or gateway."""
        self.current_status = ""  # Clear status

        if error.category == "CANCELED":
            print_formatted_text(HTML("\n<ansiyellow>🛑 Task canceled.</ansiyellow>\n"))
        else:
            print_formatted_text(HTML(f"\n<ansired>❌ Error: {error.message}</ansired>\n"))

        self.current_task_id = None
        self.processing = False  # Allow prompt to show again

    async def _handle_artifact_progress(self, part: SamDataPart, context: ResponseContext) -> None:
        """Handle artifact creation progress updates."""
        status = part.data.get("status")
        filename = part.data.get("filename", "unknown file")
        adapter_config: CliPtAdapterConfig = self.context.adapter_config

        if status == "in-progress":
            bytes_transferred = part.data.get("bytes_transferred", 0)
            if bytes_transferred > 0:
                size_str = utils.format_artifact_size(bytes_transferred)
                self.current_status = f"📄 Creating {filename} ({size_str})..."
            else:
                self.current_status = f"📄 Creating {filename}..."

        elif status == "completed":
            version = part.data.get("version", 1)
            self.current_status = ""  # Clear status

            if adapter_config.auto_save_artifacts:
                try:
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
                            context=context,
                            filename=filename,
                            content_bytes=content_bytes,
                            version=version,
                            output_dir=output_dir,
                        )

                        if summary:
                            print_formatted_text(HTML(f"<ansigreen>{summary}</ansigreen>"))
                    else:
                        print_formatted_text(HTML(f"<ansired>❌ Failed to load {filename}</ansired>"))

                except Exception as e:
                    log.exception(f"Error auto-saving artifact {filename}: {e}")
                    print_formatted_text(HTML(f"<ansired>❌ Failed to save {filename}: {e}</ansired>"))

        elif status == "failed":
            self.current_status = ""
            print_formatted_text(HTML(f"<ansired>❌ Failed to create artifact: {filename}</ansired>"))
