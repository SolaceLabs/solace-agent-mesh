import os
import sys
from pathlib import Path

import click
from dotenv import find_dotenv, load_dotenv

from cli.utils import error_exit
from solace_agent_mesh.common.utils.initializer import initialize


def _execute_with_solace_ai_connector(config_file_paths: list[str]):
    try:
        from solace_ai_connector.main import main as solace_ai_connector_main
    except ImportError:
        error_exit(
            "Error: Failed to import 'solace_ai_connector.main'.\n"
            "Please ensure 'solace-agent-mesh' (which includes the connector) is installed correctly."
        )

    program_name = sys.argv[0]
    if os.path.basename(program_name) == "sam":
        connector_program_name = program_name.replace("sam", "solace-ai-connector")
    elif os.path.basename(program_name) == "solace-agent-mesh":
        connector_program_name = program_name.replace(
            "solace-agent-mesh", "solace-ai-connector"
        )
    else:
        connector_program_name = "solace-ai-connector"

    sys.argv = [connector_program_name] + config_file_paths

    sys.argv = [
        sys.argv[0].replace("solace-agent-mesh", "solace-ai-connector"),
        *config_file_paths,
    ]
    return sys.exit(solace_ai_connector_main())


@click.command(name="run")
@click.argument(
    "files", nargs=-1, type=click.Path(exists=True, dir_okay=True, resolve_path=True)
)
@click.option(
    "-s",
    "--skip",
    "skip_files",
    multiple=True,
    help="File name(s) to exclude from the run (e.g., -s my_agent.yaml).",
)
@click.option(
    "-u",
    "--system-env",
    is_flag=True,
    default=False,
    help="Use system environment variables only; do not load .env file.",
)
def run(files: tuple[str, ...], skip_files: tuple[str, ...], system_env: bool):
    """
    Run the Solace application with specified or discovered YAML configuration files.

    This command accepts paths to individual YAML files (`.yaml`, `.yml`) or directories.
    When a directory is provided, it is recursively searched for YAML files.
    """
    click.echo(click.style("Starting Solace Application Run...", bold=True, fg="blue"))

    if not system_env:
        env_path = find_dotenv(usecwd=True)
        if env_path:
            click.echo(f"Loading environment variables from: {env_path}")
            load_dotenv(dotenv_path=env_path, override=True)

            # Resolve LOGGING_CONFIG_PATH to absolute path if it's relative
            logging_config_path = os.getenv("LOGGING_CONFIG_PATH")
            if logging_config_path and not os.path.isabs(logging_config_path):
                absolute_logging_path = os.path.abspath(logging_config_path)
                os.environ["LOGGING_CONFIG_PATH"] = absolute_logging_path

            # Reconfigure logging now that environment variables are loaded
            try:
                from solace_ai_connector.common.log import reconfigure_logging
                if reconfigure_logging():
                    click.echo("Logging reconfigured from LOGGING_CONFIG_PATH")
            except ImportError:
                pass  # solace_ai_connector might not be available yet
        else:
            click.echo(
                click.style(
                    "Warning: .env file not found in the current directory or parent directories. Proceeding without loading .env.",
                    fg="yellow",
                )
            )
    else:
        click.echo("Skipping .env file loading due to --system-env flag.")

    # Run enterprise initialization if present
    initialize()

    config_files_to_run = []
    project_root = Path.cwd()
    configs_dir = project_root / "configs"

    if not files:
        click.echo(
            f"No specific files provided. Discovering YAML files in {configs_dir}..."
        )
        if not configs_dir.is_dir():
            click.echo(
                click.style(
                    f"Error: Configuration directory '{configs_dir}' not found. Please run 'init' first or provide specific config files.",
                    fg="red",
                ),
                err=True,
            )
            sys.exit(1)

        for filepath in configs_dir.rglob("*.yaml"):
            if filepath.name.startswith("_") or filepath.name.startswith(
                "shared_config"
            ):
                click.echo(
                    f"  Skipping discovery: {filepath} (underscore prefix or shared_config)"
                )
                continue
            config_files_to_run.append(str(filepath.resolve()))

        for filepath in configs_dir.rglob("*.yml"):
            if filepath.name.startswith("_") or filepath.name.startswith(
                "shared_config"
            ):
                click.echo(
                    f"  Skipping discovery: {filepath} (underscore prefix or shared_config)"
                )
                continue
            if str(filepath.resolve()) not in config_files_to_run:
                config_files_to_run.append(str(filepath.resolve()))

    else:
        click.echo("Processing provided configuration files and directories:")
        processed_files = set()
        for path_str in files:
            path = Path(path_str)
            if path.is_dir():
                click.echo(f"  Discovering YAML files in directory: {path}")
                for yaml_ext in ("*.yaml", "*.yml"):
                    for filepath in path.rglob(yaml_ext):
                        if filepath.name.startswith("_") or filepath.name.startswith(
                            "shared_config"
                        ):
                            click.echo(
                                f"  Skipping discovery: {filepath} (underscore prefix or shared_config)"
                            )
                            continue
                        processed_files.add(str(filepath.resolve()))
            elif path.is_file():
                if path.suffix in [".yaml", ".yml"]:
                    processed_files.add(str(path.resolve()))
                else:
                    click.echo(
                        click.style(f"  Ignoring non-YAML file: {path}", fg="yellow")
                    )
        config_files_to_run = sorted(list(processed_files))

    if skip_files:
        click.echo(f"Applying --skip for: {skip_files}")
        final_list = []
        skipped_basenames = [os.path.basename(s) for s in skip_files]
        for cf in config_files_to_run:
            if os.path.basename(cf) in skipped_basenames:
                click.echo(
                    f"  Skipping execution: {cf} (due to --skip)"
                )
                continue
            final_list.append(cf)
        config_files_to_run = final_list

    if not config_files_to_run:
        click.echo(
            click.style(
                "No configuration files to run after filtering. Exiting.", fg="yellow"
            )
        )
        return 0

    click.echo(click.style("Final list of configuration files to run:", bold=True))
    for cf_path_str in config_files_to_run:
            click.echo(f"  - {cf_path_str}")

    return_code = _execute_with_solace_ai_connector(config_files_to_run)

    if return_code == 0:
        click.echo(click.style("Application run completed successfully.", fg="green"))
    else:
        click.echo(
            click.style(
                f"Application run failed or exited with code {return_code}.", fg="red"
            )
        )

    sys.exit(return_code)
