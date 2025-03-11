import subprocess
import importlib.util
import click

from cli.utils import log_error
from cli.config import Config


def remove_command(name: str, installer: str = None):
    """
    Remove a plugin by removing it from solace-agent-mesh config yaml
    Optionally uninstall the module

    Args:
        name (str): The name of the module to remove.
        installer (str, optional): Installer to use for uninstallation.
                                   Should be one of 'pip', 'poetry', 'conda', or None.
    """
    name = name.replace("-", "_")
    sam_config = Config.get_user_config()
    if not sam_config:
        log_error("No configuration found.")
        return 1

    plugin = None
    plugins = sam_config.get("solace_agent_mesh", {}).get("plugins", [])
    for p in plugins:
        if p.get("name") == name:
            plugin = p
            plugins.remove(plugin)
            Config.write_config(sam_config)
            click.echo(f"Plugin '{name}' was removed from solace-agent-mesh config.")
            break

    if not plugin:
        log_error(f"Plugin '{name}' not found in the config.")
        return

    if installer:
        # Check if the module exists
        if importlib.util.find_spec(name) is None:
            log_error(
                f"Module '{name}' is not installed. Run without uninstall flag to just remove from config."
            )
            return 1

        # Attempt to uninstall using the specified installer
        click.echo(f"Attempting to uninstall module '{name}' using {installer}...")
        try:
            if installer == "pip":
                subprocess.check_call(["pip3", "uninstall", "-y", name])
            elif installer == "uv":
                subprocess.check_call(["uv", "pip", "uninstall", "-y", name])
            elif installer == "poetry":
                subprocess.check_call(["poetry", "remove", name])
            elif installer == "conda":
                subprocess.check_call(["conda", "remove", "-y", name])
            else:
                log_error(
                    f"Unsupported installer: {installer} - (pip, poetry, or conda)."
                )
                return 1
            click.echo(f"Successfully uninstalled module '{name}'.")
        except subprocess.CalledProcessError as e:
            log_error(f"Error occurred while uninstalling module '{name}': {e}")
            return 1
    else:
        click.echo(
            click.style(
                f"Module '{name}' was only removed from the config. Use your package manager to uninstall from environment.",
                fg="yellow",
            )
        )