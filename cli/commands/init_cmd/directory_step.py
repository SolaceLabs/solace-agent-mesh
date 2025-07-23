import click
from pathlib import Path


def create_project_directories(project_root: Path) -> bool:
    """
    Creates the necessary directory structure for a new project.
    Returns True on success, False on failure.
    """
    dirs_to_create = [
        project_root / "configs",
        project_root / "configs" / "gateways",
        project_root / "configs" / "agents",
        project_root / "src",
    ]

    click.echo("Creating directory structure...")
    for dir_path in dirs_to_create:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            click.echo(f"  Created: {dir_path.relative_to(project_root)}")
        except OSError as e:
            click.echo(
                click.style(f"Error creating directory {dir_path}: {e}", fg="red"),
                err=True,
            )
            return False
    return True
