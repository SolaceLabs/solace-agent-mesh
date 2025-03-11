import os
import subprocess
import click

from cli.utils import log_error, load_plugin
from cli.config import Config


def add_command(name: str, installer: str = None, from_url=None, add_all=False):
    """
    Add a new plugin to solace-agent-mesh config yaml
    Optional install the module if not found

    Args:
        name (str): The name of the plugin module to import.
        installer (str, optional): Installer to use if the module is not installed.
                                   Should be one of 'pip', 'poetry', 'conda', or None.
    """
    name = name.replace("-", "_")
    sam_config = Config.get_user_config()
    if not sam_config:
        sam_config = Config.get_default_config()

    if "plugins" not in sam_config["solace_agent_mesh"] or not sam_config["solace_agent_mesh"]["plugins"]:
        sam_config["solace_agent_mesh"]["plugins"] = []

    if any(plugin["name"] == name for plugin in sam_config["solace_agent_mesh"]["plugins"]):
        log_error(f"Plugin '{name}' already exists.")
        return 1
    
    # Attempt to import the module
    module, module_path = load_plugin(name)
    if not module:
        if installer:
            install_name = from_url or name
            click.echo(
                f"Module '{name}' not found. Attempting to install '{install_name}' using {installer}..."
            )
            if installer == "pip":
                subprocess.check_call(["pip3", "install", install_name])
            elif installer == "uv":
                subprocess.check_call(["uv", "pip", "install", install_name])
            elif installer == "poetry":
                subprocess.check_call(["poetry", "add", install_name])
            elif installer == "conda":
                subprocess.check_call(["conda", "install", install_name])
            else:
                log_error(f"Unsupported installer: {installer}")
                return 1
            # Retry importing after installation
            module, module_path = load_plugin(name)
            if not module:
                log_error(f"Failed to import module '{name}' after installation.")
                return 1

            # Adding to requirements.txt if exists and not already added
            if os.path.exists("requirements.txt"):
                with open("requirements.txt", "r", encoding="utf-8") as f:
                    requirements = f.read().splitlines()
                if install_name not in requirements:
                    with open("requirements.txt", "a", encoding="utf-8") as f:
                        f.write(f"\n{install_name}")
        else:
            log_error(
                f"Module '{name}' is not installed, and no installer was provided."
            )
            return 1

    # Path to plugin config in the module
    plugin_file_path = os.path.join(module_path, Config.user_plugin_config_file)

    if not os.path.exists(plugin_file_path):
        log_error("Invalid solace-agent-mesh plugin module.")
        return 1

    plugin_config = Config.load_config(plugin_file_path)

    if not plugin_config or "solace_agent_mesh_plugin" not in plugin_config:
        log_error("Invalid solace-agent-mesh plugin module.")
        return 1
    plugin_config = plugin_config["solace_agent_mesh_plugin"]

    plugin_data = {
        "name": name,
        "load_unspecified_files": add_all,
        "includes_gateway_interface": plugin_config.get("includes_gateway_interface", False),
        "load": {
            "agents": [],
            "gateways": [],
            "overwrites": [],
        },
    }

    if from_url:
        plugin_data["from_url"] = from_url

    sam_config["solace_agent_mesh"]["plugins"].append(plugin_data)
    Config.write_config(sam_config)

    click.echo(f"Successfully added plugin '{name}'.")
