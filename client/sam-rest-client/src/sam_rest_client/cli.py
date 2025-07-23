"""
Command-line interface for the SAM REST API Client.
"""

import argparse
import asyncio
import os
import sys
from typing import List, Tuple, IO

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .client import (
    SAMRestClient,
    SAMTaskTimeoutError,
    SAMTaskFailedError,
    SAMClientError,
    SAMResult,
)


def ask_yes_no(question: str, console: Console) -> bool:
    """Helper to ask a simple yes/no question."""
    while True:
        response = console.input(f"[bold yellow]{question} (y/n): [/bold yellow]").lower()
        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False
        console.print("[bold red]Please answer 'y' or 'n'.[/bold red]")


async def main_async():
    """The main asynchronous logic for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="A CLI tool to interact with the Solace Agent Mesh (SAM) REST API Gateway."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="The base URL of the SAM REST API Gateway (e.g., http://localhost:8080).",
    )
    parser.add_argument(
        "--token",
        help="The bearer token for authentication.",
        default=os.environ.get("SAM_AUTH_TOKEN"),
    )
    parser.add_argument("--agent", required=True, help="The name of the target agent.")
    parser.add_argument("--prompt", required=True, help="The prompt to send to the agent.")
    parser.add_argument(
        "--file",
        action="append",
        dest="files",
        help="Path to a file to upload. Use this option multiple times for multiple files. (e.g., --file /path/to/file1.txt --file /path/to/file2.csv)",
    )
    parser.add_argument(
        "--mode",
        choices=["async", "sync"],
        default="async",
        help="The API mode to use ('async' for v2 polling, 'sync' for v1 blocking).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds for async task completion.",
    )
    parser.add_argument(
        "--log",
        help="Path to a file to write raw server responses for debugging.",
    )

    args = parser.parse_args()
    console = Console()

    log_file_handle = None
    if args.log:
        try:
            log_file_handle = open(args.log, "w", encoding="utf-8")
            console.print(f"[dim]Logging raw responses to {args.log}[/dim]")
        except IOError as e:
            console.print(f"[bold red]Error: Could not open log file {args.log}: {e}[/bold red]")
            sys.exit(1)

    client = SAMRestClient(
        base_url=args.url, auth_token=args.token, log_file_handle=log_file_handle
    )
    file_handles: List[Tuple[str, IO]] = []

    try:
        if args.files:
            for file_path in args.files:
                if not os.path.exists(file_path):
                    console.print(f"[bold red]Error: File not found: {file_path}[/bold red]")
                    sys.exit(1)
                file_handles.append((os.path.basename(file_path), open(file_path, "rb")))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task(description=f"Submitting task to agent '{args.agent}'...", total=None)
            final_result: SAMResult = await client.invoke(
                agent_name=args.agent,
                prompt=args.prompt,
                files=file_handles,
                mode=args.mode,
                timeout_seconds=args.timeout,
            )

        console.rule("[bold green]Task Completed[/bold green]")

        agent_text_response = final_result.get_text()
        if agent_text_response:
            console.print(Panel(agent_text_response, title="Agent Response", border_style="cyan"))
        else:
            console.print("[italic]No text response from agent.[/italic]")

        artifacts = final_result.get_artifacts()
        if artifacts:
            console.print("\n[bold]Generated Artifacts:[/bold]")
            for i, artifact in enumerate(artifacts):
                name = artifact.name or "unnamed_artifact"
                mime_type = artifact.mime_type or "unknown"
                size = artifact.size if artifact.size is not None else 0
                console.print(f"  [cyan]{i+1}. {name}[/cyan] ({mime_type}, {size} bytes)")

            if ask_yes_no("\nDownload artifacts to the current directory?", console):
                with Progress(console=console) as progress:
                    download_task = progress.add_task(
                        "[green]Downloading...", total=len(artifacts)
                    )
                    for artifact in artifacts:
                        if artifact.name:
                            progress.update(
                                download_task,
                                advance=1,
                                description=f"Downloading {artifact.name}...",
                            )
                            try:
                                await artifact.save_to_disk(".")
                                console.print(f"  [green]✓ Saved {artifact.name}[/green]")
                            except Exception as e:
                                console.print(
                                    f"  [bold red]✗ Failed to save {artifact.name}: {e}[/bold red]"
                                )
                        else:
                            progress.update(download_task, advance=1)
                            console.print(
                                f"  [yellow]! Skipped downloading an artifact because it has no name.[/yellow]"
                            )
        else:
            console.print("\n[italic]No artifacts were generated.[/italic]")

    except SAMTaskTimeoutError as e:
        console.print(f"\n[bold red]Error: Task Timed Out[/bold red]\n{e}")
    except SAMTaskFailedError as e:
        console.print(f"\n[bold red]Error: Task Failed[/bold red]\n{e.message}")
        console.print(e.error_details)
    except SAMClientError as e:
        console.print(f"\n[bold red]Error: Client Error[/bold red]\n{e}")
    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red]\n{e}")
    finally:
        for _, f_handle in file_handles:
            f_handle.close()
        await client.close()
        if log_file_handle:
            log_file_handle.close()


def main():
    """Entry point for the CLI script."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
