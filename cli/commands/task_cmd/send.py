"""
CLI command for sending tasks to the webui gateway and receiving responses via SSE.
"""
import asyncio
import base64
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
import httpx

from cli.utils import error_exit

from .sse_client import SSEClient
from .message_assembler import MessageAssembler
from .event_recorder import EventRecorder
from .artifact_handler import ArtifactHandler


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


def get_default_agent(agent_cards: List[Dict[str, Any]]) -> Optional[str]:
    """Get the first available agent name."""
    if agent_cards:
        return agent_cards[0].get("name")
    return None


def _get_mime_type(file_path: Path) -> str:
    """Determine MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def _read_file_as_base64(file_path: Path) -> str:
    """Read a file and return its content as base64."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_file_parts(file_paths: List[str]) -> List[dict]:
    """Build FilePart objects for the given file paths."""
    parts = []
    for file_path_str in file_paths:
        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            error_exit(f"File not found: {file_path}")
        if not file_path.is_file():
            error_exit(f"Not a file: {file_path}")

        mime_type = _get_mime_type(file_path)
        base64_content = _read_file_as_base64(file_path)

        parts.append({
            "kind": "file",
            "file": {
                "bytes": base64_content,
                "name": file_path.name,
                "mimeType": mime_type,
            },
        })

    return parts


@click.command("send")
@click.argument("message", required=True)
@click.option(
    "--url",
    "-u",
    envvar="SAM_WEBUI_URL",
    default="http://localhost:8000",
    help="Base URL of the webui gateway (default: http://localhost:8000)",
)
@click.option(
    "--agent",
    "-a",
    envvar="SAM_AGENT",
    default="orchestrator",
    help="Target agent name (default: orchestrator)",
)
@click.option(
    "--session-id",
    "-s",
    default=None,
    help="Session ID for context continuity (generates new if not provided)",
)
@click.option(
    "--token",
    "-t",
    envvar="SAM_AUTH_TOKEN",
    default=None,
    help="Bearer token for authentication",
)
@click.option(
    "--file",
    "-f",
    "files",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="File(s) to attach (can be used multiple times)",
)
@click.option(
    "--timeout",
    default=120,
    type=int,
    help="Timeout in seconds for SSE connection (default: 120)",
)
@click.option(
    "--output-dir",
    "-o",
    default=None,
    type=click.Path(),
    help="Output directory for artifacts and logs (default: /tmp/sam-task-{taskId})",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress streaming output, only show final result",
)
@click.option(
    "--no-stim",
    is_flag=True,
    help="Do not fetch the STIM file on completion",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output",
)
def send_task(
    message: str,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: tuple,
    timeout: int,
    output_dir: Optional[str],
    quiet: bool,
    no_stim: bool,
    debug: bool,
):
    """
    Send a task to the webui gateway and stream the response.

    MESSAGE is the prompt text to send to the agent.

    \b
    Examples:
        # Basic usage
        sam task send "What is the weather today?"

        # Specify agent
        sam task send "Analyze this data" --agent data_analyst

        # With file attachment
        sam task send "Summarize this document" --file ./document.pdf

        # Continue from previous session
        sam task send "What did we discuss?" --session-id abc-123

        # Custom URL with authentication
        sam task send "Hello" --url https://mygateway.com --token $MY_TOKEN
    """
    try:
        asyncio.run(
            _send_task_async(
                message=message,
                url=url,
                agent=agent,
                session_id=session_id,
                token=token,
                files=list(files),
                timeout=timeout,
                output_dir=output_dir,
                quiet=quiet,
                no_stim=no_stim,
                debug=debug,
            )
        )
    except KeyboardInterrupt:
        click.echo("\n\nTask cancelled by user.")
        sys.exit(1)
    except Exception as e:
        error_exit(f"Error: {e}")


async def _send_task_async(
    message: str,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: List[str],
    timeout: int,
    output_dir: Optional[str],
    quiet: bool,
    no_stim: bool,
    debug: bool,
):
    """Async implementation of the task send command."""

    def _debug(msg: str):
        if debug:
            click.echo(click.style(f"[DEBUG] {msg}", fg="yellow"), err=True)

    url = url.rstrip("/")
    _debug(f"Target URL: {url}")

    # Fetch available agents and validate/resolve agent name
    try:
        _debug("Fetching available agents...")
        agent_cards = await fetch_available_agents(url, token)
        _debug(f"Found {len(agent_cards)} agents")

        # Try to find the specified agent
        resolved_agent = get_agent_name_from_cards(agent_cards, agent)
        if resolved_agent:
            agent = resolved_agent
            _debug(f"Resolved agent name: {agent}")
        else:
            # Agent not found, show available agents
            available_names = [card.get("name") for card in agent_cards if card.get("name")]
            click.echo(click.style(f"Agent '{agent}' not found.", fg="red"), err=True)
            click.echo(f"Available agents: {', '.join(available_names)}", err=True)

            # Use the first available agent as fallback
            default_agent = get_default_agent(agent_cards)
            if default_agent:
                click.echo(click.style(f"Using default agent: {default_agent}", fg="yellow"), err=True)
                agent = default_agent
            else:
                error_exit("No agents available")
    except httpx.HTTPStatusError as e:
        _debug(f"Could not fetch agents: {e}")
        click.echo(click.style(f"Warning: Could not fetch agent list: {e}", fg="yellow"), err=True)
    except httpx.ConnectError:
        error_exit(f"Failed to connect to {url}. Is the gateway running?")

    # Generate session ID if not provided
    effective_session_id = session_id or str(uuid.uuid4())

    # Build message parts
    parts = [{"kind": "text", "text": message}]

    # Add file parts if files were provided
    if files:
        file_parts = _build_file_parts(files)
        parts.extend(file_parts)
        if not quiet:
            click.echo(
                click.style(f"Attached {len(file_parts)} file(s)", fg="blue")
            )

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

    # POST to /api/v1/message:stream
    if not quiet:
        click.echo(click.style(f"Sending task to {agent}...", fg="blue"))

    _debug(f"POST {url}/api/v1/message:stream")
    _debug(f"Payload: {payload}")

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
            _debug(f"Response body: {result}")
    except httpx.ConnectError as e:
        _debug(f"Connection error: {e}")
        error_exit(f"Failed to connect to {url}. Is the gateway running?")
    except httpx.HTTPStatusError as e:
        _debug(f"HTTP error: {e.response.status_code} - {e.response.text}")
        error_exit(f"HTTP error {e.response.status_code}: {e.response.text}")

    # Extract task ID from response
    task_result = result.get("result", {})
    task_id = task_result.get("id")

    if not task_id:
        error_exit(f"No task ID in response: {result}")

    if not quiet:
        click.echo(click.style(f"Task ID: {task_id}", fg="blue"))
        click.echo()

    # Create output directory
    output_path = Path(output_dir) if output_dir else Path(f"/tmp/sam-task-{task_id}")
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize components
    assembler = MessageAssembler()
    recorder = EventRecorder(output_path)
    sse_client = SSEClient(url, timeout, token, debug=debug)

    _debug(f"Subscribing to SSE events for task {task_id}")

    # Track response text for saving
    response_text_parts = []

    # Subscribe to SSE and process events
    try:
        async for event in sse_client.subscribe(task_id):
            # Record ALL events
            recorder.record_event(event.event_type, event.data)

            # Process event and get new text to print
            msg, new_text = assembler.process_event(event.event_type, event.data)

            _debug(f"Processed event: complete={msg.is_complete}, error={msg.is_error}, has_new_text={new_text is not None}")

            if new_text:
                response_text_parts.append(new_text)
                if not quiet:
                    # Print streaming text
                    click.echo(new_text, nl=False)
                    sys.stdout.flush()

            if msg.is_complete:
                _debug("Task is complete, exiting SSE loop")
                break

    except httpx.HTTPStatusError as e:
        _debug(f"SSE HTTP error: {e}")
        error_exit(f"SSE connection error: {e}")
    except asyncio.TimeoutError as e:
        _debug(f"SSE timeout: {e}")
        click.echo(f"\nTimeout: {e}", err=True)
    except Exception as e:
        _debug(f"SSE exception: {type(e).__name__}: {e}")
        click.echo(f"\nSSE error: {e}", err=True)

    # Ensure newline after streaming
    if not quiet and response_text_parts:
        click.echo()

    # Get final message state
    final_msg = assembler.get_message()

    # Save recorded events
    events_path = recorder.save()

    # Save response text
    response_text = "".join(response_text_parts)
    response_path = output_path / "response.txt"
    with open(response_path, "w") as f:
        f.write(response_text)

    # Download artifacts
    artifact_handler = ArtifactHandler(
        url, effective_session_id, output_path, token
    )
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
            await _download_stim_file(url, task_id, output_path, headers)
        except Exception as e:
            if not quiet:
                click.echo(
                    click.style(f"Warning: Could not download STIM file: {e}", fg="yellow")
                )

    # Print summary
    click.echo()
    click.echo(click.style("---", fg="cyan"))

    if final_msg.is_error:
        click.echo(click.style("Task failed.", fg="red", bold=True))
    else:
        click.echo(click.style("Task completed successfully.", fg="green", bold=True))

    click.echo(f"Session ID: {click.style(effective_session_id, fg='cyan')}  (use with --session-id to continue)")
    click.echo(f"Task ID: {task_id}")
    click.echo(f"Output directory: {output_path}")
    click.echo(f"Events recorded: {recorder.get_event_count()}")


async def _download_stim_file(
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
