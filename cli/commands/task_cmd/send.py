"""
CLI command for sending tasks to the webui gateway and receiving responses via SSE.
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional, List

import click
import httpx

from cli.utils import error_exit

from .common import (
    fetch_available_agents,
    get_agent_name_from_cards,
    execute_task,
)


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
        exit_code = asyncio.run(
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
        sys.exit(exit_code)
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
) -> int:
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
            available_names = [card.get("name") for card in agent_cards if card.get("name")]
            error_exit(
                f"Agent '{agent}' not found. Available agents: {', '.join(available_names)}"
            )
    except httpx.HTTPStatusError as e:
        _debug(f"Could not fetch agents: {e}")
        click.echo(click.style(f"Warning: Could not fetch agent list: {e}", fg="yellow"), err=True)
    except httpx.ConnectError:
        error_exit(f"Failed to connect to {url}. Is the gateway running?")

    # Resolve output_dir to Path if user specified one
    output_path = Path(output_dir) if output_dir else None

    return await execute_task(
        message=message,
        url=url,
        agent=agent,
        session_id=session_id,
        token=token,
        files=files,
        timeout=timeout,
        output_dir=output_path,
        quiet=quiet,
        no_stim=no_stim,
        debug=debug,
        session_hint="  (use with --session-id to continue)",
    )
