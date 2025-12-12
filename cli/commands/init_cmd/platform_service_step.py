import click
from pathlib import Path

from ...utils import ask_if_not_provided, load_template


PLATFORM_SERVICE_DEFAULTS = {
    "platform_api_host": "127.0.0.1",
    "platform_api_port": 8001,
}


def create_platform_service_config(
    project_root: Path, options: dict, skip_interactive: bool, default_values: dict
) -> bool:
    """
    Gathers Platform Service options and creates the configuration file (configs/services/platform.yaml).
    Platform Service is bundled with WebUI Gateway - only creates config if WebUI Gateway is enabled.
    Returns True on success or if skipped, False on failure.
    """
    # Platform Service is bundled with WebUI Gateway - skip if WebUI is disabled
    add_webui_gateway = options.get("add_webui_gateway", True)
    if not add_webui_gateway:
        click.echo(
            click.style(
                "  Skipping Platform Service (disabled with Web UI Gateway).", fg="yellow"
            )
        )
        return True

    click.echo("Configuring Platform Service options...")

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

    click.echo("Creating Platform Service configuration file...")
    destination_path = project_root / "configs" / "services" / "platform.yaml"

    try:
        template_content = load_template("platform.yaml")

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
