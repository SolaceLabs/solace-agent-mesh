import click
import multiprocessing
import webbrowser
import os
import time
from pathlib import Path
from cli.utils import error_exit, wait_for_server


config_portal_host = "CONFIG_PORTAL_HOST"


def run_flask_plugin_catalog(host, port, shared_data):
    try:
        from config_portal.backend.plugin_catalog_server import (
            create_plugin_catalog_app,
        )
        from config_portal.backend.plugin_catalog.constants import (
            PLUGIN_CATALOG_TEMP_DIR,
        )
    except ImportError:
        click.echo(
            click.style(
                "Error: Backend components for plugin catalog not found. Please ensure they are implemented.",
                fg="red",
            )
        )
        shared_data["status"] = "error_backend_missing"
        return

    temp_dir = Path(os.path.expanduser(PLUGIN_CATALOG_TEMP_DIR))
    temp_dir.mkdir(parents=True, exist_ok=True)

    app = create_plugin_catalog_app(shared_config=shared_data)
    click.echo(
        f"Starting Plugin Catalog backend on http://{host}:{port}/?config_mode=pluginCatalog"
    )
    try:
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        click.echo(click.style(f"Error starting Flask app: {e}", fg="red"))
        shared_data["status"] = f"error_flask_start: {e}"


@click.command("catalog", help="Launch the SAM Plugin catalog web interface.")
@click.option(
    "-p",
    "--port",
    default=5003,
    type=int,
    show_default=True,
    help="Port to run the plugin catalog web server on.",
)
@click.option(
    "--install-command",
    "installer_command",
    help="Command to use to install a python package. Must follow the format 'command {package} args'",
)
def catalog(port: int, installer_command: str):
    """Launches the SAM Plugin catalog web interface."""
    host = os.environ.get(config_portal_host, "127.0.0.1")
    try:
        if installer_command:
            installer_command.format(package="dummy")  # Test if the command is valid
            os.environ["SAM_PLUGIN_INSTALL_COMMAND"] = installer_command
    except (KeyError, ValueError):
        return error_exit(
            "Error: The installer command must contain a placeholder '{package}' to be replaced with the actual package name."
        )

    with multiprocessing.Manager() as manager:
        shared_data_from_web = manager.dict()
        shared_data_from_web["status"] = "initializing"
        _run_flask_target = run_flask_plugin_catalog

        gui_process = multiprocessing.Process(
            target=_run_flask_target, args=(host, port, shared_data_from_web)
        )
        gui_process.start()

        # Give the server a moment to start
        time.sleep(2)

        if shared_data_from_web.get(
            "status"
        ) == "initializing" or shared_data_from_web.get("status", "").startswith(
            "error_"
        ):
            backend_status = shared_data_from_web.get("status", "unknown_error")
            if backend_status == "initializing":
                click.echo(
                    click.style(
                        f"Plugin catalog backend is starting... If it takes too long, there might be an issue.",
                        fg="yellow",
                    )
                )
            else:
                click.echo(
                    click.style(
                        f"Plugin catalog backend failed to start properly ({backend_status}). Please check logs.",
                        fg="red",
                    )
                )
                if gui_process.is_alive():
                    gui_process.terminate()
                    gui_process.join(timeout=2)
                return  # Don't open browser if backend failed

        portal_url = f"http://{host}:{port}/?config_mode=pluginCatalog"
        click.echo(f"Opening Plugin Catalog at: {portal_url}")

        try:
            if wait_for_server(portal_url):
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

        try:
            gui_process.join()
        except KeyboardInterrupt:
            click.echo("Plugin Catalog interrupted by user. Shutting down...")
        finally:
            if gui_process.is_alive():
                click.echo("Terminating Plugin Catalog process...")
                gui_process.terminate()
                gui_process.join(timeout=5)
            if gui_process.is_alive():
                click.echo(
                    click.style("Forcibly killing Plugin Catalog process.", fg="yellow")
                )
                gui_process.kill()

        final_status = shared_data_from_web.get("status", "unknown_exit")
        if final_status == "shutdown_requested":
            click.echo("Plugin Catalog closed successfully.")
        else:
            click.echo(f"Plugin Catalog exited with status: {final_status}")
