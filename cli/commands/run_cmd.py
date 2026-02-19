import logging
import os
import sys
from pathlib import Path

import click
from dotenv import find_dotenv, load_dotenv

from cli.utils import error_exit, discover_config_files
from solace_agent_mesh.common.utils.initializer import initialize
from solace_ai_connector.common.logging_config import configure_from_file


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
    # Set up initial logging to root logger (will be overwritten by LOGGING_CONFIG_PATH if provided)
    log = None
    reset_logging = True

    def _setup_backup_logger():
        nonlocal log
        if not log:
            log = logging.getLogger()
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            log.addHandler(handler)
            log.setLevel(logging.INFO)
        return log
        
    env_path = ""

    if not system_env:
        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(dotenv_path=env_path, override=True)

            # Resolve LOGGING_CONFIG_PATH to absolute path if it's relative
            logging_config_path = os.getenv("LOGGING_CONFIG_PATH")
            if logging_config_path and not os.path.isabs(logging_config_path):
                absolute_logging_path = os.path.abspath(logging_config_path)
                os.environ["LOGGING_CONFIG_PATH"] = absolute_logging_path

    try:
        if configure_from_file():
            log = logging.getLogger(__name__)
            log.info("Logging reconfigured from LOGGING_CONFIG_PATH")
            reset_logging = False
        else:
            log = _setup_backup_logger()
    except ImportError:
        log = _setup_backup_logger()  # solace_ai_connector might not be available yet
        log.warning("Using backup logger; solace_ai_connector not available.")

    if system_env:
        log.warning("Skipping .env file loading due to --system-env flag.")
    else:
        if not env_path:
            log.warning("Warning: .env file not found in the current directory or parent directories. Proceeding without loading .env.")
        else:
            log.info("Loaded environment variables from: %s", env_path)

    # Run enterprise initialization if present
    initialize()

    try:
        config_files_to_run = discover_config_files(files, skip_files)
    except FileNotFoundError as e:
        log.error(str(e))
        sys.exit(1)

    if not config_files_to_run:
        log.warning(
            "No configuration files to run after filtering. Exiting."
        )
        return 0

    file_list = "\n".join(f"  - {cf}" for cf in config_files_to_run)
    log.info("Final list of configuration files to run:\n%s", file_list)

    if reset_logging:
        for handler in log.handlers[:]:
            log.removeHandler(handler)
    return_code = _execute_with_solace_ai_connector(config_files_to_run)

    if return_code == 0:
        log.info("Application run completed successfully.")
    else:
        log.error(
            "Application run failed or exited with code %s.", return_code
        )

    sys.exit(return_code)
