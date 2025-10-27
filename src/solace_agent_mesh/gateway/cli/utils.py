"""
Utility functions for the CLI Gateway.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.status import Status
from rich.text import Text

if TYPE_CHECKING:
    from .adapter import CliAdapter

log = logging.getLogger(__name__)

# Create a global console instance for the CLI
console = Console()


def create_cli_session_id() -> str:
    """
    Creates a unique session ID for this CLI invocation.
    Uses timestamp to ensure uniqueness.
    """
    import time

    return f"cli-session-{int(time.time() * 1000)}"


def print_welcome_banner():
    """Display welcome banner when CLI starts."""
    banner = """
🚀 **SAM CLI Gateway**

Type your message or use `/help` for commands.
Press Ctrl+D or type `/exit` to quit.
"""
    console.print(Markdown(banner))
    console.print()


def print_goodbye():
    """Display goodbye message when exiting."""
    console.print("\n[bold blue]Goodbye! 👋[/bold blue]\n")


def render_markdown(text: str):
    """Render markdown text to the console."""
    try:
        console.print(Markdown(text))
    except Exception as e:
        # Fallback to plain text if markdown rendering fails
        log.warning(f"Failed to render markdown: {e}")
        console.print(text)


def print_error(message: str):
    """Display an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_status(message: str):
    """Display a status message."""
    console.print(f"[dim]{message}[/dim]")


def print_info(message: str):
    """Display an info message."""
    console.print(f"[blue]{message}[/blue]")


async def download_artifact_to_file(
    adapter: "CliAdapter",
    context,
    filename: str,
    version: str = "latest",
    output_dir: Optional[Path] = None,
) -> bool:
    """
    Download an artifact and save it to a file.

    Args:
        adapter: The CLI adapter instance
        context: Response context for the artifact
        filename: Name of the artifact to download
        version: Version of the artifact (default: "latest")
        output_dir: Directory to save the file (default: current directory)

    Returns:
        True if download succeeded, False otherwise
    """
    try:
        # Use the adapter's context to load artifact content
        content_bytes = await adapter.context.load_artifact_content(
            context=context, filename=filename, version=version
        )

        if not content_bytes:
            print_error(f"Could not retrieve content for artifact: {filename}")
            return False

        # Determine output path
        if output_dir is None:
            output_dir = Path.cwd()

        output_path = output_dir / filename

        # Write the file
        output_path.write_bytes(content_bytes)

        # Calculate size for display
        size_kb = len(content_bytes) / 1024
        if size_kb < 1:
            size_str = f"{len(content_bytes)} bytes"
        elif size_kb < 1024:
            size_str = f"{size_kb:.1f} KB"
        else:
            size_str = f"{size_kb / 1024:.1f} MB"

        console.print(
            f"[green]✅ Downloaded {filename} ({size_str}) to {output_path}[/green]"
        )
        return True

    except Exception as e:
        log.exception(f"Error downloading artifact {filename}: {e}")
        print_error(f"Failed to download artifact: {e}")
        return False


def format_artifact_size(size_bytes: Optional[int]) -> str:
    """Format byte size for human-readable display (compact)."""
    if size_bytes is None:
        return "? KB"

    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_unique_filename(directory: Path, filename: str) -> Path:
    """
    Get a unique filename in the directory by adding _2, _3, etc. on collision.

    Args:
        directory: Target directory
        filename: Desired filename

    Returns:
        Path object with a unique filename
    """
    target_path = directory / filename
    if not target_path.exists():
        return target_path

    # Split into stem and suffix
    stem = target_path.stem
    suffix = target_path.suffix

    counter = 2
    while True:
        new_filename = f"{stem}_{counter}{suffix}"
        new_path = directory / new_filename
        if not new_path.exists():
            return new_path
        counter += 1


async def auto_save_artifact(
    adapter: "CliAdapter",
    context,
    filename: str,
    content_bytes: bytes,
    version: int,
    description: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Auto-save an artifact with collision handling.

    Args:
        adapter: The CLI adapter instance
        context: Response context
        filename: Original filename
        content_bytes: File content
        version: Artifact version
        description: Optional description
        output_dir: Directory to save (defaults to cwd)

    Returns:
        Compact summary line for display, or None on failure
    """
    try:
        if output_dir is None:
            output_dir = Path.cwd()

        # Get unique filename (handle collisions)
        output_path = get_unique_filename(output_dir, filename)

        # Write the file
        output_path.write_bytes(content_bytes)

        # Format size
        size_str = format_artifact_size(len(content_bytes))

        # Build compact summary: 📄 filename (v1, 1.2 MB) → ./filename
        summary = f"📄 {filename} (v{version}, {size_str}) → {output_path}"

        log.info(f"Auto-saved artifact: {filename} to {output_path}")
        return summary

    except Exception as e:
        log.exception(f"Error auto-saving artifact {filename}: {e}")
        return f"❌ Failed to save {filename}: {e}"


def format_artifact_summary(
    filename: str,
    version: int,
    size_bytes: Optional[int],
    saved_path: Optional[Path] = None,
) -> str:
    """
    Format a compact one-line artifact summary.

    Args:
        filename: Artifact filename
        version: Version number
        size_bytes: Size in bytes
        saved_path: Path where saved (if auto-saved)

    Returns:
        Compact summary string
    """
    size_str = format_artifact_size(size_bytes)
    if saved_path:
        return f"📄 {filename} (v{version}, {size_str}) → {saved_path}"
    else:
        return f"📄 {filename} (v{version}, {size_str})"
