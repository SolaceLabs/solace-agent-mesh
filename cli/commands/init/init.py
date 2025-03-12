import click
import sys

from .check_if_already_done import check_if_already_done
from .ai_provider_step import ai_provider_step
from .broker_step import broker_step
from .builtin_agent_step import builtin_agent_step
from .create_config_file_step import create_config_file_step
from .file_service_step import file_service_step
from .project_structure_step import project_structure_step
from .create_other_project_files_step import create_other_project_files_step

from cli.utils import (
    log_error,
)

default_options = {
    "namespace": "",
    "config_dir": "configs",
    "module_dir": "modules",
    "env_file": ".env",
    "build_dir": "build",
    "broker_type": "container",
    "broker_url": "ws://localhost:8008",
    "broker_vpn": "default",
    "broker_username": "default",
    "broker_password": "default",
    "container_engine": "docker",
    "llm_model_name": "openai/gpt-4o",
    "llm_endpoint_url": "https://api.openai.com/v1",
    "llm_api_key": "",
    "embedding_model_name": "openai/text-embedding-ada-002",
    "embedding_endpoint_url": "https://api.openai.com/v1",
    "embedding_api_key": "",
    "built_in_agent": [],
    "file_service_provider": "volume",
    "file_service_config": ["volume=/tmp/solace-agent-mesh"],
    "env_var": [],
    "rest_api_enabled": True,
    "rest_api_server_input_port": "5050",
    "rest_api_server_host": "127.0.0.1",
    "rest_api_server_input_endpoint": "/api/v1/request",
    "rest_api_gateway_name": "rest-api",
    "webui_enabled": True,
    "webui_listen_port": "5001",
    "webui_host": "127.0.0.1"
}
"""
Default options for the init command.
"""


def abort(message: str):
    """Abort the init and cleanup"""
    log_error(f"Init failed: {message}.")
    # os.system(f"rm -rf {build_dir}")
    sys.exit(1)


def init_command(options={}):
    """
    Initialize the Solace Agent Mesh application.
    """
    click.echo(click.style("Initializing Solace Agent Mesh", bold=True, fg="blue"))
    skip = False
    if "skip" in options and options["skip"]:
        skip = True

    # no description for hidden steps
    steps = [
        ("", check_if_already_done),
        ("Project structure setup", project_structure_step),
        ("Broker setup", broker_step),
        ("AI provider setup", ai_provider_step),
        ("Builtin agent setup", builtin_agent_step),
        ("File service setup", file_service_step),
        ("", create_config_file_step),
        ("Setting up project", create_other_project_files_step),
    ]
    non_hidden_steps_count = len([step for step in steps if step[0]])

    step = 0
    try:
        for name, function in steps:
            if name:
                step += 1
                click.echo(
                    click.style(
                        f"Step {step} of {non_hidden_steps_count}: {name}", fg="blue"
                    )
                )
            function(options, default_options, skip, abort)
    except KeyboardInterrupt:
        abort("\n\nAborted by user")

    click.echo(click.style("Solace Agent Mesh has been initialized", fg="green"))

    if not skip:
        click.echo(
            click.style(
                "Review the `solace-agent-mesh` config file and make any necessary changes.",
                fg="yellow",
            )
        )
        click.echo(
            click.style(
                "To get started, use the `solace-agent-mesh add` command to add agents and gateways",
                fg="blue",
            )
        )
