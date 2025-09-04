import multiprocessing
import sys
import webbrowser

import click

from ...utils import wait_for_server

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


def perform_web_init(current_cli_params: dict) -> dict:
    """
    Launches the web-based configuration portal and updates params.
    """

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

            # Map web portal keys to CLI expected keys for backwards compatibility
            key_mappings = {
                "llm_api_key": "llm_service_api_key",
                "llm_endpoint_url": "llm_service_endpoint",
                "llm_model_name": "llm_service_model_name",
            }

            for old_key, new_key in key_mappings.items():
                if old_key in config_from_portal and new_key not in config_from_portal:
                    config_from_portal[new_key] = config_from_portal[old_key]

            # Handle planning and general model names with fallback to single model name
            config_from_portal["llm_service_planning_model_name"] = (
                config_from_portal.get("llm_service_planning_model_name")
                or config_from_portal.get("llm_planning_model_name")
                or config_from_portal.get("llm_model_name")
            )

            config_from_portal["llm_service_general_model_name"] = (
                config_from_portal.get("llm_service_general_model_name")
                or config_from_portal.get("llm_general_model_name")
                or config_from_portal.get("llm_model_name")
            )

            # Clean up deprecated keys if new keys are present
            config_from_portal.pop("llm_planning_model_name", None)
            config_from_portal.pop("llm_general_model_name", None)

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
