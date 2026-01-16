import sys
from pathlib import Path

import click

from ...utils import (
    get_formatted_names,
    load_template,
)


def _write_proxy_yaml(proxy_name_input: str, project_root: Path) -> tuple[bool, str, str]:
    """
    Writes the proxy YAML file based on proxy_template.yaml.
    
    Args:
        proxy_name_input: Name provided by user
        project_root: Project root directory
        
    Returns:
        Tuple of (success, message, relative_file_path)
    """
    agents_config_dir = project_root / "configs" / "agents"
    agents_config_dir.mkdir(parents=True, exist_ok=True)
    
    formatted_names = get_formatted_names(proxy_name_input)
    proxy_name_pascal = formatted_names["PASCAL_CASE_NAME"]
    file_name_snake = formatted_names["SNAKE_CASE_NAME"]
    
    proxy_config_file_path = agents_config_dir / f"{file_name_snake}_proxy.yaml"
    
    try:
        # Load template
        template_content = load_template("proxy_template.yaml")
        
        # Replace placeholder
        modified_content = template_content.replace("__PROXY_NAME__", proxy_name_pascal)
        
        # Write file
        with open(proxy_config_file_path, "w", encoding="utf-8") as f:
            f.write(modified_content)
        
        relative_file_path = str(proxy_config_file_path.relative_to(project_root))
        return (
            True,
            f"Proxy configuration created: {relative_file_path}",
            relative_file_path,
        )
    except FileNotFoundError as e:
        return (
            False,
            f"Error: Template file 'proxy_template.yaml' not found: {e}",
            "",
        )
    except Exception as e:
        import traceback
        click.echo(
            f"DEBUG: Error in _write_proxy_yaml: {e}\n{traceback.format_exc()}",
            err=True,
        )
        return (
            False,
            f"Error creating proxy configuration file {proxy_config_file_path}: {e}",
            "",
        )


@click.command(name="proxy")
@click.argument("name", required=False)
@click.option(
    "--skip",
    is_flag=True,
    help="Skip interactive prompts (creates proxy with default template).",
)
def add_proxy(name: str, skip: bool = False):
    """
    Creates a new A2A proxy configuration.

    NAME: Name of the proxy component to create (e.g., my-proxy).
    """
    if not name:
        click.echo(
            click.style(
                "Error: You must provide a proxy name.",
                fg="red",
            ),
            err=True,
        )
        return
    
    click.echo(f"Creating proxy configuration for '{name}'...")
    
    project_root = Path.cwd()
    success, message, _ = _write_proxy_yaml(name, project_root)
    
    if success:
        click.echo(click.style(message, fg="green"))
    else:
        click.echo(click.style(message, fg="red"), err=True)
        sys.exit(1)
