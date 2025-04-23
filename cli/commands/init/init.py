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
from solace_agent_mesh.config_portal.backend.server import run_flask
import click
import multiprocessing
import sys
import time
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

    check_if_already_done(options, default_options, skip, abort)

    click.echo(click.style("Initializing Solace Agent Mesh", bold=True, fg="blue"))
    use_web_based_init = ask_yes_no_question("Would you like to configure your project through a web interface in your browser?", True)

    if use_web_based_init and not skip:

        with multiprocessing.Manager() as manager:
            # Create a shared configuration dictionary
            shared_config = manager.dict()
            
            # Start the Flask server with the shared config
            init_gui_process = multiprocessing.Process(
                target=run_flask,
                args=("127.0.0.1", 5002, shared_config)
            )
            init_gui_process.start()

            click.echo(click.style("Web configuration portal is running at http://127.0.0.1:5002", fg="green"))
            click.echo("Complete the configuration in your browser to continue...")

            # Wait for the Flask server to finish
            init_gui_process.join()
            
            # Get the configuration from the shared dictionary
            if shared_config:
                # Convert from manager.dict to regular dict
                config_from_portal = dict(shared_config)
                options.update(config_from_portal)
                click.echo(click.style("Configuration received from portal", fg="green"))

                #if web configuration portal is used, skip the steps that are already done
                steps_if_web_setup_used = [
                    ("", create_config_file_step),
                    ("", create_other_project_files_step),
                ]
                steps = steps_if_web_setup_used
            else:
                click.echo(click.style("Web configuration failed, please try again.", fg="red"))
                return
            

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
