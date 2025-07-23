import click
import pathlib
import subprocess
import tempfile
import shutil
import os
import re
import toml

from cli.utils import get_formatted_names, get_module_path, error_exit
from .official_registry import get_official_plugin_url


def ensure_directory_exists(path: pathlib.Path):
    """Creates a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


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
    """Creates a new component instance from a specified plugin source."""

    click.echo(
        f"Attempting to add component '{component_name}' using plugin source '{plugin_source}'..."
    )
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
    module_name_to_load = None
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
        module_name_to_load = plugin_source.strip().replace("-", "_")
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
                module_name_to_load = module_name_from_pyproject

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
            module_name_to_load = module_name_from_url

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
            module_name_to_load = module_name_from_pyproject

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
            module_name_to_load = module_name_from_wheel

    if not module_name_to_load:
        return error_exit("Error: Could not determine the plugin module name to load.")

    click.echo(f"Proceeding to load plugin module '{module_name_to_load}'...")
    try:
        plugin_root_path = pathlib.Path(get_module_path(module_name_to_load))
    except ImportError:
        return error_exit(
            f"Error: Plugin module '{module_name_to_load}' not found after potential installation. Please check installation logs or install manually."
        )

    if not plugin_root_path or not plugin_root_path.exists():
        return error_exit(
            f"Error: Could not determine a valid root path for plugin module '{module_name_to_load}'. Path: {plugin_root_path}"
        )

    plugin_config_path = plugin_root_path / "config.yaml"
    plugin_pyproject_path = plugin_root_path / "pyproject.toml"

    if not plugin_pyproject_path.is_file():
        return error_exit(
            f"Error: pyproject.toml not found in plugin '{module_name_to_load}' at expected path {plugin_pyproject_path}"
        )

    if not plugin_config_path.is_file():
        return error_exit(
            f"Error: config.yaml not found in plugin '{module_name_to_load}' at expected path {plugin_config_path}"
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
        ],
    }

    processed_config_content = plugin_config_content
    for placeholder, value in component_replacements.items():
        processed_config_content = processed_config_content.replace(placeholder, value)

    plugin_type = _get_plugin_type_from_pyproject(plugin_root_path)
    if plugin_type == "agent":
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
                f"Component '{component_name}' created successfully from plugin '{module_name_to_load}'.",
                fg="green",
            )
        )
    except IOError as e:
        return error_exit(
            f"Error writing component configuration file {target_path}: {e}"
        )
