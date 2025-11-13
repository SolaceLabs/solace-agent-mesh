import re
from pathlib import Path

import click
import yaml

from config_portal.backend.common import DEFAULT_COMMUNICATION_TIMEOUT

from ...utils import ask_if_not_provided, get_formatted_names, load_template

ORCHESTRATOR_DEFAULTS = {
    "agent_name": "OrchestratorAgent",
    "supports_streaming": True,
    "artifact_handling_mode": "reference",
    "enable_embed_resolution": True,
    "enable_artifact_content_instruction": True,
    "enable_builtin_artifact_tools": {"enabled": True},
    "enable_builtin_data_tools": {"enabled": True},
    "artifact_service": {
        "type": "filesystem",
        "base_path": "/tmp/samv2",
        "artifact_scope": "namespace",
        "bucket_name": "",
        "endpoint_url": "",
        "region": "us-east-1",
    },
    "agent_card": {
        "description": "The Orchestrator component. It manages tasks and coordinates multi-agent workflows.",
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text", "file"],
        "skills": [],
    },
    "agent_card_publishing": {"interval_seconds": 10},
    "agent_discovery": {"enabled": True},
    "inter_agent_communication": {
        "allow_list": ["*"],
        "request_timeout_seconds": DEFAULT_COMMUNICATION_TIMEOUT,
    },
    "use_orchestrator_db": True,
}


def create_orchestrator_config(
    project_root: Path, options: dict, skip_interactive: bool
) -> bool:
    """
    Creates the main_orchestrator.yaml file with configured values.
    Returns True on success, False on failure.
    """
    click.echo("Configuring main orchestrator...")

    raise_if_not_valid_agent_name = options.get("agent_name") or skip_interactive
    ask_if_not_provided(
        options,
        "agent_name",
        "Enter agent name",
        ORCHESTRATOR_DEFAULTS["agent_name"],
        skip_interactive,
    )

    agent_name = options.get("agent_name")
    while not re.match(r"^[a-zA-Z0-9_]+$", agent_name):
        if raise_if_not_valid_agent_name:
            raise click.UsageError(
                "Invalid agent name. Only letters, numbers, and underscores are allowed."
            )
        else:
            click.echo(
                click.style(
                    "Invalid agent name. Only letters, numbers, and underscores are allowed.",
                    fg="red",
                ),
                err=True,
            )
            agent_name = click.prompt("Please enter a valid agent name")
    options["agent_name"] = agent_name

    ask_if_not_provided(
        options,
        "supports_streaming",
        "Enable streaming support? (true/false)",
        ORCHESTRATOR_DEFAULTS["supports_streaming"],
        skip_interactive,
        is_bool=True,
    )

    options["use_orchestrator_db"] = ORCHESTRATOR_DEFAULTS["use_orchestrator_db"]

    artifact_type = ask_if_not_provided(
        options,
        "artifact_service_type",
        "Enter artifact service type",
        ORCHESTRATOR_DEFAULTS["artifact_service"]["type"],
        skip_interactive,
        choices=["memory", "filesystem", "gcs", "s3"],
    )

    artifact_base_path = None
    s3_bucket_name = None
    s3_endpoint_url = None
    s3_region = None

    if artifact_type == "filesystem":
        artifact_base_path = ask_if_not_provided(
            options,
            "artifact_service_base_path",
            "Enter artifact service base path",
            ORCHESTRATOR_DEFAULTS["artifact_service"]["base_path"],
            skip_interactive,
        )
    elif artifact_type == "s3":
        # Map CLI artifact-service-* parameters to s3_* keys
        if options.get("artifact_service_bucket_name"):
            options["s3_bucket_name"] = options["artifact_service_bucket_name"]
        if options.get("artifact_service_endpoint_url"):
            options["s3_endpoint_url"] = options["artifact_service_endpoint_url"]
        if options.get("artifact_service_region"):
            options["s3_region"] = options["artifact_service_region"]

        s3_bucket_name = ask_if_not_provided(
            options,
            "s3_bucket_name",
            "Enter S3 bucket name",
            ORCHESTRATOR_DEFAULTS["artifact_service"]["bucket_name"],
            skip_interactive,
        )
        s3_endpoint_url = ask_if_not_provided(
            options,
            "s3_endpoint_url",
            "Enter S3 endpoint URL (leave empty for AWS S3)",
            ORCHESTRATOR_DEFAULTS["artifact_service"]["endpoint_url"],
            skip_interactive,
        )
        s3_region = ask_if_not_provided(
            options,
            "s3_region",
            "Enter S3 region",
            ORCHESTRATOR_DEFAULTS["artifact_service"]["region"],
            skip_interactive,
        )

    artifact_scope = ask_if_not_provided(
        options,
        "artifact_service_scope",
        "Enter artifact service scope",
        ORCHESTRATOR_DEFAULTS["artifact_service"]["artifact_scope"],
        skip_interactive,
        choices=["namespace", "app", "custom"],
    )

    artifact_handling_mode = ask_if_not_provided(
        options,
        "artifact_handling_mode",
        "Enter artifact handling mode",
        ORCHESTRATOR_DEFAULTS["artifact_handling_mode"],
        skip_interactive,
        choices=["ignore", "embed", "reference"],
    )

    enable_embed_resolution = ask_if_not_provided(
        options,
        "enable_embed_resolution",
        "Enable embed resolution? (true/false)",
        ORCHESTRATOR_DEFAULTS["enable_embed_resolution"],
        skip_interactive,
        is_bool=True,
    )

    enable_artifact_content_instruction = ask_if_not_provided(
        options,
        "enable_artifact_content_instruction",
        "Enable artifact content instruction? (true/false)",
        ORCHESTRATOR_DEFAULTS["enable_artifact_content_instruction"],
        skip_interactive,
        is_bool=True,
    )

    agent_card_description = ask_if_not_provided(
        options,
        "agent_card_description",
        "Enter agent card description",
        ORCHESTRATOR_DEFAULTS["agent_card"]["description"],
        skip_interactive,
    )

    if "agent_card_default_input_modes" in options and isinstance(
        options["agent_card_default_input_modes"], list
    ):
        default_input_modes = options["agent_card_default_input_modes"]
    else:
        default_input_modes_str = ask_if_not_provided(
            options,
            "agent_card_default_input_modes",
            "Enter agent card default input modes (comma-separated)",
            ",".join(ORCHESTRATOR_DEFAULTS["agent_card"]["defaultInputModes"]),
            skip_interactive,
        )
        if isinstance(default_input_modes_str, list):
            default_input_modes = default_input_modes_str
        else:
            default_input_modes = [
                mode.strip() for mode in default_input_modes_str.split(",")
            ]

    if "agent_card_default_output_modes" in options and isinstance(
        options["agent_card_default_output_modes"], list
    ):
        default_output_modes = options["agent_card_default_output_modes"]
    else:
        default_output_modes_str = ask_if_not_provided(
            options,
            "agent_card_default_output_modes",
            "Enter agent card default output modes (comma-separated)",
            ",".join(ORCHESTRATOR_DEFAULTS["agent_card"]["defaultOutputModes"]),
            skip_interactive,
        )
        if isinstance(default_output_modes_str, list):
            default_output_modes = default_output_modes_str
        else:
            default_output_modes = [
                mode.strip() for mode in default_output_modes_str.split(",")
            ]

    agent_discovery_enabled = ask_if_not_provided(
        options,
        "agent_discovery_enabled",
        "Enable agent discovery? (true/false)",
        ORCHESTRATOR_DEFAULTS["agent_discovery"]["enabled"],
        skip_interactive,
        is_bool=True,
    )

    agent_card_publishing_interval = ask_if_not_provided(
        options,
        "agent_card_publishing_interval",
        "Enter agent card publishing interval (seconds)",
        ORCHESTRATOR_DEFAULTS["agent_card_publishing"]["interval_seconds"],
        skip_interactive,
    )

    if "inter_agent_communication_allow_list" in options and isinstance(
        options["inter_agent_communication_allow_list"], list
    ):
        allow_list = options["inter_agent_communication_allow_list"]
    else:
        allow_list_str = ask_if_not_provided(
            options,
            "inter_agent_communication_allow_list",
            "Enter inter-agent communication allow list (comma-separated, use * for all)",
            ",".join(ORCHESTRATOR_DEFAULTS["inter_agent_communication"]["allow_list"]),
            skip_interactive,
        )
        if isinstance(allow_list_str, list):
            allow_list = allow_list_str
        else:
            allow_list = [item.strip() for item in allow_list_str.split(",")]

    if "inter_agent_communication_deny_list" in options and isinstance(
        options["inter_agent_communication_deny_list"], list
    ):
        deny_list = options["inter_agent_communication_deny_list"]
    else:
        deny_list_str = ask_if_not_provided(
            options,
            "inter_agent_communication_deny_list",
            "Enter inter-agent communication deny list (comma-separated, leave empty for none)",
            "",
            skip_interactive,
        )
        if isinstance(deny_list_str, list):
            deny_list = deny_list_str
        else:
            deny_list = (
                [item.strip() for item in deny_list_str.split(",")]
                if deny_list_str.strip()
                else []
            )

    inter_agent_communication_timeout = ask_if_not_provided(
        options,
        "inter_agent_communication_timeout",
        "Enter inter-agent communication timeout (seconds)",
        ORCHESTRATOR_DEFAULTS["inter_agent_communication"]["request_timeout_seconds"],
        skip_interactive,
    )

    shared_config_dest_path = project_root / "configs" / "shared_config.yaml"

    try:
        shared_template_content = load_template("shared_config.yaml")

        artifact_base_path_line = ""
        if artifact_type == "filesystem":
            artifact_base_path_line = f'base_path: "{artifact_base_path}"'
        elif artifact_type == "s3":
            s3_config_lines = ["bucket_name: ${S3_BUCKET_NAME}"]
            s3_config_lines.append("endpoint_url: ${S3_ENDPOINT_URL}")
            s3_config_lines.append("region: ${S3_REGION}")
            artifact_base_path_line = "\n      ".join(s3_config_lines)

        shared_replacements = {
            "__DEFAULT_ARTIFACT_SERVICE_TYPE__": artifact_type,
            "__DEFAULT_ARTIFACT_SERVICE_SCOPE__": artifact_scope,
        }

        modified_shared_content = shared_template_content
        for placeholder, value in shared_replacements.items():
            modified_shared_content = modified_shared_content.replace(
                placeholder, str(value)
            )

        if not artifact_base_path_line:
            modified_shared_content = re.sub(
                r"\s*# __DEFAULT_ARTIFACT_SERVICE_BASE_PATH_LINE__.*",
                "",
                modified_shared_content,
            )
        else:
            modified_shared_content = modified_shared_content.replace(
                "      # __DEFAULT_ARTIFACT_SERVICE_BASE_PATH_LINE__",
                f"      {artifact_base_path_line}",
            )

        shared_config_dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(shared_config_dest_path, "w", encoding="utf-8") as f:
            f.write(modified_shared_content)
        click.echo(f"  Configured: {shared_config_dest_path.relative_to(project_root)}")

    except Exception as e:
        click.echo(
            click.style(
                f"Error configuring file {shared_config_dest_path}: {e}", fg="red"
            ),
            err=True,
        )
        return False

    try:
        logging_config_dest_path = project_root / "configs" / "logging_config.yaml"
        logging_template_content = load_template("logging_config_template.yaml")
        with open(logging_config_dest_path, "w", encoding="utf-8") as f:
            f.write(logging_template_content)
        click.echo(
            f"  Configured: {logging_config_dest_path.relative_to(project_root)}"
        )
    except Exception as e:
        error_message = (
            f"Error configuring file {logging_config_dest_path}: {e}"
            if logging_config_dest_path
            else f"Error configuring logging configuration: {e}"
        )
        click.echo(
            click.style(error_message, fg="red"),
            err=True,
        )
        return False

    main_orchestrator_path = (
        project_root / "configs" / "agents" / "main_orchestrator.yaml"
    )

    try:
        orchestrator_template_content = load_template("main_orchestrator.yaml")

        formatted_name = get_formatted_names(options["agent_name"])
        kebab_case_name = formatted_name.get("KEBAB_CASE_NAME")

        deny_list_line = ""
        if deny_list:
            deny_list_yaml = (
                yaml.dump(deny_list, Dumper=yaml.SafeDumper, default_flow_style=True)
                .strip()
                .replace("'", '"')
            )
            deny_list_line = f"deny_list: {deny_list_yaml}"

        default_instruction = """You are the Orchestrator Agent within an AI agentic system. Your primary responsibilities are to:
        1. Process tasks received from external sources via the system Gateway.
        2. Analyze each task to determine the optimal execution strategy:
           a. Single Agent Delegation: If the task can be fully addressed by a single peer agent (based on their declared capabilities/description), delegate the task to that agent.
           b. Multi-Agent Coordination: If task completion requires a coordinated effort from multiple peer agents: first, devise a logical execution plan (detailing the sequence of agent invocations and any necessary data handoffs). Then, manage the execution of this plan, invoking each agent in the defined order.
           c. Direct Execution: If the task is not suitable for delegation (neither to a single agent nor a multi-agent sequence) and falls within your own capabilities, execute the task yourself.

        Artifact Management Guidelines:
        - You must review your artifacts and return the ones that are important for the user by using artifact_return embed. You can use list_artifacts to see all available artifacts.
        - Provide regular progress updates using `status_update` embed directives, especially before initiating any tool call."""

        session_service_lines = [
            f'type: "sql"',
            'database_url: "${ORCHESTRATOR_DATABASE_URL, sqlite:///orchestrator.db}"',
            f'default_behavior: "PERSISTENT"',
        ]
        session_service_block = "\n" + "\n".join(
            [f"        {line}" for line in session_service_lines]
        )

        orchestrator_replacements = {
            "__NAMESPACE__": "${NAMESPACE}",
            "__APP_NAME__": f"{kebab_case_name}_app",
            "__SUPPORTS_STREAMING__": str(options["supports_streaming"]).lower(),
            "__AGENT_NAME__": options["agent_name"],
            "__LOG_FILE_NAME__": f"{kebab_case_name}.log",
            "__INSTRUCTION__": default_instruction,
            "__SESSION_SERVICE__": session_service_block,
            "__ARTIFACT_SERVICE__": "*default_artifact_service",
            "__ARTIFACT_HANDLING_MODE__": artifact_handling_mode,
            "__ENABLE_EMBED_RESOLUTION__": str(enable_embed_resolution).lower(),
            "__ENABLE_ARTIFACT_CONTENT_INSTRUCTION__": str(
                enable_artifact_content_instruction
            ).lower(),
            "__AGENT_CARD_DESCRIPTION__": agent_card_description,
            "__DEFAULT_INPUT_MODES__": yaml.dump(
                default_input_modes, Dumper=yaml.SafeDumper, default_flow_style=True
            )
            .strip()
            .replace("'", '"'),
            "__DEFAULT_OUTPUT_MODES__": yaml.dump(
                default_output_modes, Dumper=yaml.SafeDumper, default_flow_style=True
            )
            .strip()
            .replace("'", '"'),
            "__AGENT_CARD_PUBLISHING_INTERVAL__": str(agent_card_publishing_interval),
            "__AGENT_DISCOVERY_ENABLED__": str(agent_discovery_enabled).lower(),
            "__INTER_AGENT_COMMUNICATION_ALLOW_LIST__": yaml.dump(
                allow_list, Dumper=yaml.SafeDumper, default_flow_style=True
            )
            .strip()
            .replace("'", '"'),
            "__INTER_AGENT_COMMUNICATION_TIMEOUT__": str(
                inter_agent_communication_timeout
            ),
        }

        modified_orchestrator_content = orchestrator_template_content
        for placeholder, value in orchestrator_replacements.items():
            modified_orchestrator_content = modified_orchestrator_content.replace(
                placeholder, str(value)
            )

        if deny_list:
            modified_orchestrator_content = modified_orchestrator_content.replace(
                "__INTER_AGENT_COMMUNICATION_DENY_LIST_LINE__",
                deny_list_line,
            )
        else:
            modified_orchestrator_content = re.sub(
                r"^\s*__INTER_AGENT_COMMUNICATION_DENY_LIST_LINE__\n?$",
                "",
                modified_orchestrator_content,
                flags=re.MULTILINE,
            )

        main_orchestrator_path.parent.mkdir(parents=True, exist_ok=True)
        with open(main_orchestrator_path, "w", encoding="utf-8") as f:
            f.write(modified_orchestrator_content)

        click.echo(f"  Created: {main_orchestrator_path.relative_to(project_root)}")
        return True
    except Exception as e:
        click.echo(
            click.style(f"Error creating file {main_orchestrator_path}: {e}", fg="red"),
            err=True,
        )
        return False
