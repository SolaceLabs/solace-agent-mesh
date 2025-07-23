import click
from pathlib import Path
from cli import __version__ as cli_version


def create_project_files(project_root: Path) -> bool:
    """
    Creates standard project files like configurations, __init__.py, and requirements.txt.
    Returns True if all essential files are created, False otherwise.
    """
    click.echo("Creating project files...")
    all_successful = True

    src_init_path = project_root / "src" / "__init__.py"
    try:
        with open(src_init_path, "w", encoding="utf-8") as f:
            f.write("# Source directory\n")
        click.echo(f"  Created: {src_init_path.relative_to(project_root)}")
    except IOError as e:
        click.echo(
            click.style(f"Error creating file {src_init_path}: {e}", fg="red"), err=True
        )
        all_successful = False

    requirements_path = project_root / "requirements.txt"
    requirements_content = f"""solace-agent-mesh~={cli_version}\n"""
    try:
        with open(requirements_path, "w", encoding="utf-8") as f:
            f.write(requirements_content)
        click.echo(f"  Created: {requirements_path.relative_to(project_root)}")
    except IOError as e:
        click.echo(
            click.style(f"Error creating file {requirements_path}: {e}", fg="red"),
            err=True,
        )
        all_successful = False

    return all_successful
