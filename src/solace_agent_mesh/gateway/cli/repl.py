"""
REPL (Read-Eval-Print Loop) implementation for the CLI Gateway.
Uses prompt_toolkit for better input handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.table import Table

from ..adapter.types import ResponseContext
from . import utils

if TYPE_CHECKING:
    from .adapter import CliAdapter

log = logging.getLogger(__name__)


class CliRepl:
    """
    Interactive REPL for the CLI Gateway.

    Handles user input, slash commands, and delegates regular messages
    to the adapter's context for processing.
    """

    def __init__(self, adapter: "CliAdapter", prompt: str = "sam> "):
        self.adapter = adapter
        self.prompt = prompt
        self.running = False
        self.session_id = utils.create_cli_session_id()

        # Create prompt_toolkit session for better input handling
        self.prompt_session: PromptSession = PromptSession()

        # Command registry
        self.commands: Dict[str, Callable] = {
            "help": self.cmd_help,
            "artifacts": self.cmd_artifacts,
            "download": self.cmd_download,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,  # Alias for exit
        }

    async def start(self):
        """Start the REPL loop."""
        self.running = True
        utils.print_welcome_banner()

        try:
            # Use patch_stdout to keep output above the prompt
            with patch_stdout():
                while self.running:
                    try:
                        # Read user input using prompt_toolkit
                        user_input = await self.prompt_session.prompt_async(
                            self.prompt
                        )

                        if not user_input:
                            continue

                        user_input = user_input.strip()

                        if not user_input:
                            continue

                        # Check if it's a slash command
                        if user_input.startswith("/"):
                            await self._handle_command(user_input)
                        else:
                            # Regular message - send to agent
                            await self._handle_message(user_input)

                    except KeyboardInterrupt:
                        # Ctrl+C - just print newline and continue
                        utils.console.print()
                        continue
                    except EOFError:
                        # Ctrl+D
                        break
                    except Exception as e:
                        log.exception(f"Error in REPL loop: {e}")
                        utils.print_error(f"An unexpected error occurred: {e}")

        finally:
            utils.print_goodbye()

    async def stop(self):
        """Stop the REPL loop."""
        self.running = False

    async def _handle_command(self, command_line: str):
        """
        Handle a slash command.

        Args:
            command_line: The full command line starting with '/'
        """
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
        """
        Handle a regular message by sending it to the agent.

        Args:
            message: The user's message
        """
        try:
            # Create a simple external input that the adapter can process
            external_input = {
                "text": message,
                "session_id": self.session_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Delegate to the generic gateway's handle_external_input
            await self.adapter.context.handle_external_input(external_input)

        except Exception as e:
            log.exception(f"Error handling message: {e}")
            utils.print_error(f"Failed to process message: {e}")

    # --- Slash Command Handlers ---

    async def cmd_help(self, args: str):
        """Display help information about available commands."""
        help_text = """
**Available Commands:**

- `/help` - Show this help message
- `/artifacts` - List artifacts in the current session
- `/download <filename>` - Download an artifact to the current directory
- `/exit` or `/quit` - Exit the CLI gateway

**Usage:**

Type any message to send it to the agent. The agent's response will be displayed
as it streams in, with full markdown formatting support.

Artifacts created by the agent are automatically saved to the current directory.
"""
        utils.console.print()
        utils.render_markdown(help_text)
        utils.console.print()

    async def cmd_artifacts(self, args: str):
        """List all artifacts in the current session."""
        try:
            # Create a context for listing artifacts
            context = ResponseContext(
                task_id=f"cli-list-artifacts-{datetime.utcnow().timestamp()}",
                session_id=self.session_id,
                user_id=self.adapter.user_id,
                platform_context={},
            )

            artifacts = await self.adapter.context.list_artifacts(context)

            if not artifacts:
                utils.console.print("\n[dim]No artifacts found in this session.[/dim]\n")
                return

            # Display artifacts in a nice table
            table = Table(title=f"Artifacts ({len(artifacts)} found)")
            table.add_column("Filename", style="cyan", no_wrap=True)
            table.add_column("Version", style="magenta")
            table.add_column("Description", style="white")
            table.add_column("Modified", style="dim")

            for artifact in artifacts:
                # Format the last modified time
                modified_str = "N/A"
                if artifact.last_modified:
                    try:
                        dt_obj = datetime.fromisoformat(
                            artifact.last_modified.replace("Z", "+00:00")
                        )
                        modified_str = dt_obj.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        modified_str = artifact.last_modified

                # Truncate description if too long
                description = artifact.description or "No description"
                if len(description) > 60:
                    description = description[:57] + "..."

                table.add_row(
                    artifact.filename,
                    str(artifact.version),
                    description,
                    modified_str,
                )

            utils.console.print()
            utils.console.print(table)
            utils.console.print()

        except Exception as e:
            log.exception(f"Error listing artifacts: {e}")
            utils.print_error(f"Failed to list artifacts: {e}")

    async def cmd_download(self, args: str):
        """Download an artifact to the current directory."""
        if not args:
            utils.print_error("Usage: /download <filename> [version]")
            return

        parts = args.split()
        filename = parts[0]
        version = parts[1] if len(parts) > 1 else "latest"

        try:
            # Create a context for downloading
            context = ResponseContext(
                task_id=f"cli-download-{datetime.utcnow().timestamp()}",
                session_id=self.session_id,
                user_id=self.adapter.user_id,
                platform_context={},
            )

            success = await utils.download_artifact_to_file(
                adapter=self.adapter,
                context=context,
                filename=filename,
                version=version,
            )

            if not success:
                utils.print_error(f"Could not download artifact: {filename}")

        except Exception as e:
            log.exception(f"Error downloading artifact: {e}")
            utils.print_error(f"Failed to download artifact: {e}")

    async def cmd_exit(self, args: str):
        """Exit the CLI gateway."""
        await self.stop()
