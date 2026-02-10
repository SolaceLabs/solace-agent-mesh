"""
Common utilities shared between task send and task run commands.
"""
import asyncio
import base64
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

import click
import httpx

from cli.utils import error_exit


async def fetch_available_agents(url: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch available agents from the gateway."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{url}/api/v1/agentCards", headers=headers)
        response.raise_for_status()
        return response.json()


def get_agent_name_from_cards(agent_cards: List[Dict[str, Any]], preferred_name: str) -> Optional[str]:
    """
    Find a matching agent name from available cards.
    Tries exact match first, then case-insensitive, then partial match.
    Returns the exact name if found, or None if not found.
    """
    preferred_lower = preferred_name.lower()

    # Try exact match first
    for card in agent_cards:
        name = card.get("name", "")
        if name == preferred_name:
            return name

    # Try case-insensitive exact match
    for card in agent_cards:
        name = card.get("name", "")
        if name.lower() == preferred_lower:
            return name

    # Try partial match (name contains preferred, or preferred contains name)
    for card in agent_cards:
        name = card.get("name", "")
        name_lower = name.lower()
        if preferred_lower in name_lower or name_lower in preferred_lower:
            return name

    return None


def get_mime_type(file_path: Path) -> str:
    """Determine MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def read_file_as_base64(file_path: Path) -> str:
    """Read a file and return its content as base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_file_parts(file_paths: List[str]) -> List[dict]:
    """Build FilePart objects for the given file paths."""
    parts = []
    for file_path_str in file_paths:
        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            error_exit(f"File not found: {file_path}")
        if not file_path.is_file():
            error_exit(f"Not a file: {file_path}")

        mime_type = get_mime_type(file_path)
        base64_content = read_file_as_base64(file_path)

        parts.append({
            "kind": "file",
            "file": {
                "bytes": base64_content,
                "name": file_path.name,
                "mimeType": mime_type,
            },
        })

    return parts


async def download_stim_file(
    url: str, task_id: str, output_dir: Path, headers: dict
):
    """Download the STIM file for the task."""
    stim_url = f"{url}/api/v1/tasks/{task_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(stim_url, headers=headers)
        response.raise_for_status()

        stim_path = output_dir / f"{task_id}.stim"
        with open(stim_path, "wb") as f:
            f.write(response.content)


async def execute_task(
    message: str,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: List[str],
    timeout: int,
    output_dir: Optional[Path],
    quiet: bool,
    no_stim: bool,
    debug: bool,
    session_hint: str = "",
) -> int:
    """
    Core task execution: send a task, stream SSE response, save outputs.

    Shared by both 'sam task send' and 'sam task run'.

    Args:
        message: The prompt text to send
        url: Base URL of the gateway (already stripped of trailing slash)
        agent: Resolved agent name
        session_id: Optional session ID (generates new UUID if None)
        token: Optional auth token
        files: List of file paths to attach
        timeout: SSE timeout in seconds
        output_dir: Output directory (auto-created from task ID if None)
        quiet: Suppress streaming output
        no_stim: Skip STIM file download
        debug: Enable debug output
        session_hint: Extra text appended after session ID in summary

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from .sse_client import SSEClient
    from .message_assembler import MessageAssembler
    from .event_recorder import EventRecorder
    from .artifact_handler import ArtifactHandler

    def _debug(msg: str):
        if debug:
            click.echo(click.style(f"[DEBUG] {msg}", fg="yellow"), err=True)

    # Generate session ID if not provided
    effective_session_id = session_id or str(uuid.uuid4())

    # Build message parts
    parts = [{"kind": "text", "text": message}]

    if files:
        file_parts = build_file_parts(files)
        parts.extend(file_parts)
        if not quiet:
            click.echo(click.style(f"Attached {len(file_parts)} file(s)", fg="blue"))

    # Build JSON-RPC request payload
    payload = {
        "jsonrpc": "2.0",
        "id": f"req-{uuid.uuid4()}",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "parts": parts,
                "messageId": f"msg-{uuid.uuid4()}",
                "kind": "message",
                "contextId": effective_session_id,
                "metadata": {"agent_name": agent},
            }
        },
    }

    # Build headers
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if not quiet:
        click.echo(click.style(f"Sending task to {agent}...", fg="blue"))

    _debug(f"POST {url}/api/v1/message:stream")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{url}/api/v1/message:stream",
                json=payload,
                headers=headers,
            )
            _debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
    except httpx.ConnectError:
        click.echo(click.style(f"Failed to connect to {url}", fg="red"), err=True)
        return 1
    except httpx.HTTPStatusError as e:
        click.echo(
            click.style(f"HTTP error {e.response.status_code}: {e.response.text}", fg="red"),
            err=True,
        )
        return 1

    # Extract task ID from response
    task_result = result.get("result", {})
    task_id = task_result.get("id")

    if not task_id:
        click.echo(click.style(f"No task ID in response: {result}", fg="red"), err=True)
        return 1

    if not quiet:
        click.echo(click.style(f"Task ID: {task_id}", fg="blue"))
        click.echo()

    # Create output directory if not provided
    if output_dir is None:
        output_dir = Path(f"/tmp/sam-task-{task_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    assembler = MessageAssembler()
    recorder = EventRecorder(output_dir)
    sse_client = SSEClient(url, timeout, token, debug=debug)

    _debug(f"Subscribing to SSE events for task {task_id}")

    # Track response text for saving
    response_text_parts = []

    # Subscribe to SSE and process events
    try:
        async for event in sse_client.subscribe(task_id):
            recorder.record_event(event.event_type, event.data)

            msg, new_text = assembler.process_event(event.event_type, event.data)

            if new_text:
                response_text_parts.append(new_text)
                if not quiet:
                    click.echo(new_text, nl=False)
                    sys.stdout.flush()

            if msg.is_complete:
                _debug("Task is complete")
                break

    except httpx.HTTPStatusError as e:
        click.echo(click.style(f"\nSSE connection error: {e}", fg="red"), err=True)
        return 1
    except asyncio.TimeoutError as e:
        click.echo(click.style(f"\nTimeout: {e}", fg="yellow"), err=True)
    except Exception as e:
        click.echo(click.style(f"\nSSE error: {e}", fg="red"), err=True)
        return 1

    # Ensure newline after streaming
    if not quiet and response_text_parts:
        click.echo()

    # Get final message state
    final_msg = assembler.get_message()

    # Save recorded events
    recorder.save()

    # Save response text
    response_text = "".join(response_text_parts)
    response_path = output_dir / "response.txt"
    with open(response_path, "w") as f:
        f.write(response_text)

    # Download artifacts
    artifact_handler = ArtifactHandler(url, effective_session_id, output_dir, token)
    try:
        downloaded_artifacts = await artifact_handler.download_all_artifacts()
        if downloaded_artifacts and not quiet:
            click.echo()
            click.echo(click.style("Downloaded artifacts:", fg="green"))
            for artifact in downloaded_artifacts:
                click.echo(f"  - {artifact.filename} ({artifact.size} bytes)")
    except Exception as e:
        if not quiet:
            click.echo(click.style(f"Warning: Could not download artifacts: {e}", fg="yellow"))

    # Fetch STIM file
    if not no_stim:
        try:
            await download_stim_file(url, task_id, output_dir, headers)
        except Exception as e:
            if not quiet:
                click.echo(click.style(f"Warning: Could not download STIM file: {e}", fg="yellow"))

    # Print summary
    click.echo()
    click.echo(click.style("---", fg="cyan"))

    if final_msg.is_error:
        click.echo(click.style("Task failed.", fg="red", bold=True))
        exit_code = 1
    else:
        click.echo(click.style("Task completed successfully.", fg="green", bold=True))
        exit_code = 0

    click.echo(f"Session ID: {click.style(effective_session_id, fg='cyan')}{session_hint}")
    click.echo(f"Task ID: {task_id}")
    click.echo(f"Output directory: {output_dir}")
    click.echo(f"Events recorded: {recorder.get_event_count()}")

    return exit_code
