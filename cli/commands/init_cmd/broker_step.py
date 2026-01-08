import shutil
import click
import os
import sys

from config_portal.backend.common import (
    CONTAINER_RUN_COMMAND
)

from ...utils import ask_if_not_provided


def broker_setup_step(
    options: dict, default_values: dict, skip_interactive: bool
) -> dict:
    """
    Handles the broker setup during initialization.
    Updates the 'options' dictionary with broker configurations.
    """
    click.echo(click.style("Configuring Broker...", fg="blue"))

    broker_type_prompt = (
        "Which broker type do you want to use?\n"
        "  1) Existing Solace Pub/Sub+ broker\n"
        "  2) New local Solace PubSub+ broker container (requires Podman or Docker)\n"
        "  3) Run in 'dev mode' (all-in-one process, not for production)\n"
        "Enter the number of your choice"
    )

    broker_type = ask_if_not_provided(
        options,
        "broker_type",
        broker_type_prompt,
        default_values.get("broker_type", "1"),
        skip_interactive,
        ["1", "2", "3", "solace", "container", "dev_mode", "dev_broker", "dev"],
    )
    options["broker_type"] = broker_type

    if broker_type in ["2", "container"]:
        options["dev_mode"] = "false"
        has_podman = shutil.which("podman")
        has_docker = shutil.which("docker")
        if not has_podman and not has_docker:
            click.echo(
                click.style(
                    "Error: Podman or Docker is required to run a local Solace broker container.",
                    fg="red",
                ),
                err=True,
            )
            sys.exit(1)

        container_engine_default = "podman" if has_podman else "docker"
        container_engine = ask_if_not_provided(
            options,
            "container_engine",
            "Which container engine to use?",
            container_engine_default,
            skip_interactive,
            ["podman", "docker"],
        )
        options["container_engine"] = container_engine

        full_container_command = f"{container_engine}{CONTAINER_RUN_COMMAND}"
        click.echo(
            f"Attempting to run Solace PubSub+ broker container using {container_engine}:"
        )
        click.echo(f"  Command: {full_container_command}")

        if not skip_interactive:
            if not click.confirm(
                f"Execute this command to start the broker container?", default=True
            ):
                click.echo(
                    click.style(
                        "Broker container deployment skipped by user.", fg="yellow"
                    )
                )
                options["broker_url"] = ask_if_not_provided(
                    options,
                    "broker_url",
                    "Enter Solace broker URL endpoint",
                    default_values.get("broker_url"),
                    skip_interactive,
                )
                options["broker_vpn"] = ask_if_not_provided(
                    options,
                    "broker_vpn",
                    "Enter Solace broker VPN name",
                    default_values.get("broker_vpn"),
                    skip_interactive,
                )
                options["broker_username"] = ask_if_not_provided(
                    options,
                    "broker_username",
                    "Enter Solace broker username",
                    default_values.get("broker_username"),
                    skip_interactive,
                )
                options["broker_password"] = ask_if_not_provided(
                    options,
                    "broker_password",
                    "Enter Solace broker password",
                    default_values.get("broker_password"),
                    skip_interactive,
                    hide_input=True,
                )
                return options

        try:
            response_status = os.system(full_container_command)
            if response_status != 0:
                click.echo(
                    click.style(
                        f"Error: Failed to start Solace PubSub+ broker container (exit code: {response_status}). Check container logs.",
                        fg="red",
                    ),
                    err=True,
                )
                sys.exit(1)
            click.echo(
                click.style(
                    "Solace PubSub+ broker container started successfully (or already running).",
                    fg="green",
                )
            )
            options["broker_url"] = default_values.get(
                "SOLACE_LOCAL_BROKER_URL", "ws://localhost:8008"
            )
            options["broker_vpn"] = default_values.get(
                "SOLACE_LOCAL_BROKER_VPN", "default"
            )
            options["broker_username"] = default_values.get(
                "SOLACE_LOCAL_BROKER_USERNAME", "default"
            )
            options["broker_password"] = default_values.get(
                "SOLACE_LOCAL_BROKER_PASSWORD", "default"
            )
        except Exception as e:
            click.echo(
                click.style(
                    f"An error occurred while trying to run the container: {e}",
                    fg="red",
                ),
                err=True,
            )
            sys.exit(1)

    elif broker_type in ["1", "solace"]:
        options["dev_mode"] = "false"
        ask_if_not_provided(
            options,
            "broker_url",
            "Enter Solace broker URL endpoint",
            default_values.get("broker_url"),
            skip_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_vpn",
            "Enter Solace broker VPN name",
            default_values.get("broker_vpn"),
            skip_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_username",
            "Enter Solace broker username",
            default_values.get("broker_username"),
            skip_interactive,
        )
        ask_if_not_provided(
            options,
            "broker_password",
            "Enter Solace broker password",
            default_values.get("broker_password"),
            skip_interactive,
            hide_input=True,
        )

    elif broker_type in ["3", "dev_broker", "dev_mode", "dev"]:
        options["dev_mode"] = "true"
        click.echo(
            click.style(
                "Dev mode selected. Broker configurations will be minimal or handled by the application internally.",
                fg="yellow",
            )
        )
        options["broker_url"] = default_values.get(
            "DEV_BROKER_URL", "INTERNAL_DEV_BROKER"
        )
        options["broker_vpn"] = default_values.get("DEV_BROKER_VPN", "dev_vpn")
        options["broker_username"] = default_values.get(
            "DEV_BROKER_USERNAME", "dev_user"
        )
        options["broker_password"] = default_values.get(
            "DEV_BROKER_PASSWORD", "dev_pass"
        )

    return options
