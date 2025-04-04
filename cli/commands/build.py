import os
import sys
import click
import shutil
import re
from functools import partial

from cli.commands.init import init_command
from cli.commands.plugin.build import get_all_plugin_gateway_interfaces, build_plugins
from cli.config import Config
from cli.utils import (
    literal_format_template,
    load_template,
    get_cli_root_dir,
    extract_yaml_env_variables,
    get_display_path,
    log_error,
    apply_document_parsers,
    normalize_and_reindent_yaml
)


def abort_cleanup(build_dir):
    """Abort the build and cleanup the build directory."""
    log_error("Build aborted.")
    click.echo("Cleaning up build directory.")
    os.system(f"rm -rf {build_dir}")
    sys.exit(1)


def write_env_variables(env_variables, output_file, default_env_vars):
    """Extract environment variables to a file."""

    try:
        env_variables = list(sorted(env_variables))
        # Check if directory exists
        if not os.path.exists(output_file):
            dir_name = os.path.dirname(output_file)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

        existing_env_variables = []
        # Check if the file exists
        if os.path.exists(output_file):
            # Read existing env variables
            with open(output_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
                existing_env_variables = [
                    line.split("=")[0].strip() for line in lines if "=" in line
                ]

        # Remove existing env variables
        env_variables = [
            env_var
            for env_var in env_variables
            if env_var not in existing_env_variables
        ]

        # Create env file content
        env_file_content = ""
        for env_var in env_variables:
            env_file_content += f"{env_var}=\n"

        # Add default env variables
        for key, value in default_env_vars.items():
            if key not in existing_env_variables:
                env_file_content += f"{key}={value}\n"

        # Append to the file
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(env_file_content)
        click.echo(
            f"Environment variables extracted to {get_display_path(output_file)}"
        )
    except Exception as e:
        click.echo(f"Something went wrong in extract environment variables to a file")


def resolve_relative_import_path_hof(module_name):
    """Replaces all src.path imports with the the provided module name
    Only paths that are in the packages artifact are replaced
    """
    root_dir = get_cli_root_dir()
    # All directories in the root directory
    directories = [
        d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))
    ]
    # Acceptable relative directories
    relative_directories_pair = [
        (f" src.{dir}", f" {module_name}.{dir}") for dir in directories
    ]

    def resolve_relative_import_path(file_content, meta):
        if "skip_relative_import_path" in meta and meta["skip_relative_import_path"]:
            return file_content
        for relative_dir, module_dir in relative_directories_pair:
            file_content = file_content.replace(relative_dir, module_dir)
        return file_content

    return resolve_relative_import_path


def build_agents(config, build_config_dir, abort, parsers):
    configs_path = config["config_directory"]
    agent_config_path = os.path.join(configs_path, "agents")
    # Check if the agents directory exists
    if not os.path.exists(agent_config_path):
        click.echo(
            f"No user defined agents were found at '{get_display_path(agent_config_path)}'."
        )
    else:
        click.echo("Building agents.")
        # Get all agent configuration files
        agent_configs = [
            f for f in os.listdir(agent_config_path) if f.endswith(".yaml")
        ]
        for agent_config in agent_configs:
            try:
                # Read agent configuration file
                agent_config_file = os.path.join(agent_config_path, agent_config)
                with open(agent_config_file, "r", encoding="utf-8") as f:
                    agent_config_content = f.read()
                # Apply document parsers
                meta = {"skip_relative_import_path": True}
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
                    f'Error reading agent configuration file for "{agent_config}": {e}'
                )
                abort()
            except Exception as e:
                log_error(
                    f'Error building agent configuration for "{agent_config}": {e}'
                )
                abort()


def build_gateways(config, build_config_dir, abort, parsers, plugin_gateway_interfaces):
    configs_path = config["config_directory"]
    gateways_config_path = os.path.join(configs_path, "gateways")

    # Check if the gateways directory exists
    if not os.path.exists(gateways_config_path):
        click.echo(
            f"No user defined gateways were found at '{get_display_path(gateways_config_path)}'."
        )
    else:
        click.echo("Building gateways.")

        # Loop over the subdirectories of gateways_config_path
        for subdir in os.listdir(gateways_config_path):
            build_specific_gateway(
                build_config_dir,
                abort,
                parsers,
                gateways_config_path,
                subdir,
                plugin_gateway_interfaces,
            )


def build_specific_gateway(
    build_config_dir,
    abort,
    parsers,
    gateways_config_path,
    gateway_name,
    known_plugin_interfaces=[],
):
    subdir_path = os.path.join(gateways_config_path, gateway_name)
    if os.path.isdir(subdir_path):
        click.echo(f"Building gateway in subdirectory: {gateway_name}")

        try:
            click.echo("Building gateway template.")
            # Load common header and gateway config
            gateway_header_template = load_template("gateway-header.yaml")
            gateway_config_file = os.path.join(subdir_path, "gateway.yaml")
            with open(gateway_config_file, "r", encoding="utf-8") as g:
                gateway_config_content = g.read()
                
            # Define config aliases to check for so that if they are missing we can add defaults
            config_aliases = {
                "response_format_prompt": "- response_format_prompt: &response_format_prompt \"\""
            }
            
            # Check which aliases are already in the gateway config
            gateway_found_aliases = set()
            for alias in config_aliases:
                if f"&{alias}" in gateway_config_content:
                    gateway_found_aliases.add(alias)

            click.echo("Getting interface types.")
            known_interfaces = ["slack", "web", "rest-api"]
            interface_files = []

            # Find the interface types by looking at the files in the subdirectory
            for file in os.listdir(subdir_path):
                if (
                    file.endswith(".yaml")
                    and file != "gateway.yaml"
                    and not file.endswith("-flows.yaml")
                ):
                    interface_files.append(file)

            # Process interfaces
            for interface_file in interface_files:
                interface_name = interface_file.split(".yaml")[0]
                if gateway_name == interface_name:
                    interface_config = (
                        f"gateway_{gateway_name}.yaml"
                    )
                    gateway_id = gateway_name
                else:
                    interface_config = (
                        f"gateway_{gateway_name}_{interface_name.replace('-', '_')}.yaml"
                    )
                    gateway_id = f"{gateway_name}_{interface_name}"
                interface_build_path = os.path.join(build_config_dir, interface_config)

                complete_interface_gateway = gateway_header_template
   
                reindented_gateway_config_content = normalize_and_reindent_yaml(complete_interface_gateway, gateway_config_content)
                complete_interface_gateway += reindented_gateway_config_content

                # interface specific config
                interface_config_file = os.path.join(subdir_path, interface_file)
                with open(interface_config_file, "r", encoding="utf-8") as g:
                    file_content = g.read()
                    
                # Check which aliases are in the interface config
                interface_found_aliases = set()
                for alias in config_aliases:
                    if f"&{alias}" in file_content:
                        interface_found_aliases.add(alias)
                
                reindented_file_content = normalize_and_reindent_yaml(complete_interface_gateway, file_content)
                complete_interface_gateway += reindented_file_content

                # Add any missing config aliases
                missing_aliases = set(config_aliases.keys()) - gateway_found_aliases - interface_found_aliases
                if missing_aliases:
                    complete_interface_gateway += "\n# Default configurations\nshared_config_defaults:\n"
                    for alias in missing_aliases:
                        complete_interface_gateway += f"{config_aliases[alias]}\n"

                # Write interface specific flows
                complete_interface_gateway += "\nflows:\n"

                if interface_name in known_interfaces:
                    custom_interface_flows_path = os.path.join(
                        subdir_path, f"{interface_name}-flows.yaml"
                    )
                    # First check for custom flow file, fall back to template
                    if os.path.exists(custom_interface_flows_path):
                        with open(
                            custom_interface_flows_path, "r", encoding="utf-8"
                        ) as g:
                            flow_content = g.read()
                    else:
                        flow_content = load_template(f"{interface_name}-flows.yaml")
                    complete_interface_gateway += flow_content
                elif interface_name in known_plugin_interfaces:
                    # Write interface specific flows
                    interface_flows_path = os.path.join(
                        known_plugin_interfaces[interface_name],
                        f"{interface_name}-flows.yaml",
                    )
                    try:
                        with open(interface_flows_path, "r", encoding="utf-8") as g:
                            interface_flow_template_file = g.read()
                    except IOError as e:
                        log_error(
                            f'Expected plugin flow file "{interface_name}-flows.yaml" is not present.'
                        )
                        abort()
                    complete_interface_gateway += interface_flow_template_file
                else:
                    # This is a custom interface. The related flows can be in
                    # the same directory as the interface config and end with -flows.yaml
                    # or it will use the default flows template
                    custom_interface_flows_path = os.path.join(
                        subdir_path, f"{interface_name}-flows.yaml"
                    )
                    
                    if os.path.exists(custom_interface_flows_path):
                        with open(
                            custom_interface_flows_path, "r", encoding="utf-8"
                        ) as g:
                            interface_flow_template_file = g.read()
                    else:
                        interface_flow_template_file = load_template("gateway-flows.yaml")

                    complete_interface_gateway += interface_flow_template_file

                # Apply parsers to gateway config for this interface
                meta = {
                    "extra_literals": {
                        "GATEWAY_ID": gateway_id,
                        "SNAKE_CASE_NAME": gateway_id.replace("-", "_"),
                    }
                }

                complete_interface_gateway = apply_document_parsers(
                    complete_interface_gateway, parsers, meta
                )
                with open(interface_build_path, "w", encoding="utf-8") as f:
                    f.write(complete_interface_gateway)

        except IOError as e:
            log_error(
                f'Error reading gateway configuration file for "{gateway_name}": {e}'
            )
            abort()
        except Exception as e:
            log_error(f'Error building gateway configuration for "{gateway_name}": {e}')
            abort()


def build_built_in_agents(config, build_config_dir, abort, parsers):
    ### Built-in agents
    click.echo("Building built-in agents.")
    built_in_agents = config["built_in"]["agents"]
    filtered_agent_names = [
        f"agent_{agent.get('name')}.yaml"
        for agent in built_in_agents
        if agent.get("name") and agent.get("enabled")
    ]
    agents_config_source_path = os.path.join(get_cli_root_dir(), "configs")

    for agent in filtered_agent_names:
        # Check if agent exists
        agent_config_file = os.path.join(agents_config_source_path, agent)
        if not os.path.exists(agent_config_file):
            log_error(
                f"Error: Built-in agent configuration file for {agent} not found.",
            )
            abort()
        try:
            # Read agent configuration file
            with open(agent_config_file, "r", encoding="utf-8") as f:
                agent_config_content = f.read()
            # Apply document parsers
            agent_config_content = apply_document_parsers(agent_config_content, parsers)
            # Write agent configuration to build directory
            agent_build_path = os.path.join(build_config_dir, agent)
            with open(agent_build_path, "w", encoding="utf-8") as f:
                f.write(agent_config_content)
        except IOError as e:
            log_error(
                f"Error reading built-in agent configuration file for {agent}: {e}",
            )
            abort()
        except Exception as e:
            log_error(
                f"Error building built-in agent configuration for {agent}: {e}",
            )
            abort()


def build_solace_agent_mesh(config, build_config_dir, abort, parsers):
    click.echo("Building configs required for Solace Agent Mesh.")
    configs_source_path = os.path.join(get_cli_root_dir(), "configs")
    # Prefixes to skip
    skip_prefixes = ["agent", "gateway", "_"]
    # Get all config file names
    config_files = [
        f
        for f in os.listdir(configs_source_path)
        if f.endswith(".yaml")
        and not any(f.startswith(prefix) for prefix in skip_prefixes)
    ]
    for config_file in config_files:
        try:
            # Read config file
            config_file_path = os.path.join(configs_source_path, config_file)
            with open(config_file_path, "r", encoding="utf-8") as f:
                config_content = f.read()
            if not config_content.strip():
                continue
            # Apply document parsers
            config_content = apply_document_parsers(config_content, parsers)
            # Write config to build directory
            config_build_path = os.path.join(build_config_dir, config_file)
            with open(config_build_path, "w", encoding="utf-8") as f:
                f.write(config_content)
        except IOError as e:
            log_error(
                f'Error reading config file for "{config_file}": {e}',
            )
            abort()
        except Exception as e:
            log_error(
                f'Error building config file for "{config_file}": {e}',
            )
            abort()


def build_runtime_config(config, build_config_dir, abort):
    runtime_config_path = os.path.join(build_config_dir, "config.yaml")
    runtime_config = config.get("runtime", {})
    try:
        Config.write_config(runtime_config, runtime_config_path)
        click.echo(f"Created runtime config at {get_display_path(runtime_config_path)}")
    except IOError as e:
        log_error(f"Error writing runtime config file: {e}")
        abort()


def build_force_overwrite(config, build_config_dir, abort, parsers, overwrite_src_path):
    """
    Overwriting default system config files with user provide overwrite files
    """
    # Check if the overwrite directory exists
    if not os.path.exists(overwrite_src_path):
        return
    click.echo(
        f"Force overwriting default config files with provided files from '{get_display_path(overwrite_src_path)}'."
    )
    overwrite_files = [f for f in os.listdir(overwrite_src_path) if f.endswith(".yaml")]
    for overwrite_file in overwrite_files:
        try:
            # Read overwrite file
            overwrite_file_path = os.path.join(overwrite_src_path, overwrite_file)
            with open(overwrite_file_path, "r", encoding="utf-8") as f:
                overwrite_content = f.read()
            if not overwrite_content.strip():
                continue
            # Apply document parsers
            overwrite_content = apply_document_parsers(overwrite_content, parsers)
            # Write overwrite to build directory
            overwrite_build_path = os.path.join(build_config_dir, overwrite_file)
            with open(overwrite_build_path, "w", encoding="utf-8") as f:
                f.write(overwrite_content)
        except IOError as e:
            log_error(
                f'Error reading overwrite file for "{overwrite_file}": {e}',
            )
            abort()
        except Exception as e:
            log_error(
                f'Error building overwrite file for "{overwrite_file}": {e}',
            )
            abort()


def build_command(skip_without_asking=False, no_init=False):
    """Build the Solace Agent Mesh application."""
    config_path = Config.user_config_file
    config = click.get_current_context().obj["solace_agent_mesh"]

    if not os.path.exists(config_path) and not no_init:
        init_command({"skip": skip_without_asking})
        config = Config.get_config(config_path).get("solace_agent_mesh")

    click.echo("Building Solace Agent Mesh application")
    configs_path = config["config_directory"]
    modules_path = config["modules_directory"]
    build_dir = config["build"]["build_directory"]

    build_config_dir = os.path.join(build_dir, "configs")
    abort = partial(abort_cleanup, build_dir)

    skip_user_configs = False

    # List of all required env variables
    env_variables = set()

    orchestrator_instance_count = str(config["build"].get("orchestrator_instance_count"))
    # check if it's a number
    if not orchestrator_instance_count.isdigit():
        log_error("Orchestrator instance count must be a number.")
        abort()

    # Format literals
    format_literals = {
        "MODULE_DIRECTORY": modules_path.replace("\\", ".").replace("/", "."),
        "ORCHESTRATOR_INSTANCE_COUNT": orchestrator_instance_count,
    }

    ####################
    # Document Parsers #
    ####################
    parsers = []

    ### ENV Parser
    def extract_env_var(content, _):
        # Extract environment variables from the config
        variables = extract_yaml_env_variables(content)
        for var in variables:
            env_variables.add(var)
        return content

    parsers.append(extract_env_var)

    ### Log level override
    log_level = config["build"].get("log_level_override")

    def log_level_override(content, _):
        if log_level:
            content = re.sub(
                r"log_file_level: \w+", f"log_file_level: {log_level}", content
            )
            content = re.sub(
                r"stdout_log_level: \w+", f"stdout_log_level: {log_level}", content
            )
        return content

    parsers.append(log_level_override)
    ### Relative import path resolver Parser
    resolve_relative_import_path = resolve_relative_import_path_hof("solace_agent_mesh")
    parsers.append(resolve_relative_import_path)

    ### Literal formatter Parser
    def format_literals_parser(content, meta):
        if "extra_literals" in meta and meta["extra_literals"]:
            return literal_format_template(
                content,
                {
                    **format_literals,
                    **meta["extra_literals"],
                },
            )
        return literal_format_template(content, format_literals)

    parsers.append(format_literals_parser)

    ########################
    # Handling Directories #
    ########################

    # Check if the config directory exists
    if not os.path.exists(configs_path):
        if skip_without_asking:
            click.echo(
                f"No user defined components were found at '{get_display_path(configs_path)}'."
            )
            skip_user_configs = True
        else:
            skip_user_configs = click.confirm(
                f"No user defined components were found at '{get_display_path(configs_path)}'. Do you want to continue the build?",
                default=False,
            )
            if not skip_user_configs:
                log_error("Build aborted.")
                return 1

    try:
        # Delete build directory if it exists
        if os.path.exists(build_dir):
            os.system(f"rm -rf {build_dir}")
        # Create recursive directories if they don't exist
        os.makedirs(build_config_dir, exist_ok=True)
    except IOError as e:
        log_error(f"Error creating build directory: {e}")
        abort()

    plugin_gateway_interfaces = get_all_plugin_gateway_interfaces(config, abort)
    ####################
    # Building Plugins #
    ####################
    if "plugins" in config and isinstance(config["plugins"], list):
        build_plugins(
            config,
            build_config_dir,
            abort,
            parsers,
            plugin_gateway_interfaces,
            build_specific_gateway,
        )

    ########################
    # User Defined Configs #
    ########################
    if skip_user_configs:
        click.echo("Skipping user defined components.")
    else:
        ####################
        # Building Modules #
        ####################
        try:
            if not os.path.exists(modules_path):
                click.echo(
                    f"No user defined modules were found at '{get_display_path(modules_path)}'."
                )
            else:
                click.echo("Building modules.")
                os.system(f"cp -r {modules_path} {build_dir}")
        except IOError as e:
            log_error(f"Error copying modules directory: {e}")
            abort()

        ###################
        # Building Agents #
        ###################
        build_agents(config, build_config_dir, abort, parsers)

        #####################
        # Building Gateways #
        #####################
        build_gateways(
            config, build_config_dir, abort, parsers, plugin_gateway_interfaces
        )

    ############################
    # Building Built-in Agents #
    ############################
    build_built_in_agents(config, build_config_dir, abort, parsers)

    ###########################
    # Building Solace Agent Mesh #
    ###########################
    build_solace_agent_mesh(config, build_config_dir, abort, parsers)

    ###########################
    # Building Runtime Config #
    ###########################
    build_runtime_config(config, build_dir, abort)

    ############################
    # Building Force Overwrite #
    ############################
    overwrite_src_path = config.get("overwrite_directory")
    overwrite_plugins_path = os.path.join(build_dir, "overwrites")
    if os.path.exists(overwrite_plugins_path):
        build_force_overwrite(
            config, build_config_dir, abort, parsers, overwrite_plugins_path
        )
        # remove the overwrite directory
        shutil.rmtree(overwrite_plugins_path)

    build_force_overwrite(config, build_config_dir, abort, parsers, overwrite_src_path)

    ####################
    # Default ENV Vars #
    ####################
    default_env_vars = {
        "RUNTIME_CONFIG_PATH": os.path.join(build_dir, "config.yaml"),
    }
    # Handle environment variables
    if config["build"]["extract_env_vars"]:
        write_env_variables(env_variables, config["env_file"], default_env_vars)

    # Build completed
    click.echo(click.style("Build completed.", bold=True, fg="green"))
    click.echo(f"\tBuild directory: {get_display_path(build_dir)}")
    return 0
