import click
import subprocess
import os
from pathlib import Path
from cli.utils import error_exit


@click.command("build")
@click.argument(
    "plugin_path_arg",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    default=".",
    metavar="PLUGIN_PATH",
)
def build_plugin_cmd(plugin_path_arg: str):
    """
    Builds the SAM plugin in the specified directory (defaults to current directory).
    This command requires the 'build' package to be installed (pip install build).
    """
    target_path = Path(plugin_path_arg)
    pyproject_file = target_path / "pyproject.toml"

    if not pyproject_file.is_file():
        click.echo(
            click.style(f"Error: pyproject.toml not found in {target_path}", fg="red")
        )
        click.echo(
            click.style(
                "Please ensure you are in the root directory of the plugin or provide the correct path.",
                fg="yellow",
            )
        )
        error_exit()

    click.echo(f"Building plugin in {target_path}...")
    click.echo(
        click.style(
            "Note: This command uses 'python -m build'. Ensure 'build' package is installed ('pip install build').",
            fg="cyan",
        )
    )

    original_cwd = Path.cwd()
    error_exit_msg = None
    try:
        os.chdir(target_path)
        process = subprocess.run(
            ["python", "-m", "build"], capture_output=True, text=True, check=False
        )

        if process.stdout:
            click.echo("--- Build Output ---")
            click.echo(process.stdout)
            click.echo("--- End of Build Output ---")

        if process.stderr:
            click.echo(click.style("--- Build Errors/Warnings ---", fg="yellow"))
            click.echo(click.style(process.stderr, fg="yellow"))
            click.echo(click.style("--- End of Build Errors/Warnings ---", fg="yellow"))

        if process.returncode == 0:
            dist_path = target_path / "dist"
            click.echo(
                click.style(
                    f"Plugin built successfully! Artifacts are in: {dist_path}",
                    fg="green",
                )
            )
            if dist_path.exists() and dist_path.is_dir():
                click.echo("Generated files:")
                for item in sorted(dist_path.iterdir()):
                    click.echo(f"  - {item.name}")
        else:
            error_exit_msg = (
                f"Error: 'python -m build' failed with exit code {process.returncode}."
            )
            error_exit_msg += "\nPlease check the build output above for details."

    except FileNotFoundError:
        error_exit_msg = f"Error: Python executable not found. Ensure Python is installed and in your PATH."
    except Exception as e:
        error_exit_msg = f"An unexpected error occurred during the build process: {e}"
    finally:
        os.chdir(original_cwd)
        if error_exit_msg:
            error_exit(error_exit_msg)
