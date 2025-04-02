import subprocess
import os
import click

from cli.utils import log_error, apply_document_parsers, load_plugin
from cli.config import Config


def build_command():
    """Builds the plugin python module."""
    subprocess.check_call(["python", "-m", "build"])


def get_all_plugin_gateway_interfaces(config, abort, return_plugin_config=False):
    plugins = config.get("plugins", [])
    gateway_interfaces = {}

    for plugin in plugins:
        if plugin.get("includes_gateway_interface"):
            name = plugin.get("name")
            plugin_path = load_plugin(name, return_path_only=True)
            if not plugin_path:
                log_error(f"Plugin '{name}' is not installed.")
                abort()
            interface_path = os.path.join(plugin_path, "interfaces")

            if not os.path.exists(interface_path):
                continue

            interface_gateway_configs = (Config.load_config(os.path.join(plugin_path, Config.user_plugin_config_file)) or {}).get("solace_agent_mesh_plugin", {}).get("interface_gateway_configs", {})
            interface_gateway_config = None
            # Ensuring flow and default pair exist
            interface_pairs = {}
            for file in os.listdir(interface_path):
                if file.endswith("-flows.yaml") :
                    name = file.split("-flows.yaml")[0]
                    if name not in interface_pairs:
                        interface_pairs[name] = []
                    interface_pairs[name].append(file)

                elif file.endswith("-default-config.yaml"):
                    name = file.split("-default-config.yaml")[0]
                    if name not in interface_pairs:
                        interface_pairs[name] = []
                    interface_pairs[name].append(file)
            
            for name, files in interface_pairs.items():
                if len(files) == 2:
                    if return_plugin_config:
                        for interface_name, interface_config in interface_gateway_configs.items():
                            if interface_name == name.replace("-", "_"):
                                interface_gateway_config = interface_config
                                break
                        gateway_interfaces[name] = (interface_path, interface_gateway_config)
                    else:
                        gateway_interfaces[name] = interface_path
        
    return gateway_interfaces


def build_plugins(config, build_config_dir, abort, parsers, plugin_gateway_interfaces, build_specific_gateway):
    plugins = config.get("plugins", [])
    plugins_overwrite_dir = os.path.join(build_config_dir, "..", "overwrites")

    os.makedirs(build_config_dir, exist_ok=True)
    os.makedirs(plugins_overwrite_dir, exist_ok=True)

    for plugin in plugins:
        click.echo("Building plugin: " + plugin.get("name"))
        name = plugin.get("name")
        load_unspecified_files = plugin.get("load_unspecified_files", True)
        load = plugin.get("load", {})
        agents_to_load = [agent.replace("-", "_") for agent in (load.get("agents") or [])]
        gateways_to_load = load.get("gateways") or []
        overwrites_to_load = load.get("overwrites") or []

        plugin_path = load_plugin(name, return_path_only=True)
        if not plugin_path:
            log_error(f"Plugin '{name}' is not installed.")
            abort()

        try:
            # Path to plugin config in the module
            plugin_file_path = os.path.join(plugin_path, Config.user_plugin_config_file)
            plugin_config = Config.load_config(plugin_file_path)

            if not plugin_config or "solace_agent_mesh_plugin" not in plugin_config:
                raise ValueError("Invalid solace-agent-mesh plugin module.")
        except Exception:
            log_error(
                f"Error loading plugin '{name}': Invalid solace-agent-mesh plugin module."
            )
            abort()

        ################
        # Build Agents #
        ################
        agent_config_path = os.path.join(plugin_path, "configs", "agents")
        if os.path.exists(agent_config_path):
            click.echo("Building agents for plugin: " + name)
            # Get all agent configuration files
            agent_configs = [
                f for f in os.listdir(agent_config_path) if f.endswith(".yaml")
            ]
            yaml_agents = [f"{agent}.yaml" for agent in agents_to_load]
            if not load_unspecified_files:
                agent_configs = [f for f in agent_configs if f in yaml_agents]

            # Ensuring all user requested agents are present
            for agent_config in yaml_agents:
                if agent_config not in agent_configs:
                    log_error(
                        f"Agent '{agent_config[:-5]}' was not found in the plugin '{name}'"
                    )
                    abort()

            for agent_config in agent_configs:
                try:
                    # Read agent configuration file
                    agent_config_file = os.path.join(agent_config_path, agent_config)
                    with open(agent_config_file, "r", encoding="utf-8") as f:
                        agent_config_content = f.read()
                    # Apply document parsers
                    meta = {
                        "skip_relative_import_path": True,
                        "extra_literals": {
                            "MODULE_DIRECTORY": f"{name}.src",
                        },
                    }
                    agent_config_content = apply_document_parsers(
                        agent_config_content, parsers, meta
                    )
                    # Write agent configuration to build directory
                    agent_build_path = os.path.join(
                        build_config_dir, "agent_" + agent_config
                    )
                    with open(agent_build_path, "w", encoding="utf-8") as f:
                        f.write(agent_config_content)
                except IOError as e:
                    log_error(
                        f'Error reading agent configuration file for "{agent_config}" from plugin "{name}": {e}'
                    )
                    abort()
                except Exception as e:
                    log_error(
                        f'Error building agent configuration for "{agent_config}" from plugin "{name}": {e}'
                    )
                    abort()

        ##################
        # Build Gateways #
        ##################
        gateway_config_path = os.path.join(plugin_path, "configs", "gateways")
        gateway_dirs = [gateway.replace("-", "_") for gateway in gateways_to_load]
        if os.path.exists(gateway_config_path):
            gateway_subdirs = os.listdir(gateway_config_path)
            for gateway in gateway_dirs:
                if gateway not in gateway_subdirs:
                    log_error(
                        f"Gateway '{gateway}' was not found in the plugin '{name}'"
                    )
                    abort()

            # Loop over the subdirectories of gateways_config_path
            for gateway in gateway_subdirs:
                if load_unspecified_files or gateway in gateway_dirs:
                    build_specific_gateway(
                        build_config_dir, abort, parsers, gateway_config_path, gateway, plugin_gateway_interfaces
                    )

        ####################
        # Build Overwrites #
        ####################
        overwrite_config_path = os.path.join(plugin_path, "configs", "overwrite")
        if os.path.exists(overwrite_config_path):
            click.echo("Building overwrite for plugin: " + name)
            # Get all overwrite configuration files
            overwrite_configs = [
                f for f in os.listdir(overwrite_config_path) if f.endswith(".yaml")
            ]
            if not load_unspecified_files:
                overwrite_configs = [
                    f for f in overwrite_configs if f in overwrites_to_load
                ]

            # Ensuring all user requested overwrites are present
            for overwrite_config in overwrites_to_load:
                if overwrite_config not in overwrite_configs:
                    log_error(
                        f"Overwrite '{overwrite_config}' was not found in the plugin '{name}'"
                    )
                    abort()
            for overwrite_config in overwrite_configs:
                try:
                    # Read overwrite configuration file
                    overwrite_config_file = os.path.join(
                        overwrite_config_path, overwrite_config
                    )
                    with open(overwrite_config_file, "r", encoding="utf-8") as f:
                        overwrite_config_content = f.read()
                    # Apply document parsers
                    meta = {
                        "skip_relative_import_path": True,
                        "extra_literals": {
                            "MODULE_DIRECTORY": f"{name}.src",
                        },
                    }
                    overwrite_config_content = apply_document_parsers(
                        overwrite_config_content, parsers, meta
                    )
                    # Write overwrite configuration to build directory
                    overwrite_build_path = os.path.join(
                        plugins_overwrite_dir, overwrite_config
                    )
                    with open(overwrite_build_path, "w", encoding="utf-8") as f:
                        f.write(overwrite_config_content)
                except IOError as e:
                    log_error(
                        f'Error reading overwrite configuration file for "{overwrite_config}" from plugin "{name}": {e}'
                    )
                    abort()
                except Exception as e:
                    log_error(
                        f'Error building overwrite configuration for "{overwrite_config}" from plugin "{name}": {e}'
                    )
                    abort()
