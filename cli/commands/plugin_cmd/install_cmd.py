import tempfile
import os
import re
import subprocess
import pathlib
import click
import shutil
import toml

from cli.utils import get_module_path, error_exit
from .official_registry import get_official_plugin_url


def _check_command_exists(command: str) -> bool:
    """Checks if a command exists on the system."""
    return shutil.which(command) is not None

def _get_plugin_name_from_source_pyproject(source_path: pathlib.Path) -> str | None:
    """Reads pyproject.toml from source_path and returns the project name."""
    pyproject_path = source_path / "pyproject.toml"
    if not pyproject_path.is_file():
        click.echo(
            click.style(
                f"Warning: pyproject.toml not found at {pyproject_path}. Cannot determine module name automatically.",
                fg="yellow",
            )
        )
        return None
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        project_name = data.get("project", {}).get("name")
        if project_name:
            return project_name.strip().replace("-", "_")  # Normalize to snake_case
        click.echo(
            click.style(
                f"Warning: Could not find 'project.name' in {pyproject_path}.",
                fg="yellow",
            )
        )
        return None
    except Exception as e:
        click.echo(click.style(f"Error parsing {pyproject_path}: {e}", fg="red"))
        return None

def _run_install(
    install_command, install_target: str | pathlib.Path, operation_desc: str
) -> str | None:
    """Runs install for the given target."""
    click.echo(
        f"Attempting to install plugin using {install_command} from {operation_desc}..."
    )
    try:
        process = subprocess.run(
            install_command.format(package=str(install_target)).split(),
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode == 0:
            click.echo(
                click.style(
                    f"Plugin successfully installed via from {operation_desc}.",
                    fg="green",
                )
            )
            if process.stdout:
                click.echo(f"install output:\n{process.stdout}")
            return None
        else:
            return f"Error: 'install {install_target}' failed.\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}"
    except FileNotFoundError:
        return "Error: 'python' or command not found. Ensure Python and command are installed and in your PATH."
    except Exception as e:
        return f"An unexpected error occurred during install: {e}"

def install_plugin(plugin_source: str, installer_command: str | None = None) -> tuple[str | None, pathlib.Path | None]:
    """Installs a plugin from the specified source.

    Args:
        plugin_source: Source of the plugin (module name, local path, or Git URL)
        installer_command: Command to install the plugin, with '{package}' placeholder
    Returns:
        Tuple of (module_name, plugin_path) if successful, or (None, None) on failure
    """
    if not installer_command:
        installer_command = os.environ.get(
            "SAM_PLUGIN_INSTALL_COMMAND", "pip3 install {package}"
        )
    try:
        installer_command.format(package="dummy")  # Test if the command is valid
    except (KeyError, ValueError):
        return error_exit(
            "Error: The installer command must contain a placeholder '{package}' to be replaced with the actual package name."
        )

    official_plugin_url = get_official_plugin_url(plugin_source)
    if official_plugin_url:
        click.echo(f"Found official plugin '{plugin_source}' at: {official_plugin_url}")
        plugin_source = official_plugin_url

    install_type = None  # "module", "local", "git"
    module_name = None
    install_target = None
    source_path_for_name_extraction = None

    if plugin_source.startswith(("http://", "https://")) and plugin_source.endswith(
        ".git"
    ):
        install_type = "repository"
        install_target = plugin_source
    elif plugin_source.startswith(("git+")):
        install_type = "git"
        install_target = plugin_source
    elif os.path.exists(plugin_source):
        local_path = pathlib.Path(plugin_source).resolve()
        if local_path.is_dir():
            install_type = "local"
            install_target = str(local_path)
            source_path_for_name_extraction = local_path
        elif local_path.is_file() and local_path.suffix in [".whl", ".tar.gz"]:
            install_type = "wheel"
            install_target = str(local_path)
        else:
            return error_exit(
                f"Error: Local path '{plugin_source}' exists but is not a directory or wheel."
            )
    elif not re.search(r"[/\\]", plugin_source):
        install_type = "module"
        module_name = plugin_source.strip().replace("-", "_")
    else:
        return error_exit(
            f"Error: Invalid plugin source '{plugin_source}'. Not a recognized module name, local path, or Git URL."
        )

    if install_type in ["local", "git", "repository", "wheel"]:
        if install_type == "repository":
            if not _check_command_exists("git"):
                return error_exit(
                    "Error: 'git' command not found. Please install Git or install the plugin manually."
                )

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = pathlib.Path(temp_dir)
                cloned_repo_path = temp_dir_path / "plugin_repo"
                click.echo(
                    f"Cloning Git repository '{plugin_source}' to temporary directory {cloned_repo_path}..."
                )
                try:
                    subprocess.run(
                        ["git", "clone", plugin_source, str(cloned_repo_path)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    source_path_for_name_extraction = cloned_repo_path
                except subprocess.CalledProcessError as e:
                    return error_exit(f"Error cloning Git repository: {e.stderr}")
                except FileNotFoundError:
                    return error_exit("Error: 'git' command not found during clone.")

                module_name_from_pyproject = _get_plugin_name_from_source_pyproject(
                    source_path_for_name_extraction
                )
                if not module_name_from_pyproject:
                    return error_exit(
                        "Could not determine module name from pyproject.toml in the Git repo. Aborting."
                    )

                err = _run_install(
                    installer_command, install_target, f"Git URL ({plugin_source})"
                )
                if err:
                    return error_exit(err)
                module_name = module_name_from_pyproject

        elif install_type == "git":
            module_name_from_url = (
                plugin_source.split("#")[0]
                .split("?")[0]
                .split("/")[-1]
                .replace(".git", "")
                .replace("-", "_")
            )
            if "#subdirectory=" in plugin_source:
                module_name_from_url = (
                    plugin_source.split("#subdirectory=")[-1]
                    .split("?")[0]
                    .replace(".git", "")
                    .replace("-", "_")
                )

            if not module_name_from_url:
                return error_exit(
                    f"Could not determine module name from the Git URL {plugin_source}. Aborting."
                )

            err = _run_install(
                installer_command, install_target, f"Git URL ({plugin_source})"
            )
            if err:
                return error_exit(err)
            module_name = module_name_from_url

        elif install_type == "local":
            module_name_from_pyproject = _get_plugin_name_from_source_pyproject(
                source_path_for_name_extraction
            )
            if not module_name_from_pyproject:
                return error_exit(
                    f"Could not determine module name from pyproject.toml at {source_path_for_name_extraction}. Aborting."
                )

            err = _run_install(
                installer_command, install_target, f"local path ({install_target})"
            )
            if err:
                return error_exit(err)
            module_name = module_name_from_pyproject

        elif install_type == "wheel":
            module_name_from_wheel = (
                pathlib.Path(install_target).stem.split("-")[0]
            )
            if not module_name_from_wheel:
                return error_exit(
                    f"Could not determine module name from the wheel file {install_target}. Aborting."
                )

            err = _run_install(
                installer_command, install_target, f"wheel file ({install_target})"
            )
            if err:
                return error_exit(err)
            module_name = module_name_from_wheel

    if not module_name:
        return error_exit("Error: Could not determine the plugin module name to load.")

    click.echo(f"Proceeding to load plugin module '{module_name}'...")
    try:
        plugin_path = pathlib.Path(get_module_path(module_name))
    except ImportError:
        return error_exit(
            f"Error: Plugin module '{module_name}' not found after potential installation. Please check installation logs or install manually."
        )
    
    if not plugin_path or not plugin_path.exists():
        return error_exit(
            f"Error: Could not determine a valid root path for plugin module '{module_name}'. Path: {plugin_path}"
        )
    
    return module_name, plugin_path


@click.command("install")
@click.argument("plugin_source")
@click.option(
    "--install-command",
    "installer_command",
    help="Command to use to install a python package. Must follow the format 'command {package} args', by default 'pip3 install {package}'. Can also be set through the environment variable SAM_PLUGIN_INSTALL_COMMAND.",
)
def install_plugin_cmd(
    plugin_source: str,
    installer_command: str | None = None
):
    """
    Installs a plugin from the specified source.
    
    PLUGIN_SOURCE can be: \n
      - A local path to a directory (e.g., '/path/to/plugin') \n
      - A local path to a wheel file (e.g., '/path/to/plugin.whl') \n
      - A Git URL (e.g., 'https://github.com/user/repo.git') \n
      - The name of the plugin from https://github.com/SolaceLabs/solace-agent-mesh-core-plugins \n
    """
    module_name, plugin_path = install_plugin(plugin_source, installer_command)
    if module_name and plugin_path:
        click.echo(
            click.style(
                f"Plugin '{module_name}' installed and available at {plugin_path}.",
                fg="green",
            )
        )
