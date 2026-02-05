"""
CLI command for running SAM, sending a task, and stopping - all in one command.
"""
import asyncio
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
import httpx

from cli.utils import error_exit

from .common import (
    fetch_available_agents,
    get_agent_name_from_cards,
    build_file_parts,
    download_stim_file,
)
from .sam_runner import SAMRunner, discover_config_files
from .sse_client import SSEClient
from .message_assembler import MessageAssembler
from .event_recorder import EventRecorder
from .artifact_handler import ArtifactHandler


async def wait_for_agents(
    url: str,
    target_agent: str,
    token: Optional[str],
    timeout: float,
    poll_interval: float,
    stabilization_wait: float,
    debug_fn,
) -> tuple[List[Dict[str, Any]], str]:
    """
    Wait for agents to become available.

    Algorithm:
    1. Poll /api/v1/agentCards until we get a response with at least one agent
    2. Wait stabilization_wait seconds for all agents to register
    3. Poll again to get the final list
    4. Verify target agent exists

    Returns:
        Tuple of (agent_cards, resolved_agent_name)

    Raises:
        TimeoutError: If agents don't become ready within timeout
    """
    start_time = time.time()
    first_agents_time = None

    while time.time() - start_time < timeout:
        try:
            agent_cards = await fetch_available_agents(url, token)

            if agent_cards:
                if first_agents_time is None:
                    # First time we see agents - start stabilization wait
                    first_agents_time = time.time()
                    agent_names = [c.get("name", "?") for c in agent_cards]
                    debug_fn(f"First agents detected: {agent_names}")
                    debug_fn(f"Waiting {stabilization_wait}s for stabilization...")
                    await asyncio.sleep(stabilization_wait)
                    # Poll again after stabilization
                    agent_cards = await fetch_available_agents(url, token)
                    agent_names = [c.get("name", "?") for c in agent_cards]
                    debug_fn(f"After stabilization: {agent_names}")

                # Check if target agent is available
                resolved_agent = get_agent_name_from_cards(agent_cards, target_agent)
                if resolved_agent:
                    return agent_cards, resolved_agent

                debug_fn(f"Target agent '{target_agent}' not yet available")

        except httpx.ConnectError:
            debug_fn("Gateway not yet responding...")
        except httpx.HTTPStatusError as e:
            debug_fn(f"Gateway error: {e.response.status_code}")

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Timeout waiting for agent '{target_agent}' after {timeout}s")


async def run_task_async(
    message: str,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: List[str],
    timeout: int,
    output_dir: Path,
    quiet: bool,
    no_stim: bool,
    debug: bool,
) -> int:
    """
    Send a task and stream the response.

    This is adapted from send.py's _send_task_async but assumes agents are already ready.

    Returns:
        Exit code (0 for success, 1 for failure)
    """

    def _debug(msg: str):
        if debug:
            click.echo(click.style(f"[DEBUG] {msg}", fg="yellow"), err=True)

    # Generate session ID if not provided
    effective_session_id = session_id or str(uuid.uuid4())

    # Build message parts
    parts = [{"kind": "text", "text": message}]

    # Add file parts if files were provided
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
        click.echo(click.style(f"HTTP error {e.response.status_code}: {e.response.text}", fg="red"), err=True)
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

    # Update output directory with task ID if using default
    if str(output_dir).endswith("-pending"):
        output_dir = Path(str(output_dir).replace("-pending", f"-{task_id}"))
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
            # Record ALL events
            recorder.record_event(event.event_type, event.data)

            # Process event and get new text to print
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

    click.echo(f"Session ID: {click.style(effective_session_id, fg='cyan')}")
    click.echo(f"Task ID: {task_id}")
    click.echo(f"Output directory: {output_dir}")
    click.echo(f"Events recorded: {recorder.get_event_count()}")

    return exit_code


@click.command("run")
@click.argument("message", required=True)
@click.option(
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    type=click.Path(exists=True, dir_okay=True, resolve_path=True),
    help="YAML config files or directories (can be used multiple times). Defaults to configs/ directory.",
)
@click.option(
    "--skip",
    "-s",
    "skip_files",
    multiple=True,
    help="File name(s) to exclude from configs (e.g., -s my_agent.yaml).",
)
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
    default=300,
    type=int,
    help="Timeout in seconds for task execution (default: 300)",
)
@click.option(
    "--startup-timeout",
    default=60,
    type=int,
    help="Timeout in seconds for agent readiness (default: 60)",
)
@click.option(
    "--output-dir",
    "-o",
    default=None,
    type=click.Path(),
    help="Output directory for artifacts and logs (default: /tmp/sam-task-run-{taskId})",
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
    "--system-env",
    is_flag=True,
    help="Use system environment variables only; do not load .env file.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output",
)
def run_task(
    message: str,
    config_paths: tuple,
    skip_files: tuple,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: tuple,
    timeout: int,
    startup_timeout: int,
    output_dir: Optional[str],
    quiet: bool,
    no_stim: bool,
    system_env: bool,
    debug: bool,
):
    """
    Start SAM, send a task, stream the response, and stop.

    This command runs SAM with the specified configuration, waits for agents
    to become ready, sends a task, streams the response, and then cleanly
    shuts down SAM.

    MESSAGE is the prompt text to send to the agent.

    \b
    Examples:
        # Basic usage with default configs
        sam task run "What agents are available?"

        # Specify config files
        sam task run "Hello" -c examples/agents/orchestrator.yaml -c examples/gateways/webui.yaml

        # With file attachment
        sam task run "Summarize this document" --file ./document.pdf -c configs/

        # Target specific agent
        sam task run "Analyze data" --agent data_analyst -c configs/
    """
    try:
        exit_code = asyncio.run(
            _run_task_main(
                message=message,
                config_paths=config_paths,
                skip_files=skip_files,
                url=url,
                agent=agent,
                session_id=session_id,
                token=token,
                files=list(files),
                timeout=timeout,
                startup_timeout=startup_timeout,
                output_dir=output_dir,
                quiet=quiet,
                no_stim=no_stim,
                system_env=system_env,
                debug=debug,
            )
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        click.echo("\n\nTask cancelled by user.")
        sys.exit(1)
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        error_exit(f"Error: {e}")


async def _run_task_main(
    message: str,
    config_paths: tuple,
    skip_files: tuple,
    url: str,
    agent: str,
    session_id: Optional[str],
    token: Optional[str],
    files: List[str],
    timeout: int,
    startup_timeout: int,
    output_dir: Optional[str],
    quiet: bool,
    no_stim: bool,
    system_env: bool,
    debug: bool,
) -> int:
    """Main async implementation of the task run command."""

    def _debug(msg: str):
        if debug:
            click.echo(click.style(f"[DEBUG] {msg}", fg="yellow"), err=True)

    def _info(msg: str):
        if not quiet:
            click.echo(msg)

    # Discover config files
    try:
        config_files = discover_config_files(config_paths, skip_files)
    except FileNotFoundError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        return 1

    if not config_files:
        click.echo(click.style("No configuration files found.", fg="red"), err=True)
        return 1

    _info(click.style(f"Starting SAM with {len(config_files)} config file(s)...", fg="blue"))
    for cf in config_files:
        _debug(f"  Config: {cf}")

    # Create output directory (use pending suffix until we have task ID)
    output_path = Path(output_dir) if output_dir else Path(f"/tmp/sam-task-run-pending")
    output_path.mkdir(parents=True, exist_ok=True)
    log_file = output_path / "sam.log"

    # Create SAM runner
    sam_runner = SAMRunner(
        config_files=config_files,
        log_file=log_file,
        load_env=not system_env,
    )

    exit_code = 1

    try:
        # Start SAM
        sam_runner.start()
        _info(click.style("SAM started.", fg="green"))

        # Wait for agents to be ready
        _info(click.style(f"Waiting for agents (timeout: {startup_timeout}s)...", fg="blue"))

        try:
            agent_cards, resolved_agent = await wait_for_agents(
                url=url,
                target_agent=agent,
                token=token,
                timeout=startup_timeout,
                poll_interval=1.0,
                stabilization_wait=2.0,
                debug_fn=_debug,
            )
        except TimeoutError as e:
            click.echo(click.style(str(e), fg="red"), err=True)
            click.echo(click.style(f"Check {log_file} for SAM startup logs.", fg="yellow"), err=True)
            return 1

        agent_names = [c.get("name", "?") for c in agent_cards]
        _info(click.style(f"Agents ready: {', '.join(agent_names)}", fg="green"))

        if resolved_agent != agent:
            _info(click.style(f"Using agent: {resolved_agent}", fg="yellow"))

        _info("")

        # Send the task
        exit_code = await run_task_async(
            message=message,
            url=url,
            agent=resolved_agent,
            session_id=session_id,
            token=token,
            files=files,
            timeout=timeout,
            output_dir=output_path,
            quiet=quiet,
            no_stim=no_stim,
            debug=debug,
        )

    finally:
        # Always stop SAM
        _info("")
        _info(click.style("Stopping SAM...", fg="blue"))
        sam_runner.stop()
        _info(click.style("Done.", fg="green"))

    return exit_code
