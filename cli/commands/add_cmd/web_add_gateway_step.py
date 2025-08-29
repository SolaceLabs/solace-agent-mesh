import click
import multiprocessing
import webbrowser
from pathlib import Path
from cli.utils import wait_for_server


from config_portal.backend.server import run_flask


def launch_add_gateway_web_portal(cli_options: dict):
    """
    Launches the web-based configuration portal for adding a new gateway.
    The actual file writing will happen in the calling command after the portal returns data.

    Args:
        cli_options (dict): A dictionary that can contain initial values,
                              e.g., {'name': 'my-initial-gateway-name'}
                              This is passed to the Flask app.
    Returns:
        tuple | None: A tuple (gateway_name, gateway_options, project_root) if successful,
                      otherwise None.
    """
    click.echo(
        click.style("Attempting to start web-based 'Add Gateway' portal...", fg="blue")
    )

    with multiprocessing.Manager() as manager:
        shared_data_from_web = manager.dict()

        flask_process_args = ("127.0.0.1", 5002, shared_data_from_web)
        add_gateway_gui_process = multiprocessing.Process(
            target=run_flask, args=flask_process_args
        )
        add_gateway_gui_process.start()
        portal_url = "http://127.0.0.1:5002/?config_mode=addGateway"

        click.echo(
            click.style(
                f"Add Gateway portal is attempting to start. Waiting a moment...",
                fg="cyan",
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
        except Exception as e:
            click.echo(
                click.style(
                    f"Could not automatically open browser: {e}. Please open {portal_url} manually.",
                    fg="yellow",
                )
            )

        click.echo(
            "Complete the gateway configuration in your browser. The CLI will resume once the portal is closed or submits data."
        )

        add_gateway_gui_process.join()

        if shared_data_from_web:
            returned_data = dict(shared_data_from_web)
            if returned_data.get("status") == "success_from_gui_save":
                gateway_name_from_gui = returned_data.get("gateway_name_input")
                gateway_config_options = returned_data.get("config")

                if gateway_name_from_gui and gateway_config_options is not None:
                    click.echo(
                        click.style(
                            "Configuration received from web portal.", fg="cyan"
                        )
                    )
                    project_root = Path.cwd()
                    return gateway_name_from_gui, gateway_config_options, project_root
                else:
                    click.echo(
                        click.style(
                            f"Incomplete data received from web portal. Name: {gateway_name_from_gui}, Config: {gateway_config_options}",
                            fg="red",
                        ),
                        err=True,
                    )
            elif returned_data.get("status") == "shutdown_aborted":
                click.echo(
                    click.style(
                        f"Web portal feedback: {returned_data.get('message', 'Operation aborted by user.')}",
                        fg="yellow",
                    )
                )
            else:
                click.echo(
                    click.style(
                        f"Web portal operation failed or was cancelled. Message: {returned_data.get('message', 'No specific error message.')}",
                        fg="red",
                    ),
                    err=True,
                )
        else:
            click.echo(
                click.style(
                    "No data received from web portal (e.g., portal closed abruptly or server failed). Gateway not created.",
                    fg="yellow",
                ),
                err=True,
            )
        return None
