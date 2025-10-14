from pathlib import Path

import click

from ...utils import ask_yes_no_question
from .broker_step import broker_setup_step
from .directory_step import create_project_directories
from .env_step import ENV_DEFAULTS, create_env_file
from .orchestrator_step import ORCHESTRATOR_DEFAULTS as O_DEFAULTS
from .orchestrator_step import create_orchestrator_config
from .project_files_step import create_project_files
from .web_init_step import perform_web_init
from .webui_gateway_step import WEBUI_GATEWAY_DEFAULTS, create_webui_gateway_config


def _get_flat_orchestrator_defaults():
    """Flattens and maps ORCHESTRATOR_DEFAULTS for DEFAULT_INIT_VALUES."""
    flat_defaults = {}
    flat_defaults["agent_name"] = O_DEFAULTS["agent_name"]
    flat_defaults["supports_streaming"] = O_DEFAULTS["supports_streaming"]
    flat_defaults["session_service_type"] = "memory"
    flat_defaults["session_service_behavior"] = "PERSISTENT"
    flat_defaults["artifact_service_type"] = O_DEFAULTS["artifact_service"]["type"]
    flat_defaults["artifact_service_base_path"] = O_DEFAULTS["artifact_service"][
        "base_path"
    ]
    flat_defaults["artifact_service_scope"] = O_DEFAULTS["artifact_service"][
        "artifact_scope"
    ]
    flat_defaults["artifact_service_bucket_name"] = O_DEFAULTS["artifact_service"].get(
        "bucket_name", ""
    )
    flat_defaults["artifact_service_endpoint_url"] = O_DEFAULTS["artifact_service"].get(
        "endpoint_url", ""
    )
    flat_defaults["artifact_service_region"] = O_DEFAULTS["artifact_service"].get(
        "region", "us-east-1"
    )
    flat_defaults["artifact_handling_mode"] = O_DEFAULTS["artifact_handling_mode"]
    flat_defaults["enable_embed_resolution"] = O_DEFAULTS["enable_embed_resolution"]
    flat_defaults["enable_artifact_content_instruction"] = O_DEFAULTS[
        "enable_artifact_content_instruction"
    ]
    flat_defaults["agent_card_description"] = O_DEFAULTS["agent_card"]["description"]
    flat_defaults["agent_card_default_input_modes"] = ",".join(
        O_DEFAULTS["agent_card"]["defaultInputModes"]
    )
    flat_defaults["agent_card_default_output_modes"] = ",".join(
        O_DEFAULTS["agent_card"]["defaultOutputModes"]
    )
    flat_defaults["agent_discovery_enabled"] = O_DEFAULTS["agent_discovery"]["enabled"]
    flat_defaults["agent_card_publishing_interval"] = O_DEFAULTS[
        "agent_card_publishing"
    ]["interval_seconds"]
    flat_defaults["inter_agent_communication_allow_list"] = ",".join(
        O_DEFAULTS["inter_agent_communication"]["allow_list"]
    )
    flat_defaults["inter_agent_communication_deny_list"] = ",".join(
        O_DEFAULTS["inter_agent_communication"].get("deny_list", [])
    )
    flat_defaults["inter_agent_communication_timeout"] = O_DEFAULTS[
        "inter_agent_communication"
    ]["request_timeout_seconds"]
    return flat_defaults


DEFAULT_INIT_VALUES = {
    "broker_type": "1",
    "broker_url": "ws://localhost:8008",
    "broker_vpn": "default",
    "broker_username": "default",
    "broker_password": "default",
    "container_engine": "docker",
    "SOLACE_LOCAL_BROKER_URL": "ws://localhost:8008",
    "SOLACE_LOCAL_BROKER_VPN": "default",
    "SOLACE_LOCAL_BROKER_USERNAME": "default",
    "SOLACE_LOCAL_BROKER_PASSWORD": "default",
    "DEV_BROKER_URL": "ws://localhost:8008",
    "DEV_BROKER_VPN": "default",
    "DEV_BROKER_USERNAME": "default",
    "DEV_BROKER_PASSWORD": "default",
    "llm_endpoint_url": "YOUR_LLM_ENDPOINT_URL_HERE",
    "llm_api_key": "YOUR_LLM_API_KEY_HERE",
    "llm_planning_model_name": "YOUR_LLM_PLANNING_MODEL_NAME_HERE",
    "llm_general_model_name": "YOUR_LLM_GENERAL_MODEL_NAME_HERE",
    "namespace": "solace_app/",
    "dev_mode": "false",
    **_get_flat_orchestrator_defaults(),
    "add_webui_gateway": True,
    "webui_session_secret_key": ENV_DEFAULTS.get("SESSION_SECRET_KEY"),
    "webui_fastapi_host": ENV_DEFAULTS.get("FASTAPI_HOST"),
    "webui_fastapi_port": int(ENV_DEFAULTS.get("FASTAPI_PORT", "8000")),
    "webui_fastapi_https_port": int(ENV_DEFAULTS.get("FASTAPI_HTTPS_PORT", "8443")),
    "webui_ssl_keyfile": ENV_DEFAULTS.get("SSL_KEYFILE", ""),
    "webui_ssl_certfile": ENV_DEFAULTS.get("SSL_CERTFILE", ""),
    "webui_ssl_keyfile_password": ENV_DEFAULTS.get("SSL_KEYFILE_PASSWORD", ""),
    "webui_enable_embed_resolution": ENV_DEFAULTS.get(
        "ENABLE_EMBED_RESOLUTION", "true"
    ).lower()
    == "true",
    "webui_frontend_welcome_message": WEBUI_GATEWAY_DEFAULTS.get(
        "frontend_welcome_message", "How can I assist you today?"
    ),
    "webui_frontend_bot_name": WEBUI_GATEWAY_DEFAULTS.get(
        "frontend_bot_name", "Solace Agent Mesh"
    ),
    "webui_frontend_collect_feedback": WEBUI_GATEWAY_DEFAULTS.get(
        "frontend_collect_feedback", False
    ),
}


def run_init_flow(skip_interactive: bool, use_web_based_init_flag: bool, **cli_options):
    """
    Orchestrates the initialization of a new Solace application project
    by running a sequence of steps.
    """
    click.echo(
        click.style("Initializing Solace Application Project...", bold=True, fg="blue")
    )
    options = {k: v for k, v in cli_options.items() if v is not None}

    actual_use_web_init = use_web_based_init_flag
    if not skip_interactive and not use_web_based_init_flag:
        actual_use_web_init = ask_yes_no_question(
            "Would you like to configure your project through a web interface in your browser?",
            default=True,
        )

    project_root = Path.cwd()
    click.echo(f"Project will be initialized in: {project_root}")

    if actual_use_web_init:
        if skip_interactive:
            click.echo(
                click.style(
                    "Web-based init (--gui) is not compatible with --skip. Proceeding with CLI-based init using provided options or defaults.",
                    fg="yellow",
                )
            )
        else:
            options = perform_web_init(options)
            skip_interactive = True

    steps = [
        ("Broker Setup", broker_setup_step),
        (
            "Project Directory Setup",
            lambda opts, defs, skip: create_project_directories(project_root),
        ),
        (
            "Project Files Creation",
            lambda opts, defs, skip: create_project_files(project_root),
        ),
        (
            "Main Orchestrator Configuration",
            lambda opts, defs, skip: create_orchestrator_config(
                project_root, opts, skip
            ),
        ),
        (
            "Web UI Gateway Configuration",
            lambda opts, defs, skip: create_webui_gateway_config(
                project_root, opts, skip, defs
            ),
        ),
        (
            ".env File Creation",
            lambda opts, defs, skip: create_env_file(project_root, opts, skip),
        ),
    ]

    step_count = 0
    total_display_steps = len([s_name for s_name, _ in steps if s_name])

    for step_name, step_function in steps:
        if step_name:
            step_count += 1
            click.echo(
                click.style(
                    f"\n--- Step {step_count} of {total_display_steps}: {step_name} ---",
                    bold=True,
                    fg="blue",
                )
            )

        step_function(options, DEFAULT_INIT_VALUES, skip_interactive)

    click.echo(click.style("\nProject initialization complete!", fg="green", bold=True))
    click.echo(
        click.style(
            "Review the generated files, especially .env and configuration YAMLs.",
            fg="yellow",
        )
    )
    click.echo(
        click.style(
            "Next steps: Consider running 'solace-agent-mesh run' or 'sam run'.",
            fg="blue",
        )
    )


@click.command(name="init")
@click.option(
    "--skip",
    is_flag=True,
    default=False,
    help="Non-interactive mode. Skip all prompts and use default values where applicable.",
)
@click.option(
    "--gui",
    is_flag=True,
    default=False,
    help="Launch the browser-based initialization interface.",
)
@click.option("--llm-service-endpoint", type=str, help="LLM Service Endpoint URL.")
@click.option("--llm-service-api-key", type=str, help="LLM Service API Key.")
@click.option(
    "--llm-service-planning-model-name", type=str, help="LLM Planning Model Name."
)
@click.option(
    "--llm-service-general-model-name", type=str, help="LLM General Model Name."
)
@click.option("--namespace", type=str, help="Namespace for the project.")
@click.option(
    "--broker-type",
    type=click.Choice(
        ["1", "2", "3", "solace", "container", "dev_mode", "dev_broker", "dev"],
        case_sensitive=False,
    ),
    help="Broker type: 1/solace (existing), 2/container (new local), 3/dev (dev mode).",
)
@click.option("--broker-url", type=str, help="Solace broker URL endpoint.")
@click.option("--broker-vpn", type=str, help="Solace broker VPN name.")
@click.option("--broker-username", type=str, help="Solace broker username.")
@click.option("--broker-password", type=str, help="Solace broker password.")
@click.option(
    "--container-engine",
    type=click.Choice(["podman", "docker"], case_sensitive=False),
    help="Container engine for local broker.",
)
@click.option(
    "--dev-mode",
    "dev_mode_flag",
    is_flag=True,
    help="Shortcut to select dev mode for broker (equivalent to --broker-type 3/dev).",
)
@click.option("--agent-name", type=str, help="Agent name for the main orchestrator.")
@click.option(
    "--supports-streaming",
    is_flag=True,
    help="Enable streaming support for the agent.",
    default=None,
)
@click.option(
    "--session-service-type",
    type=click.Choice(["memory", "vertex_rag", "sql"]),
    help="Session service type.",
)
@click.option(
    "--session-service-behavior",
    type=click.Choice(["PERSISTENT", "RUN_BASED"]),
    help="Session service behavior.",
)
@click.option(
    "--artifact-service-type",
    type=click.Choice(["memory", "filesystem", "gcs", "s3"]),
    help="Artifact service type.",
)
@click.option(
    "--artifact-service-base-path",
    type=str,
    help="Artifact service base path (for filesystem type).",
)
@click.option(
    "--artifact-service-bucket-name",
    type=str,
    help="S3 bucket name (for s3 artifact service type).",
)
@click.option(
    "--artifact-service-endpoint-url",
    type=str,
    help="S3 endpoint URL (for s3 artifact service type, optional for AWS S3).",
)
@click.option(
    "--artifact-service-region",
    type=str,
    help="S3 region (for s3 artifact service type).",
)
@click.option(
    "--artifact-service-scope",
    type=click.Choice(["namespace", "app", "custom"]),
    help="Artifact service scope.",
)
@click.option(
    "--artifact-handling-mode",
    type=click.Choice(["ignore", "embed", "reference"]),
    help="Artifact handling mode.",
)
@click.option(
    "--enable-embed-resolution",
    is_flag=True,
    help="Enable embed resolution.",
    default=None,
)
@click.option(
    "--enable-artifact-content-instruction",
    is_flag=True,
    help="Enable artifact content instruction.",
    default=None,
)
@click.option(
    "--enable-builtin-artifact-tools",
    is_flag=True,
    help="Enable built-in artifact tools.",
    default=None,
)
@click.option(
    "--enable-builtin-data-tools",
    is_flag=True,
    help="Enable built-in data tools.",
    default=None,
)
@click.option("--agent-card-description", type=str, help="Agent card description.")
@click.option(
    "--agent-card-default-input-modes",
    type=str,
    help="Agent card default input modes (comma-separated).",
)
@click.option(
    "--agent-card-default-output-modes",
    type=str,
    help="Agent card default output modes (comma-separated).",
)
@click.option(
    "--agent-discovery-enabled",
    is_flag=True,
    help="Enable agent discovery.",
    default=None,
)
@click.option(
    "--agent-card-publishing-interval",
    type=int,
    help="Agent card publishing interval (seconds).",
)
@click.option(
    "--inter-agent-communication-allow-list",
    type=str,
    help="Inter-agent communication allow list (comma-separated, use * for all).",
)
@click.option(
    "--inter-agent-communication-deny-list",
    type=str,
    help="Inter-agent communication deny list (comma-separated).",
)
@click.option(
    "--inter-agent-communication-timeout",
    type=int,
    help="Inter-agent communication timeout (seconds).",
)
@click.option(
    "--add-webui-gateway",
    is_flag=True,
    default=None,
    help="Add a default Web UI gateway configuration.",
)
@click.option(
    "--webui-session-secret-key", type=str, help="Session secret key for Web UI."
)
@click.option("--webui-fastapi-host", type=str, help="Host for Web UI FastAPI server.")
@click.option("--webui-fastapi-port", type=int, help="Port for Web UI FastAPI server.")
@click.option(
    "--webui-fastapi-https-port", type=int, help="HTTPS port for Web UI FastAPI server."
)
@click.option("--webui-ssl-keyfile", type=str, help="SSL key file path for Web UI.")
@click.option(
    "--webui-ssl-certfile", type=str, help="SSL certificate file path for Web UI."
)
@click.option(
    "--webui-ssl-keyfile-password", type=str, help="SSL key file passphrase for Web UI."
)
@click.option(
    "--webui-enable-embed-resolution",
    is_flag=True,
    default=None,
    help="Enable embed resolution for Web UI.",
)
@click.option(
    "--webui-frontend-welcome-message",
    type=str,
    help="Frontend welcome message for Web UI.",
)
@click.option(
    "--webui-frontend-bot-name", type=str, help="Frontend bot name for Web UI."
)
@click.option(
    "--webui-frontend-collect-feedback",
    is_flag=True,
    default=None,
    help="Enable feedback collection in Web UI.",
)
@click.option(
    "--web-ui-gateway-database-url",
    type=str,
    help="Database URL for the WebUI Gateway.",
)
@click.option(
    "--orchestrator-database-url",
    type=str,
    help="Database URL for the Orchestrator.",
)
def init(**kwargs):
    """
    Initialize a new Solace application project.
    Creates a directory structure, default configuration files, and a .env file.
    """
    use_web_based_init_val = kwargs.get("gui", False)

    if kwargs.get("dev_mode_flag"):
        if kwargs.get("broker_type") is None:
            kwargs["broker_type"] = "dev"
        elif kwargs.get("broker_type") not in ["3", "dev", "dev_mode", "dev_broker"]:
            click.echo(
                click.style(
                    f"Warning: --dev-mode flag is set, but --broker-type is also set to '{kwargs.get('broker_type')}'. Dev mode will be used for broker configuration.",
                    fg="yellow",
                )
            )
            kwargs["broker_type"] = "dev"

    skip_interactive_val = kwargs.pop("skip", False)
    use_web_based_init_val = kwargs.pop("gui", False)

    run_init_flow(
        skip_interactive=skip_interactive_val,
        use_web_based_init_flag=use_web_based_init_val,
        **kwargs,
    )
