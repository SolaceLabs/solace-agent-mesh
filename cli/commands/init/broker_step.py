import shutil
import click
import os

from cli.utils import ask_if_not_provided
from solace_agent_mesh.config_portal.backend.common import CONTAINER_RUN_COMMAND

def broker_step(options, default_options, none_interactive, abort):
    """
    Initialize the broker.
    """
    broker_type = ask_if_not_provided(
        options,
        "broker_type",
        (
            "Which broker type do you want to use?\n"
            "\t1) Existing Solace Pub/Sub+ broker\n"
            "\t2) New local Solace PubSub+ broker container (podman/docker)\n"
            "\t3) Run in 'dev mode' - all in one process (not recommended for production)\n"
            "Enter the number of your choice"
        ),
        "1",
        none_interactive,
        ["1", "2", "3"],
    )
    if broker_type == "2" or broker_type == "container":
        options["dev_mode"] = "false"
        # Check if the user have podman or docker installed
        has_podman = shutil.which("podman")
        has_docker = shutil.which("docker")
        if not has_podman and not has_docker:
            abort(
                "You need to have either podman or docker installed to use the container broker."
            )

        container_engine = "podman" if has_podman else "docker"
        if has_podman and has_docker:
            container_engine = ask_if_not_provided(
                options,
                "container_engine",
                "Which container engine do you want to use?",
                "podman",
                none_interactive,
                ["podman", "docker"],
            )

        # Run command for the container start
        command = container_engine + CONTAINER_RUN_COMMAND
        click.echo(
            f"Running the Solace PubSub+ broker container using {container_engine}"
        )
        response_status = os.system(command)
        if response_status != 0:
            abort("Failed to start the Solace PubSub+ broker container.")

        options["broker_url"] = default_options["broker_url"]
        options["broker_vpn"] = default_options["broker_vpn"]
        options["broker_username"] = default_options["broker_username"]
        options["broker_password"] = default_options["broker_password"]

    elif broker_type == "1" or broker_type == "solace":
        options["dev_mode"] = "false"
        ask_if_not_provided(
            options,
            "broker_url",
            "Enter the Solace broker url endpoint",
            default_options["broker_url"],
            none_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_vpn",
            "Enter the Solace broker vpn name",
            default_options["broker_vpn"],
            none_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_username",
            "Enter the Solace broker username",
            default_options["broker_username"],
            none_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_password",
            "Enter the Solace broker password",
            default_options["broker_password"],
            none_interactive,
            hide_input=True,
        )

    elif (
        broker_type == "3" or
        broker_type == "dev_broker" or
        broker_type == "dev_mode" or
        broker_type == "dev"
    ):
        options["dev_mode"] = "true"
