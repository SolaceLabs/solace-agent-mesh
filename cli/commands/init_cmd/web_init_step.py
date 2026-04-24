import multiprocessing
import sys
import webbrowser

import click

from ...utils import wait_for_server


def perform_web_init(current_cli_params: dict) -> dict:
    """
    Launches the web-based configuration portal and updates params.
    """
    # Lazy import to avoid loading Flask at CLI startup
    try:
        from config_portal.backend.server import run_flask
    except ImportError as e:
        click.echo(
            click.style(
                f"Critical Error: Could not import run_flask from config_portal.backend.server. Error: {e}\n",
                fg="red",
            ),
            err=True,
        )
        click.echo(click.style("Aborting web-based initialization.", fg="red"), err=True)
        sys.exit(1)

    click.echo(
        click.style("Attempting to start web-based configuration portal...", fg="blue")
    )

    with multiprocessing.Manager() as manager:
        shared_config_from_web = manager.dict()
        init_gui_process = multiprocessing.Process(
            target=run_flask, args=("127.0.0.1", 5002, shared_config_from_web)
        )
        init_gui_process.start()
        portal_url = "http://127.0.0.1:5002"
        click.echo(
            click.style(
                f"Web configuration portal is running at {portal_url}",
                fg="green",
            )
        )
        if wait_for_server(portal_url):
            try:
                webbrowser.open(portal_url)
            except Exception:
                click.echo(
                    click.style(
                        f"Could not automatically open browser, Please open {portal_url} manually.",
                        fg="yellow",
                    )
                )
        else:
            click.echo(
                click.style(
                    "Server did not start in time. Please check for errors and try again.",
                    fg="red",
                )
            )

        click.echo(
            "Complete the configuration in your browser. The CLI will resume once the portal is closed or submits data."
        )

        init_gui_process.join()
        if shared_config_from_web:
            config_from_portal = dict(shared_config_from_web)

            click.echo(
                click.style("Configuration received from web portal.", fg="green")
            )

            for key, value in config_from_portal.items():
                current_cli_params[key] = value
        else:
            click.echo(
                click.style(
                    "No configuration data received from web portal, or portal was closed without saving.",
                    fg="yellow",
                )
            )
            click.echo(
                click.style(
                    "Proceeding with values from CLI options or defaults if available.",
                    fg="yellow",
                )
            )

    return current_cli_params
