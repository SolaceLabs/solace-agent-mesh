import click
from pathlib import Path

from ...utils import ask_if_not_provided, ask_yes_no_question, load_template


WEBUI_GATEWAY_DEFAULTS = {
    "webui_frontend_welcome_message": "",
    "webui_frontend_bot_name": "Solace Agent Mesh",
    "webui_frontend_logo_url": "",
    "webui_frontend_collect_feedback": False,
    "webui_session_secret_key": "please_change_me_in",
    "webui_fastapi_host": "127.0.0.1",
    "webui_fastapi_port": 8000,
    "webui_fastapi_https_port": 8443,
    "webui_ssl_keyfile": "",
    "webui_ssl_certfile": "",
    "webui_ssl_keyfile_password": "",
    "webui_enable_embed_resolution": True,
}


def create_webui_gateway_config(
    project_root: Path, options: dict, skip_interactive: bool, default_values: dict
) -> bool:
    """
    Gathers WebUI Gateway options and creates the configuration file (configs/gateways/webui.yaml)
    if the user opts in. It customizes the template based on user input or defaults.
    Returns True on success or if skipped, False on failure.
    """
    click.echo("Configuring Web UI Gateway options...")

    add_gateway = options.get("add_webui_gateway")
    if not skip_interactive and add_gateway is None:
        add_gateway = default_values.get("add_webui_gateway", True)
    elif add_gateway is None:
        add_gateway = default_values.get("add_webui_gateway", True)

    options["add_webui_gateway"] = add_gateway

    if not add_gateway:
        click.echo(click.style("  Skipping Web UI Gateway file creation.", fg="yellow"))
        return True

    options["webui_session_secret_key"] = ask_if_not_provided(
        options,
        "webui_session_secret_key",
        "Enter Web UI Session Secret Key",
        default=default_values.get(
            "webui_session_secret_key",
            WEBUI_GATEWAY_DEFAULTS["webui_session_secret_key"],
        ),
        none_interactive=skip_interactive,
        hide_input=True,
    )
    options["webui_fastapi_host"] = ask_if_not_provided(
        options,
        "webui_fastapi_host",
        "Enter Web UI FastAPI Host",
        default=default_values.get(
            "webui_fastapi_host", WEBUI_GATEWAY_DEFAULTS["webui_fastapi_host"]
        ),
        none_interactive=skip_interactive,
    )
    options["webui_fastapi_port"] = ask_if_not_provided(
        options,
        "webui_fastapi_port",
        "Enter Web UI FastAPI Port",
        default=default_values.get(
            "webui_fastapi_port", WEBUI_GATEWAY_DEFAULTS["webui_fastapi_port"]
        ),
        none_interactive=skip_interactive,
    )
    options["webui_fastapi_https_port"] = ask_if_not_provided(
        options,
        "webui_fastapi_https_port",
        "Enter Web UI FastAPI HTTPS Port",
        default=default_values.get("webui_fastapi_https_port", 8443),
        none_interactive=skip_interactive,
    )
    options["webui_enable_embed_resolution"] = ask_if_not_provided(
        options,
        "webui_enable_embed_resolution",
        "Enable Embed Resolution for Web UI? (true/false)",
        default=default_values.get(
            "webui_enable_embed_resolution",
            WEBUI_GATEWAY_DEFAULTS["webui_enable_embed_resolution"],
        ),
        none_interactive=skip_interactive,
        is_bool=True,
    )
    options["webui_ssl_keyfile"] = ask_if_not_provided(
        options,
        "webui_ssl_keyfile",
        "Enter SSL Key File Path",
        default=default_values.get("webui_ssl_keyfile", ""),
        none_interactive=skip_interactive,
    )
    options["webui_ssl_certfile"] = ask_if_not_provided(
        options,
        "webui_ssl_certfile",
        "Enter SSL Certificate File Path",
        default=default_values.get("webui_ssl_certfile", ""),
        none_interactive=skip_interactive,
    )
    options["webui_ssl_keyfile_password"] = ask_if_not_provided(
        options,
        "webui_ssl_keyfile_password",
        "Enter SSL Key File Passphrase",
        default=default_values.get("webui_ssl_keyfile_password", ""),
        none_interactive=skip_interactive,
        hide_input=True,
    )

    options["webui_frontend_welcome_message"] = ask_if_not_provided(
        options,
        "webui_frontend_welcome_message",
        "Enter Frontend Welcome Message for Web UI",
        default=default_values.get(
            "webui_frontend_welcome_message",
            WEBUI_GATEWAY_DEFAULTS["webui_frontend_welcome_message"],
        ),
        none_interactive=skip_interactive,
    )
    options["webui_frontend_bot_name"] = ask_if_not_provided(
        options,
        "webui_frontend_bot_name",
        "Enter Frontend Bot Name for Web UI",
        default=default_values.get(
            "webui_frontend_bot_name", WEBUI_GATEWAY_DEFAULTS["webui_frontend_bot_name"]
        ),
        none_interactive=skip_interactive,
    )
    options["webui_frontend_logo_url"] = ask_if_not_provided(
        options,
        "webui_frontend_logo_url",
        "Enter Frontend Logo URL (PNG, SVG, JPG or data URI)",
        default=default_values.get(
            "webui_frontend_logo_url", WEBUI_GATEWAY_DEFAULTS["webui_frontend_logo_url"]
        ),
        none_interactive=skip_interactive,
    )
    options["webui_frontend_collect_feedback"] = ask_if_not_provided(
        options,
        "webui_frontend_collect_feedback",
        "Enable Frontend Feedback Collection for Web UI? (true/false)",
        default=default_values.get(
            "webui_frontend_collect_feedback",
            WEBUI_GATEWAY_DEFAULTS["webui_frontend_collect_feedback"],
        ),
        none_interactive=skip_interactive,
        is_bool=True,
    )

    click.echo("Creating Web UI Gateway configuration file...")
    destination_path = project_root / "configs" / "gateways" / "webui.yaml"

    try:
        template_content = load_template("webui.yaml")
        
        session_service_lines = [
            f'type: "sql"',
            'database_url: "${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui_gateway.db}"',
            f'default_behavior: "PERSISTENT"',
        ]
        session_service_block = "\n" + "\n".join(
            [f"        {line}" for line in session_service_lines]
        )
        
        replacements = {
            "__FRONTEND_WELCOME_MESSAGE__": str(
                options.get("webui_frontend_welcome_message", '${FRONTEND_WELCOME_MESSAGE, "Hello, how can I assist you?"}')
            ),
            "__FRONTEND_BOT_NAME__": str(
                options.get("webui_frontend_bot_name", "${FRONTEND_BOT_NAME, Solace Agent Mesh}")
            ),
            "__FRONTEND_LOGO_URL__": str(
                options.get("webui_frontend_logo_url", "${WEBUI_FRONTEND_LOGO_URL}")
            ),
            "__FRONTEND_COLLECT_FEEDBACK__": str(
                options.get("webui_frontend_collect_feedback", "${FRONTEND_COLLECT_FEEDBACK, false}")
            ).lower(),
            "__SESSION_SERVICE__": session_service_block,
        }

        modified_content = template_content
        for placeholder, value in replacements.items():
            if value is not None:
                modified_content = modified_content.replace(placeholder, str(value))

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
                f"An unexpected error occurred during Web UI Gateway configuration: {e}",
                fg="red",
            ),
            err=True,
        )
        return False
