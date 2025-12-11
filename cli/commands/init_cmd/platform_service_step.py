import click
from pathlib import Path

from ...utils import ask_if_not_provided, load_template


PLATFORM_SERVICE_DEFAULTS = {
    "platform_api_host": "127.0.0.1",
    "platform_api_port": 8001,
    "platform_database_url": "sqlite:///platform.db",
    "external_auth_service_url": "",
    "external_auth_provider": "",
    "use_authorization": False,
}


def create_platform_service_config(
    project_root: Path, options: dict, skip_interactive: bool, default_values: dict
) -> bool:
    """
    Gathers Platform Service options and creates the configuration file (configs/services/platform_service.yaml)
    if the user opts in. It customizes the template based on user input or defaults.
    Returns True on success or if skipped, False on failure.
    """
    click.echo("Configuring Platform Service options...")

    add_platform_service = options.get("add_platform_service")
    if not skip_interactive and add_platform_service is None:
        add_platform_service = ask_if_not_provided(
            options,
            "add_platform_service",
            "Add Platform Service configuration? (Recommended for enterprise features)",
            default=default_values.get("add_platform_service", True),
            none_interactive=skip_interactive,
            is_bool=True,
        )
    elif add_platform_service is None:
        add_platform_service = default_values.get("add_platform_service", True)

    options["add_platform_service"] = add_platform_service

    if not add_platform_service:
        click.echo(
            click.style("  Skipping Platform Service file creation.", fg="yellow")
        )
        return True

    options["platform_api_host"] = ask_if_not_provided(
        options,
        "platform_api_host",
        "Enter Platform API Host",
        default=default_values.get(
            "platform_api_host", PLATFORM_SERVICE_DEFAULTS["platform_api_host"]
        ),
        none_interactive=skip_interactive,
    )
    options["platform_api_port"] = ask_if_not_provided(
        options,
        "platform_api_port",
        "Enter Platform API Port",
        default=default_values.get(
            "platform_api_port", PLATFORM_SERVICE_DEFAULTS["platform_api_port"]
        ),
        none_interactive=skip_interactive,
    )
    options["platform_database_url"] = ask_if_not_provided(
        options,
        "platform_database_url",
        "Enter Platform Database URL",
        default=default_values.get(
            "platform_database_url", PLATFORM_SERVICE_DEFAULTS["platform_database_url"]
        ),
        none_interactive=skip_interactive,
    )

    # Validate database URL (basic check)
    # if not platform_database_url or not isinstance(platform_database_url, str):
    #     click.echo(
    #         click.style(
    #             "  Warning: Invalid database URL. Using default SQLite database.",
    #             fg="yellow",
    #         )
    #     )
    #     platform_database_url = PLATFORM_SERVICE_DEFAULTS["platform_database_url"]
    # elif not platform_database_url.strip():
    #     click.echo(
    #         click.style(
    #             "  Warning: Empty database URL. Using default SQLite database.",
    #             fg="yellow",
    #         )
    #     )
    #     platform_database_url = PLATFORM_SERVICE_DEFAULTS["platform_database_url"]

    # options["platform_database_url"] = platform_database_url

    options["external_auth_service_url"] = ask_if_not_provided(
        options,
        "external_auth_service_url",
        "Enter External Auth Service URL (leave empty to disable OAuth2)",
        default=default_values.get(
            "external_auth_service_url",
            PLATFORM_SERVICE_DEFAULTS["external_auth_service_url"],
        ),
        none_interactive=skip_interactive,
    )
    options["external_auth_provider"] = ask_if_not_provided(
        options,
        "external_auth_provider",
        "Enter External Auth Provider (generic, azure, okta)",
        default=default_values.get(
            "external_auth_provider",
            PLATFORM_SERVICE_DEFAULTS["external_auth_provider"],
        ),
        none_interactive=skip_interactive,
    )
    options["use_authorization"] = ask_if_not_provided(
        options,
        "use_authorization",
        "Enable Authorization? (true/false)",
        default=default_values.get(
            "use_authorization", PLATFORM_SERVICE_DEFAULTS["use_authorization"]
        ),
        none_interactive=skip_interactive,
        is_bool=True,
    )

    click.echo("Creating Platform Service configuration file...")
    destination_path = project_root / "configs" / "services" / "platform_service.yaml"

    try:
        template_content = load_template("platform_service.yaml")

        # No placeholder replacements needed - template uses env vars directly
        modified_content = template_content

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with open(destination_path, "w", encoding="utf-8") as f:
            f.write(modified_content)

        click.echo(f"  Created: {destination_path.relative_to(project_root)}")
        return True

    except FileNotFoundError:
        click.echo(click.style("Error: Template file not found.", fg="red"), err=True)
        return False
    except IOError as e:
        click.echo(
            click.style(f"Error writing file {destination_path}: {e}", fg="red"),
            err=True,
        )
        return False
    except Exception as e:
        click.echo(
            click.style(
                f"An unexpected error occurred during Platform Service configuration: {e}",
                fg="red",
            ),
            err=True,
        )
        return False
