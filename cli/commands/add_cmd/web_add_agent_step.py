import click
import multiprocessing
import sys
import webbrowser
from pathlib import Path
from cli.utils import wait_for_server


from config_portal.backend.server import run_flask


def launch_add_agent_web_portal(cli_options: dict):
    """
    Launches the web-based configuration portal for adding a new agent.
    The actual file writing will happen here after the portal returns data.
    """
    click.echo(
        click.style("Attempting to start web-based 'Add Agent' portal...", fg="blue")
    )

    with multiprocessing.Manager() as manager:
        shared_data_from_web = manager.dict()

        add_agent_gui_process = multiprocessing.Process(
            target=run_flask, args=("127.0.0.1", 5002, shared_data_from_web)
        )
        add_agent_gui_process.start()
        portal_url = "http://127.0.0.1:5002/?config_mode=addAgent"
        click.echo(
            click.style(
                f"Add Agent portal is running. Opening your browser to '{portal_url}'...",
                fg="green",
            )
        )
        try:
            if wait_for_server(portal_url):
                click.echo(
                    click.style(
                        f"Opening your browser to '{portal_url}'...",
                        fg="green",
                    )
                )
                webbrowser.open(portal_url)
            else:
                raise TimeoutError("Server did not start in time.")
        except Exception:
            click.echo(
                click.style(
                    f"Could not automatically open browser, Please open {portal_url} manually.",
                    fg="yellow",
                )
            )

        click.echo(
            "Complete the agent configuration in your browser. The CLI will resume once the portal is closed or submits data."
        )

        add_agent_gui_process.join()

        if shared_data_from_web:
            returned_data = dict(shared_data_from_web)
            if returned_data.get("status") == "success_from_gui_save":
                agent_name_from_gui = returned_data.get("agent_name_input")
                agent_config_options = returned_data.get("config")
                if agent_name_from_gui and agent_config_options:
                    click.echo(
                        click.style(
                            "Configuration received from web portal. Writing agent file...",
                            fg="cyan",
                        )
                    )
                    project_root = Path.cwd()
                    return agent_name_from_gui, agent_config_options, project_root

                else:
                    click.echo(
                        click.style(
                            "Incomplete data received from web portal.", fg="red"
                        )
                    )
            elif returned_data.get("status") == "shutdown_aborted":
                click.echo(
                    click.style(
                        f"Web portal feedback: {returned_data.get('message', 'Operation aborted.')}",
                        fg="yellow",
                    )
                )
            else:
                click.echo(
                    click.style(
                        f"Web portal operation failed or was cancelled. Message: {returned_data.get('message', 'No specific error message.')}",
                        fg="red",
                    )
                )
        else:
            click.echo(
                click.style(
                    "No data received from web portal (e.g., portal closed abruptly). Agent not created.",
                    fg="yellow",
                )
            )
        sys.exit(1)
