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
from .web_init_step import web_init_step

from cli.utils import (
    log_error,
    ask_yes_no_question,
)
from solace_agent_mesh.config_portal.backend.common import default_options


def abort(message: str):
    """Abort the init and cleanup"""
    log_error(f"Init failed: {message}.")
    # os.system(f"rm -rf {build_dir}")
    sys.exit(1)


def init_command(options={}):
    """
    Initialize the Solace Agent Mesh application.
    """
    skip = False
    if "skip" in options and options["skip"]:
        skip = True

    click.echo(click.style("Initializing Solace Agent Mesh", bold=True, fg="blue"))
    check_if_already_done(options, default_options, skip, abort)

    use_web_based_init = options.get("use_web_based_init", False)
    if not use_web_based_init and not skip:
        use_web_based_init = ask_yes_no_question("Would you like to configure your project through a web interface in your browser?", True)

    # no description for hidden steps
    cli_steps = [
        ("Project structure setup", project_structure_step),
        ("Broker setup", broker_step),
        ("AI provider setup", ai_provider_step),
        ("Builtin agent setup", builtin_agent_step),
        ("File service setup", file_service_step),
        ("", create_config_file_step),
        ("Setting up project", create_other_project_files_step),
    ]

    web_steps = [
        ("Initilize in web", web_init_step),
        ("", create_config_file_step),
        ("", create_other_project_files_step),
    ]

    steps = web_steps if use_web_based_init else cli_steps
         
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
