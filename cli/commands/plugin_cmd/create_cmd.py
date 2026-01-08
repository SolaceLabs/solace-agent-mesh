import click
import pathlib
from cli.utils import (
    get_formatted_names,
    ask_if_not_provided,
    load_template,
    error_exit,
)
from cli import __version__ as cli_version
from .official_registry import is_official_plugin

PLUGIN_TYPES = ["agent", "gateway", "tool", "custom"]

DEFAULT_PLUGIN_TYPE = "agent"
DEFAULT_AUTHOR_NAME = "Your Name"
DEFAULT_AUTHOR_EMAIL = "your.email@example.com"
DEFAULT_PLUGIN_VERSION = "0.1.0"


def ensure_directory_exists(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)


def replace_placeholders(content: str, replacements: dict) -> str:
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, str(value))
    return content


def load_plugin_type_config_template(plugin_type: str, replacement: dict) -> str:
    """Loads the template for the specified plugin type."""
    template_name = f"plugin_{plugin_type}_config_template.yaml"
    try:
        return load_template(template_name, replace_placeholders, replacement)
    except FileNotFoundError:
        error_exit(
            f"Template file '{template_name}' not found. Please ensure it exists in the templates directory."
        )
    except Exception as e:
        error_exit(f"Error loading template '{template_name}': {e}")


def setup_plugin_type_src(plugin_type: str, src_path: pathlib.Path, replacements: dict):
    """Sets up the source directory for the specified plugin type."""

    # --- Generate __init__.py ---
    src_init_py_content = ""
    try:
        with open(src_path / "__init__.py", "w", encoding="utf-8") as f:
            f.write(src_init_py_content)
        click.echo(f"  Created: {src_path / '__init__.py'}")
    except IOError as e:
        error_exit(f"Error writing {src_path / '__init__.py'}: {e}")

    if plugin_type == "agent" or plugin_type == "tool":
        # --- Generate tools.py ---
        try:
            src_tools_py_content = load_template(
                "plugin_tools_template.py", replace_placeholders, replacements
            )
            with open(src_path / "tools.py", "w", encoding="utf-8") as f:
                f.write(src_tools_py_content)
            click.echo(f"  Created: {src_path / 'tools.py'}")
        except FileNotFoundError:
            error_exit(
                "Template file 'plugin_tools_template.py' not found. Please ensure it exists in the templates directory."
            )
        except IOError as e:
            error_exit(f"Error writing {src_path / 'tools.py'}: {e}")

    elif plugin_type == "gateway":
        placeholders = {
            **replacements,
            "__GATEWAY_NAME_SNAKE_CASE__": replacements["__PLUGIN_SNAKE_CASE_NAME__"],
            "__GATEWAY_NAME_PASCAL_CASE__": replacements["__PLUGIN_PASCAL_CASE_NAME__"],
            "__GATEWAY_NAME_UPPER_CASE__": replacements[
                "__PLUGIN_UPPER_SNAKE_CASE_NAME__"
            ],
            "__GATEWAY_NAME_KEBAB_CASE__": replacements["__PLUGIN_KEBAB_CASE_NAME__"],
        }
        # --- Generate app.py ---
        try:
            src_gateway_py_content = load_template(
                "gateway_app_template.py", replace_placeholders, placeholders
            )
            with open(src_path / "app.py", "w", encoding="utf-8") as f:
                f.write(src_gateway_py_content)
            click.echo(f"  Created: {src_path / 'app.py'}")
        except FileNotFoundError:
            error_exit(
                "Template file 'gateway_app_template.py' not found. Please ensure it exists in the templates directory."
            )
        except IOError as e:
            error_exit(f"Error writing {src_path / 'app.py'}: {e}")
        # --- Generate gateway_component_template.py ---
        try:
            src_gateway_component_py_content = load_template(
                "gateway_component_template.py", replace_placeholders, placeholders
            )
            with open(src_path / "component.py", "w", encoding="utf-8") as f:
                f.write(src_gateway_component_py_content)
            click.echo(f"  Created: {src_path / 'component.py'}")
        except FileNotFoundError:
            error_exit(
                "Template file 'gateway_component_template.py' not found. Please ensure it exists in the templates directory."
            )
        except IOError as e:
            error_exit(f"Error writing {src_path / 'component.py'}: {e}")

    elif plugin_type == "custom":
        # --- generate app.py ---
        placeholders = {
            **replacements,
            "__COMPONENT_PASCAL_CASE_NAME__": replacements[
                "__PLUGIN_PASCAL_CASE_NAME__"
            ],
        }
        try:
            src_custom_py_content = load_template(
                "plugin_custom_template.py", replace_placeholders, placeholders
            )
            with open(src_path / "app.py", "w", encoding="utf-8") as f:
                f.write(src_custom_py_content)
            click.echo(f"  Created: {src_path / 'app.py'}")
        except FileNotFoundError:
            error_exit(
                "Template file 'plugin_custom_template.py' not found. Please ensure it exists in the templates directory."
            )
        except IOError as e:
            error_exit(f"Error writing {src_path / 'app.py'}: {e}")


@click.command("create")
@click.argument("plugin_name_arg")
@click.option("--type", "type_opt", help="Plugin type. Options: agent, gateway, tool, custom")
@click.option("--author-name", "author_name_opt", help="Author's name.")
@click.option("--author-email", "author_email_opt", help="Author's email.")
@click.option("--description", "description_opt", help="Plugin description.")
@click.option("--version", "version_opt", help="Initial plugin version.")
@click.option(
    "--skip",
    is_flag=True,
    help="Skip interactive prompts and use defaults or provided flags.",
)
def create_plugin_cmd(
    plugin_name_arg: str,
    type_opt: str,
    author_name_opt: str,
    author_email_opt: str,
    description_opt: str,
    version_opt: str,
    skip: bool,
):
    """Creates a new SAM plugin directory structure with interactive prompts for metadata."""

    options = {
        "plugin_name": plugin_name_arg,
        "type": type_opt,
        "author_name": author_name_opt,
        "author_email": author_email_opt,
        "description": description_opt,
        "version": version_opt,
    }

    plugin_formats = get_formatted_names(plugin_name_arg)
    default_description = f"A SAM plugin: {plugin_formats['SPACED_NAME']}"

    if is_official_plugin(plugin_formats["KEBAB_CASE_NAME"]) or is_official_plugin(
        plugin_formats["SNAKE_CASE_NAME"]
    ):
        error_exit(
            f"Error: Plugin name '{plugin_name_arg}' conflicts with an official plugin. "
            f"Please choose a different name."
        )

    if not skip:
        click.echo(
            "Please provide the following details for your new plugin (press Enter to accept defaults):"
        )

    options["type"] = ask_if_not_provided(
        options,
        "type",
        "Plugin Type",
        default=DEFAULT_PLUGIN_TYPE,
        choices=PLUGIN_TYPES,
        none_interactive=skip,
    ).lower()
    if options["type"] not in PLUGIN_TYPES:
        error_exit(
            f"Invalid plugin type '{options['type']}'. Must be one of: {', '.join(PLUGIN_TYPES)}."
        )

    options["author_name"] = ask_if_not_provided(
        options,
        "author_name",
        "Author's Name",
        default=DEFAULT_AUTHOR_NAME,
        none_interactive=skip,
    )
    options["author_email"] = ask_if_not_provided(
        options,
        "author_email",
        "Author's Email",
        default=DEFAULT_AUTHOR_EMAIL,
        none_interactive=skip,
    )
    options["description"] = ask_if_not_provided(
        options,
        "description",
        "Plugin Description",
        default=default_description,
        none_interactive=skip,
    )
    options["version"] = ask_if_not_provided(
        options,
        "version",
        "Initial plugin version",
        default=DEFAULT_PLUGIN_VERSION,
        none_interactive=skip,
    )

    click.echo(f"Creating plugin '{plugin_formats['KEBAB_CASE_NAME']}'...")

    base_plugin_path = pathlib.Path(plugin_formats["KEBAB_CASE_NAME"])
    src_path = base_plugin_path / "src" / plugin_formats["SNAKE_CASE_NAME"]

    try:
        ensure_directory_exists(base_plugin_path)
        ensure_directory_exists(src_path)
    except Exception as e:
        error_exit(f"Error creating plugin directories: {e}")

    replacements = {
        "__PLUGIN_KEBAB_CASE_NAME__": plugin_formats["KEBAB_CASE_NAME"],
        "__PLUGIN_SNAKE_CASE_NAME__": plugin_formats["SNAKE_CASE_NAME"],
        "__PLUGIN_UPPER_SNAKE_CASE_NAME__": plugin_formats["SNAKE_UPPER_CASE_NAME"],
        "__PLUGIN_SPACED_NAME__": plugin_formats["SPACED_NAME"],
        "__PLUGIN_PASCAL_CASE_NAME__": plugin_formats["PASCAL_CASE_NAME"],
        "__PLUGIN_AUTHOR_NAME__": options["author_name"],
        "__PLUGIN_AUTHOR_EMAIL__": options["author_email"],
        "__PLUGIN_DESCRIPTION__": options["description"],
        "__PLUGIN_VERSION__": options["version"],
        "__PLUGIN_META_DATA_TYPE__": options["type"].lower(),
        "__COMPONENT_KEBAB_CASE_NAME__": "__COMPONENT_KEBAB_CASE_NAME__",
        "__COMPONENT_PASCAL_CASE_NAME__": "__COMPONENT_PASCAL_CASE_NAME__",
        "__COMPONENT_UPPER_SNAKE_CASE_NAME__": "__COMPONENT_UPPER_SNAKE_CASE_NAME__",
        "__COMPONENT_SNAKE_CASE_NAME__": "__COMPONENT_SNAKE_CASE_NAME__",
    }

    # --- Generate config.yaml ---
    try:
        config_yaml_content = load_plugin_type_config_template(
            options["type"], replacements
        )
        with open(base_plugin_path / "config.yaml", "w", encoding="utf-8") as f:
            f.write(config_yaml_content)
        click.echo(f"  Created: {base_plugin_path / 'config.yaml'}")
    except IOError as e:
        error_exit(f"Error writing config.yaml: {e}")
    except Exception as e:
        error_exit(f"Error processing config.yaml template: {e}")

    # --- Generate pyproject.toml ---
    try:
        pyproject_toml_content = load_template(
            "plugin_pyproject_template.toml", replace_placeholders, replacements
        )
        with open(base_plugin_path / "pyproject.toml", "w", encoding="utf-8") as f:
            f.write(pyproject_toml_content)
        click.echo(f"  Created: {base_plugin_path / 'pyproject.toml'}")
    except FileNotFoundError:
        error_exit(
            "Template file 'plugin_pyproject_template.toml' not found. Please ensure it exists in the templates directory."
        )
    except IOError as e:
        error_exit(f"Error writing pyproject.toml: {e}")
    except Exception as e:
        error_exit(f"Error processing pyproject.toml template: {e}")

    # --- Generate src directory ---
    setup_plugin_type_src(options["type"], src_path, replacements)

    # --- Generate README.md ---
    try:
        readme_md_content = load_template(
            "plugin_readme_template.md", replace_placeholders, replacements
        )
        with open(base_plugin_path / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_md_content)
        click.echo(f"  Created: {base_plugin_path / 'README.md'}")
    except FileNotFoundError:
        error_exit(
            "Template file 'plugin_readme_template.md' not found. Please ensure it exists in the templates directory."
        )
    except IOError as e:
        error_exit(f"Error writing README.md: {e}")
    except Exception as e:
        error_exit(f"Error processing README.md template: {e}")

    click.echo(
        click.style(
            f"\nPlugin '{plugin_formats['KEBAB_CASE_NAME']}' created successfully at ./{base_plugin_path}",
            fg="green",
        )
    )
