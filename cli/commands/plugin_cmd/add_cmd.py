import click
import pathlib
import toml

from cli.utils import get_formatted_names, error_exit
from .install_cmd import install_plugin


def ensure_directory_exists(path: pathlib.Path):
    """Creates a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)

def _get_plugin_type_from_pyproject(source_path: pathlib.Path) -> str | None:
    """Reads pyproject.toml from source_path and returns the plugin type."""
    pyproject_path = source_path / "pyproject.toml"
    if not pyproject_path.is_file():
        click.echo(
            click.style(
                f"Warning: pyproject.toml not found at {pyproject_path}. Cannot determine plugin type automatically.",
                fg="yellow",
            )
        )
        return None
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        project_name = data.get("project", {}).get("name", "").strip().replace("-", "_")
        plugin_type = (
            data.get("tool", {}).get(project_name, {}).get("metadata", {}).get("type")
        )
        if plugin_type:
            return plugin_type.strip()
        click.echo(
            click.style(
                f"Warning: Could not find plugin type for '{project_name}' in {pyproject_path}.",
                fg="yellow",
            )
        )
        return None
    except Exception as e:
        click.echo(click.style(f"Error parsing {pyproject_path}: {e}", fg="red"))
        return None



@click.command("add")
@click.argument("component_name")
@click.option(
    "--plugin",
    "plugin_source",
    required=True,
    help="Plugin source: installed module name, local path, or Git URL.",
)
@click.option(
    "--install-command",
    "installer_command",
    help="Command to use to install a python package. Must follow the format 'command {package} args', by default 'pip3 install {package}'. Can also be set through the environment variable SAM_PLUGIN_INSTALL_COMMAND.",
)
def add_plugin_component_cmd(
    component_name: str, plugin_source: str, installer_command: str | None = None
):
    """Installs the plugin and creates a new component instance from a specified plugin source."""

    click.echo(
        f"Attempting to add component '{component_name}' using plugin source '{plugin_source}'..."
    )

    module_name, plugin_path = install_plugin(plugin_source, installer_command)

    plugin_config_path = plugin_path / "config.yaml"
    plugin_pyproject_path = plugin_path / "pyproject.toml"

    if not plugin_pyproject_path.is_file():
        return error_exit(
            f"Error: pyproject.toml not found in plugin '{module_name}' at expected path {plugin_pyproject_path}"
        )

    if not plugin_config_path.is_file():
        return error_exit(
            f"Error: config.yaml not found in plugin '{module_name}' at expected path {plugin_config_path}"
        )
    try:
        plugin_config_content = plugin_config_path.read_text(encoding="utf-8")
    except Exception as e:
        return error_exit(
            f"Error reading plugin config.yaml from {plugin_config_path}: {e}"
        )

    component_formats = get_formatted_names(component_name)

    component_replacements = {
        "__COMPONENT_SNAKE_CASE_NAME__": component_formats["SNAKE_CASE_NAME"],
        "__COMPONENT_UPPER_SNAKE_CASE_NAME__": component_formats[
            "SNAKE_UPPER_CASE_NAME"
        ],
        "__COMPONENT_KEBAB_CASE_NAME__": component_formats["KEBAB_CASE_NAME"],
        "__COMPONENT_PASCAL_CASE_NAME__": component_formats["PASCAL_CASE_NAME"],
        "__COMPONENT_SPACED_NAME__": component_formats["SPACED_NAME"],
        "__COMPONENT_SPACED_CAPITALIZED_NAME__": component_formats[
            "SPACED_CAPITALIZED_NAME"
        ]
    }

    processed_config_content = plugin_config_content
    for placeholder, value in component_replacements.items():
        processed_config_content = processed_config_content.replace(placeholder, value)

    plugin_type = _get_plugin_type_from_pyproject(plugin_path)
    if plugin_type == "agent" or plugin_type == "tool":
        target_dir = pathlib.Path("configs/agents")
    elif plugin_type == "gateway":
        target_dir = pathlib.Path("configs/gateways")
    else:
        target_dir = pathlib.Path("configs/plugins")

    try:
        ensure_directory_exists(target_dir)
    except Exception as e:
        return error_exit(f"Error creating target directory {target_dir}: {e}")

    target_filename = f"{component_formats['KEBAB_CASE_NAME']}.yaml"
    target_path = target_dir / target_filename

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(processed_config_content)
        click.echo(f"  Created component configuration: {target_path}")
        click.echo(
            click.style(
                f"Component '{component_name}' created successfully from plugin '{module_name}'.",
                fg="green",
            )
        )
    except IOError as e:
        return error_exit(
            f"Error writing component configuration file {target_path}: {e}"
        )
