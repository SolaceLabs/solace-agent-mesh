import os
import click

from cli.utils import log_error, load_plugin, get_display_path, get_formatted_names


def copy_from_plugin(name, plugin_name, entity_type):
    """
    Creates a template for an agent or gateway by copying from an existing plugin.

    name: Name of the component to create.
    plugin_name: Name of the plugin. This is either just the plugin or plugin:entity_name
                 for cases where the source config name is different from the destination name
    entity_type: Type of the entity to create. (agents or gateways)
    """
    if entity_type not in ["agents", "gateways"]:
        log_error("Invalid entity type.")
        return 1

    src_entity_name = name
    if ":" in plugin_name:
        plugin_name, src_entity_name = plugin_name.split(":")

    plugin_name = plugin_name.replace("-", "_")
    plugin_path = load_plugin(plugin_name, return_path_only=True)
    if not plugin_path:
        log_error(f"Could not find '{plugin_name}' installed.")
        return 1

    name_cases = get_formatted_names(name)

    item_name = name.replace("-", "_")
    item_name = f"{item_name}.yaml" if entity_type == "agents" else item_name

    src_entity_name = src_entity_name.replace("-", "_")
    src_entity_name = (
        f"{src_entity_name}.yaml" if entity_type == "agents" else src_entity_name
    )
    template_path = os.path.join(plugin_path, "configs", entity_type, src_entity_name)

    if not os.path.exists(template_path):
        log_error(f"Could not find '{src_entity_name}' in '{plugin_name}' plugin.")
        return 1

    config = click.get_current_context().obj
    config_directory = config["solace_agent_mesh"]["config_directory"]
    target_directory = os.path.join(config_directory, entity_type)
    os.makedirs(target_directory, exist_ok=True)

    def parse_file(content):
        content = (
            content.replace(" src.", f" {plugin_name}.src.")
            .replace("{{MODULE_DIRECTORY}}", f"{plugin_name}.src")
            .replace("src.src.", "src.")
        )
        for case, val in name_cases.items():
            content = content.replace(f"{{{{{case}}}}}", val)

        return content

    if entity_type == "agents":
        with open(template_path, "r", encoding="utf-8") as f:
            template_file = parse_file(f.read())
        target_path = os.path.join(target_directory, item_name)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(template_file)

    elif entity_type == "gateways":
        target_directory = os.path.join(target_directory, item_name)
        os.makedirs(target_directory, exist_ok=True)

        for file_item in os.listdir(template_path):
            source_path = os.path.join(template_path, file_item)
            if not os.path.isfile(source_path):
                continue
            with open(source_path, "r", encoding="utf-8") as f:
                template_file = parse_file(f.read())
            target_path = os.path.join(target_directory, file_item)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(template_file)

    else:
        log_error("Invalid entity type.")
        return 1

    temp_file = os.path.join(config_directory, ".gitkeep")
    if os.path.exists(temp_file):
        os.remove(temp_file)

    click.echo(
        f"Copied {entity_type[:-1]} '{name}' from plugin '{plugin_name}' at: {get_display_path(target_directory)}"
    )
