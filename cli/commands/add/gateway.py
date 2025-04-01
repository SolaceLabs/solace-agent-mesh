import os
import sys
import click

from cli.utils import get_display_path, load_template, log_error, get_formatted_names
from cli.commands.plugin.build import get_all_plugin_gateway_interfaces
from cli.config import Config

def _add_python_files(modules_directory, template_args, created_file_names):
    # Creating the python files
    module_directory = os.path.join(
        modules_directory,
        "gateways",
        template_args["SNAKE_CASE_NAME"],
    )
    # Create the gateway directory
    os.makedirs(module_directory, exist_ok=True)
    # Create the __init__.py file
    init_file = os.path.join(module_directory, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("")
    created_file_names.append(init_file)

    # Create the gateway python file
    for gateways_file in ["base", "input", "output"]:
        gateway_path = os.path.join(
            module_directory,
            f"{template_args['SNAKE_CASE_NAME']}_{gateways_file}.py",
        )
        gateway_template = load_template(f"gateway_{gateways_file}.py", template_args)
        if not os.path.exists(gateway_path):
            with open(gateway_path, "w", encoding="utf-8") as f:
                f.write(gateway_template)
        created_file_names.append(gateway_path)

def add_gateway_command(name, interfaces):
    """
    Creates a gateway configuration directory and files based on provided templates.

    This function performs the following steps:
    1. Creates a directory for the gateway in the specified configuration directory.
    2. Copies a gateway configuration template file to the new gateway directory.
    3. If a list of interfaces is provided, creates configuration files for each interface based on corresponding templates.

    Args:
        interfaces (list): A list of interface names for which configuration files should be created.
        formatted_name (dict): A dictionary containing the formatted name of the gateway.
                               The key "SNAKE_CASE_NAME" is used to name the gateway directory.

    Returns:
        int: Returns 1 if an IOError occurs during the creation of the gateway configuration, otherwise returns None.

    Raises:
        IOError: If there is an error creating the gateway configuration files or directories.
    """

    # Name must be kebab-case, and only character, numbers, and hyphens are allowed
    if not name.islower() or not name.replace("-", "").isalnum():
        log_error(
            "Error: Name must be kebab-case. Only lowercase letters, numbers, and hyphens are allowed.",
        )
        return 1

    formatted_name = get_formatted_names(name)
    created_file_names = []

    try:
        # Create a directory for the gateway in the config directory
        config = click.get_current_context().obj["solace_agent_mesh"]
        config_directory = config["config_directory"]
        gateway_directory = os.path.join(
            config_directory, "gateways", formatted_name["SNAKE_CASE_NAME"]
        )

        def abort():
            sys.exit(1)

        plugin_gateway_interfaces = get_all_plugin_gateway_interfaces(config, abort)

        # Check if the gateway directory already exists
        if os.path.exists(gateway_directory):
            overwrite = click.confirm(
                f"Gateway directory {gateway_directory} already exists. Do you want to overwrite it?",
                default=False,
            )
            if not overwrite:
                click.echo("Gateway template not created.")
                return
        os.makedirs(gateway_directory, exist_ok=True)

        # Create the gateway config file from the template directory
        # The file name is gateway-default-config.yaml but write it as gateway.yaml in the gateway_directory
        gateway_config_template = load_template("gateway-default-config.yaml")
        gateway_config_path = os.path.join(gateway_directory, "gateway.yaml")
        with open(gateway_config_path, "w", encoding="utf-8") as f:
            f.write(gateway_config_template)

        created_file_names.append(gateway_config_path)

        # If the interface list is not empty, create the interface config files
        if interfaces:
            for interface in interfaces:
                # Load the interface template from the templates directory.
                # The name will be {interface}-default-config.yaml
                # Write the file as {interface}.yaml in the gateway_directory
                if interface in plugin_gateway_interfaces:
                    interface_default_path = os.path.join(
                        plugin_gateway_interfaces[interface],
                        f"{interface}-default-config.yaml",
                    )
                    if not os.path.exists(interface_default_path):
                        log_error("Error: Interface template not found.")
                        return 1
                    with open(interface_default_path, "r", encoding="utf-8") as g:
                        interface_template = g.read()
                else:
                    interface_template = load_template(
                        f"{interface}-default-config.yaml"
                    )
                    if not interface_template:
                        log_error("Error: Interface template not found.")
                        return 1

                interface_config_path = os.path.join(
                    gateway_directory, f"{interface}.yaml"
                )
                with open(interface_config_path, "w", encoding="utf-8") as f:
                    f.write(interface_template)

                created_file_names.append(interface_config_path)

        else:
            click.echo(click.style("No interfaces provided. A gateway from scratch will be created.", fg="yellow"))
            try:
                # Create the gateway config file
                interface_config_path = os.path.join(
                    gateway_directory,
                    f"{formatted_name['SNAKE_CASE_NAME']}.yaml",
                )
                gateway_template = load_template("gateway-config-template.yaml", formatted_name)
                if not os.path.exists(interface_config_path):
                    with open(interface_config_path, "w", encoding="utf-8") as f:
                        f.write(gateway_template)
                created_file_names.append(interface_config_path)

                _add_python_files(config["modules_directory"], formatted_name, created_file_names)
            except IOError as e:
                log_error(f"Error creating gateway, gateway config was created: {e}")
                return 1
            
        temp_file = os.path.join(config_directory, "__TEMPLATES_WILL_BE_HERE__")
        if os.path.exists(temp_file):
            os.remove(temp_file)

    except IOError as e:
        log_error(f"Error creating gateway config: {e}")
        return 1
    
    finally:
        if created_file_names:
            click.echo("Created the following gateway template files:")
            for file_name in created_file_names:
                click.echo(f"  - {get_display_path(file_name)}")


def add_interface_command(name):
    """
    Creates a new gateway interface with the provided name.
    """
    config = Config.get_plugin_config()
    plugin_config = config.get("solace_agent_mesh_plugin", {})
    plugin_name = plugin_config.get("name")
    if not plugin_name or plugin_name == "solace-agent-mesh-plugin":
        log_error("Could not find a valid plugin project")
        return 1
    
    plugin_name = plugin_name.replace("-","_")
    template_args = get_formatted_names(name)
    template_args.update({
        "MODULE_DIRECTORY": f"{plugin_name}.src"
    })
    created_file_names = []

    interfaces_directory = os.path.join("interfaces")
    modules_directory = os.path.join("src")

    try:
        os.makedirs(interfaces_directory, exist_ok=True)

        temp_file = os.path.join(interfaces_directory, "__INTERFACES_WILL_BE_HERE__")
        if os.path.exists(temp_file):
            os.remove(temp_file)

        # Create the interface flows and config file
        interface_flows_path = os.path.join(interfaces_directory, f"{template_args['HYPHENED_NAME']}-flows.yaml")
        interface_config_path = os.path.join(interfaces_directory, f"{template_args['HYPHENED_NAME']}-default-config.yaml")

        interface_flows_template = load_template("gateway-flows.yaml", template_args)
        interface_flows_template = interface_flows_template.replace(" src.gateway", " solace_agent_mesh.src.gateway")
        if not os.path.exists(interface_flows_path):
            with open(interface_flows_path, "w", encoding="utf-8") as f:
                f.write(interface_flows_template)
        created_file_names.append(interface_flows_path)

        interface_config_template = load_template("gateway-config-template.yaml", template_args)
        if not os.path.exists(interface_config_path):
            with open(interface_config_path, "w", encoding="utf-8") as f:
                f.write(interface_config_template)
        created_file_names.append(interface_config_path)

        _add_python_files(modules_directory, template_args, created_file_names)

        # Update the 'solace-agent-mesh-plugin' configuration file
        plugin_config["includes_gateway_interface"] = True
        plugin_gateway_config_template = load_template("plugin-gateway-default-config.yaml", parser=Config.get_yaml_parser())
        if not plugin_gateway_config_template:
            log_error("Error: Plugin gateway config template not found.")
        else:
            if "interface_gateway_configs" not in plugin_config:
                plugin_config["interface_gateway_configs"] = {}
            plugin_config["interface_gateway_configs"][template_args["HYPHENED_NAME"]] = plugin_gateway_config_template.get("plugin_gateway_default_config", {})
            Config.write_config(config, Config.user_plugin_config_file)
            click.echo(f"Updated {Config.user_plugin_config_file} with default gateway interface configuration for {template_args['HYPHENED_NAME']}")

    except IOError as e:
        log_error(f"Error creating gateway interface, {e}")
        return 1
    
    finally:
        if created_file_names:
            click.echo("Created the following gateway template files:")
            for file_name in created_file_names:
                click.echo(f"  - {get_display_path(file_name)}")