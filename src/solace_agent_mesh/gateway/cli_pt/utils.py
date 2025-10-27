"""
Utility functions for the CLI Gateway (prompt_toolkit version).
"""

import logging
from pathlib import Path
from typing import Optional

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText, HTML

log = logging.getLogger(__name__)


def create_cli_session_id() -> str:
    """
    Creates a unique session ID for this CLI invocation.
    Uses timestamp to ensure uniqueness.
    """
    import time
    return f"cli-session-{int(time.time() * 1000)}"


def print_welcome():
    """Display welcome banner when CLI starts."""
    print_formatted_text(HTML(
        "\n<b><ansigreen>🚀 SAM CLI Gateway (prompt_toolkit)</ansigreen></b>\n\n"
        "Type your message or use <b>/help</b> for commands.\n"
        "Press Ctrl+D or type <b>/exit</b> to quit.\n"
    ))


def print_goodbye():
    """Display goodbye message when exiting."""
    print_formatted_text(HTML("\n<b><ansiblue>Goodbye! 👋</ansiblue></b>\n"))


def print_error(message: str):
    """Display an error message."""
    print_formatted_text(HTML(f"<ansired><b>Error:</b></ansired> {message}"))


def print_info(message: str):
    """Display an info message."""
    print_formatted_text(HTML(f"<ansiblue>{message}</ansiblue>"))


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

        # Build compact summary
        summary = f"📄 {filename} (v{version}, {size_str}) → {output_path}"

        log.info(f"Auto-saved artifact: {filename} to {output_path}")
        return summary

    except Exception as e:
        log.exception(f"Error auto-saving artifact {filename}: {e}")
        return f"❌ Failed to save {filename}: {e}"
