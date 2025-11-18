import json
import sys
from pathlib import Path

import click
import yaml

from config_portal.backend.common import AGENT_DEFAULTS, USE_DEFAULT_SHARED_ARTIFACT, USE_DEFAULT_SHARED_SESSION

from ...utils import (
    ask_if_not_provided,
    ask_yes_no_question,
    create_and_validate_database,
    get_formatted_names,
    indent_multiline_string,
    load_template,
)
from .web_add_agent_step import launch_add_agent_web_portal

DATABASE_URL_KEY = "database_url"


def _append_to_env_file(project_root: Path, key: str, value: str):
    env_path = project_root / ".env"
    try:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f'\n{key}="{value}"\n')
        return True
    except OSError as e:
        click.echo(
            click.style(f"Error appending to .env file: {e}", fg="red"), err=True
        )
        return False


def _write_agent_yaml_from_data(
    agent_name_input: str, config_options: dict, project_root: Path
) -> tuple[bool, str, str]:
    """
    Writes the agent YAML file based on provided configuration options.
    """
    agents_config_dir = project_root / "configs" / "agents"
    agents_config_dir.mkdir(parents=True, exist_ok=True)

    formatted_names = get_formatted_names(agent_name_input)
    agent_name_camel = config_options.get(
        "agent_name", formatted_names["PASCAL_CASE_NAME"]
    )
    file_name_snake = formatted_names["SNAKE_CASE_NAME"]

    agent_config_file_path = agents_config_dir / f"{file_name_snake}_agent.yaml"

    try:
        modified_content = load_template("agent_template.yaml")
        session_service_type_opt = config_options.get("session_service_type")
        if session_service_type_opt and session_service_type_opt != USE_DEFAULT_SHARED_SESSION:
            type_val = session_service_type_opt
            behavior_val = config_options.get(
                "session_service_behavior", AGENT_DEFAULTS["session_service_behavior"]
            )

            session_service_lines = [
                f'type: "{type_val}"',
                f'default_behavior: "{behavior_val}"',
            ]

            if type_val == "sql":
                database_url_placeholder = (
                    f"${{{formatted_names['SNAKE_UPPER_CASE_NAME']}_DATABASE_URL, sqlite:///{file_name_snake}.db}}"
                )
                session_service_lines.append(
                    f'database_url: "{database_url_placeholder}"'
                )

            session_service_block = "\n" + "\n".join(
                [f"        {line}" for line in session_service_lines]
            )
        else:
            session_service_block = "*default_session_service"
        artifact_service_type_opt = config_options.get("artifact_service_type")
        if (
            artifact_service_type_opt
            and artifact_service_type_opt != USE_DEFAULT_SHARED_ARTIFACT
        ):
            type_val = artifact_service_type_opt
            scope_val = config_options.get(
                "artifact_service_scope", AGENT_DEFAULTS["artifact_service_scope"]
            )
            custom_artifact_lines = [f'type: "{type_val}"']
            if type_val == "filesystem":
                base_path_val = config_options.get(
                    "artifact_service_base_path",
                    AGENT_DEFAULTS["artifact_service_base_path"],
                )
                custom_artifact_lines.append(f'base_path: "{base_path_val}"')
            elif type_val == "s3":
                custom_artifact_lines.append("bucket_name: ${S3_BUCKET_NAME}")
                custom_artifact_lines.append("endpoint_url: ${S3_ENDPOINT_URL}")
                custom_artifact_lines.append("region: ${S3_REGION}")
            custom_artifact_lines.append(f"artifact_scope: {scope_val}")
            artifact_service_block = "\n" + "\n".join(
                [f"        {line}" for line in custom_artifact_lines]
            )
        else:
            artifact_service_block = "*default_artifact_service"

        tools_data = config_options.get("tools")
        actual_tools_list = []
        if isinstance(tools_data, str):
            try:
                actual_tools_list = json.loads(tools_data)
                if not isinstance(actual_tools_list, list):
                    click.echo(
                        click.style(
                            "Warning: Tools data was a string but not a valid JSON list. Defaulting to empty tools list.",
                            fg="yellow",
                        ),
                        err=True,
                    )
                    actual_tools_list = []
            except json.JSONDecodeError:
                click.echo(
                    click.style(
                        f"Warning: Could not parse tools JSON string: {tools_data}. Defaulting to empty tools list.",
                        fg="yellow",
                    ),
                    err=True,
                )
                actual_tools_list = []
        elif isinstance(tools_data, list):
            actual_tools_list = tools_data

        for tool in actual_tools_list:
            if (
                tool.get("tool_type") == "mcp"
                and "connection_params" in tool
                and "timeout" not in tool["connection_params"]
            ):
                tool["connection_params"]["timeout"] = 30

        tools_replacement_value = yaml.dump(
            actual_tools_list,
            Dumper=yaml.SafeDumper,
            default_flow_style=False,
            indent=2,
        ).strip()

        if "\n" in tools_replacement_value:
            tools_replacement_value = indent_multiline_string(
                tools_replacement_value, 8, True
            )

        actual_skills_list = []
        skills_from_gui = config_options.get("agent_card_skills")
        skills_from_cli_str = config_options.get("agent_card_skills_str")

        if isinstance(skills_from_gui, list):
            actual_skills_list = skills_from_gui
        elif isinstance(skills_from_cli_str, str):
            try:
                parsed_skills = json.loads(skills_from_cli_str)
                if isinstance(parsed_skills, list):
                    actual_skills_list = parsed_skills
                else:
                    click.echo(
                        click.style(
                            f"Warning: Skills string '{skills_from_cli_str}' was not a valid JSON list. Defaulting to empty skills list.",
                            fg="yellow",
                        ),
                        err=True,
                    )
            except json.JSONDecodeError:
                click.echo(
                    click.style(
                        f"Warning: Could not parse skills JSON string: {skills_from_cli_str}. Defaulting to empty skills list.",
                        fg="yellow",
                    ),
                    err=True,
                )

        skills_replacement_value = "[]"
        if actual_skills_list:
            skills_dump = yaml.dump(
                actual_skills_list,
                Dumper=yaml.SafeDumper,
                default_flow_style=False,
                indent=2,
            ).strip()

            skills_replacement_value = indent_multiline_string(skills_dump, 10, True)

        instructions = config_options.get("instruction", AGENT_DEFAULTS["instruction"])
        instructions = instructions.replace("__AGENT_NAME__", agent_name_camel)
        instructions = indent_multiline_string(instructions, 8)

        replacements = {
            "__AGENT_NAME__": agent_name_camel,
            "__AGENT_SPACED_NAME__": get_formatted_names(agent_name_camel).get(
                "SPACED_CAPITALIZED_NAME"
            ),
            "__NAMESPACE__": config_options.get(
                "namespace", AGENT_DEFAULTS["namespace"]
            ),
            "__SUPPORTS_STREAMING__": str(
                config_options.get(
                    "supports_streaming", AGENT_DEFAULTS["supports_streaming"]
                )
            ).lower(),
            "__MODEL_ALIAS__": f"*{config_options.get('model_type', AGENT_DEFAULTS['model_type'])}_model",
            "__INSTRUCTION__": instructions,
            "__TOOLS_CONFIG__": tools_replacement_value,
            "__SESSION_SERVICE__": session_service_block,
            "__ARTIFACT_SERVICE__": artifact_service_block,
            "__ARTIFACT_HANDLING_MODE__": config_options.get(
                "artifact_handling_mode", AGENT_DEFAULTS["artifact_handling_mode"]
            ),
            "__ENABLE_EMBED_RESOLUTION__": str(
                config_options.get(
                    "enable_embed_resolution", AGENT_DEFAULTS["enable_embed_resolution"]
                )
            ).lower(),
            "__ENABLE_ARTIFACT_CONTENT_INSTRUCTION__": str(
                config_options.get(
                    "enable_artifact_content_instruction",
                    AGENT_DEFAULTS["enable_artifact_content_instruction"],
                )
            ).lower(),
            "__AGENT_CARD_DESCRIPTION__": indent_multiline_string(
                config_options.get(
                    "agent_card_description", AGENT_DEFAULTS["agent_card_description"]
                ),
                10,
            ),
            "__DEFAULT_INPUT_MODES__": yaml.dump(
                config_options.get(
                    "agent_card_default_input_modes",
                    AGENT_DEFAULTS["agent_card_default_input_modes"],
                ),
                Dumper=yaml.SafeDumper,
                default_flow_style=True,
            )
            .strip()
            .replace("'", '"'),
            "__DEFAULT_OUTPUT_MODES__": yaml.dump(
                config_options.get(
                    "agent_card_default_output_modes",
                    AGENT_DEFAULTS["agent_card_default_output_modes"],
                ),
                Dumper=yaml.SafeDumper,
                default_flow_style=True,
            )
            .strip()
            .replace("'", '"'),
            "__AGENT_CARD_SKILLS__": skills_replacement_value,
            "__AGENT_CARD_PUBLISHING_INTERVAL__": str(
                config_options.get(
                    "agent_card_publishing_interval",
                    AGENT_DEFAULTS["agent_card_publishing_interval"],
                )
            ),
            "__AGENT_DISCOVERY_ENABLED__": str(
                config_options.get(
                    "agent_discovery_enabled", AGENT_DEFAULTS["agent_discovery_enabled"]
                )
            ).lower(),
            "__INTER_AGENT_COMMUNICATION_ALLOW_LIST__": yaml.dump(
                config_options.get(
                    "inter_agent_communication_allow_list",
                    AGENT_DEFAULTS["inter_agent_communication_allow_list"],
                ),
                Dumper=yaml.SafeDumper,
                default_flow_style=True,
            )
            .strip()
            .replace("'", '"'),
            "__INTER_AGENT_COMMUNICATION_DENY_LIST__": yaml.dump(
                config_options.get(
                    "inter_agent_communication_deny_list",
                    AGENT_DEFAULTS["inter_agent_communication_deny_list"],
                ),
                Dumper=yaml.SafeDumper,
                default_flow_style=True,
            )
            .strip()
            .replace("'", '"'),
            "__INTER_AGENT_COMMUNICATION_TIMEOUT__": str(
                config_options.get(
                    "inter_agent_communication_timeout",
                    AGENT_DEFAULTS["inter_agent_communication_timeout"],
                )
            ),
        }

        for placeholder, value in replacements.items():
            modified_content = modified_content.replace(placeholder, str(value))
        if config_options.get(DATABASE_URL_KEY):
            env_key = f"{formatted_names['SNAKE_UPPER_CASE_NAME']}_DATABASE_URL"
            if config_options[DATABASE_URL_KEY] == "default_agent_db":
                db_file = project_root / "data" / f"{formatted_names['SNAKE_CASE_NAME']}.db"
                config_options[DATABASE_URL_KEY] = f"sqlite:///{db_file.resolve()}"
            if not _append_to_env_file(
                project_root, env_key, config_options[DATABASE_URL_KEY]
            ):
                return False, "Failed to write to .env file.", ""

        with open(agent_config_file_path, "w", encoding="utf-8") as f:
            f.write(modified_content)

        relative_file_path = str(agent_config_file_path.relative_to(project_root))
        return (
            True,
            f"Agent configuration created: {relative_file_path}",
            relative_file_path,
        )
    except Exception as e:
        import traceback

        click.echo(
            f"DEBUG: Error in _write_agent_yaml_from_data: {e}\n{traceback.format_exc()}",
            err=True,
        )
        return (
            False,
            f"Error creating agent configuration file {agent_config_file_path}: {e}",
            "",
        )


def create_agent_config(
    agent_name_input: str, cli_provided_options: dict, skip_interactive: bool
) -> bool:
    """
    Collects options (interactively or from CLI) and creates a new agent configuration file.
    This is the main function called by the CLI for non-GUI agent creation.
    """
    click.echo(f"Configuring agent '{agent_name_input}' via CLI...")

    project_root = Path.cwd()
    collected_options = cli_provided_options.copy()

    formatted_names = get_formatted_names(agent_name_input)
    agent_name_camel_case = formatted_names["PASCAL_CASE_NAME"]
    collected_options["agent_name"] = agent_name_camel_case

    collected_options["namespace"] = ask_if_not_provided(
        collected_options,
        "namespace",
        "Enter namespace (e.g., myorg/dev, or leave for ${NAMESPACE})",
        AGENT_DEFAULTS["namespace"],
        skip_interactive,
    )
    collected_options["supports_streaming"] = ask_if_not_provided(
        collected_options,
        "supports_streaming",
        "Enable streaming support?",
        AGENT_DEFAULTS["supports_streaming"],
        skip_interactive,
        is_bool=True,
    )
    collected_options["model_type"] = ask_if_not_provided(
        collected_options,
        "model_type",
        "Enter model type",
        AGENT_DEFAULTS["model_type"],
        skip_interactive,
        choices=[
            "planning",
            "general",
            "image_gen",
            "report_gen",
            "multimodal",
            "gemini_pro",
        ],
    )
    default_instruction = AGENT_DEFAULTS["instruction"].replace(
        "__AGENT_NAME__", agent_name_camel_case
    )
    collected_options["instruction"] = ask_if_not_provided(
        collected_options,
        "instruction",
        "Enter agent instruction",
        default_instruction,
        skip_interactive,
    )

    collected_options["session_service_type"] = "sql"

    collected_options["artifact_service_type"] = ask_if_not_provided(
        collected_options,
        "artifact_service_type",
        "Artifact service type",
        AGENT_DEFAULTS["artifact_service_type"],
        skip_interactive,
        choices=[USE_DEFAULT_SHARED_ARTIFACT, "memory", "filesystem", "gcs", "s3"],
    )
    if collected_options["artifact_service_type"] != USE_DEFAULT_SHARED_ARTIFACT:
        if collected_options.get("artifact_service_type") == "filesystem":
            collected_options["artifact_service_base_path"] = ask_if_not_provided(
                collected_options,
                "artifact_service_base_path",
                "Artifact service base path",
                AGENT_DEFAULTS["artifact_service_base_path"],
                skip_interactive,
            )
        elif collected_options.get("artifact_service_type") == "s3":
            collected_options["artifact_service_bucket_name"] = ask_if_not_provided(
                collected_options,
                "artifact_service_bucket_name",
                "S3 bucket name",
                AGENT_DEFAULTS.get("artifact_service_bucket_name", ""),
                skip_interactive,
            )
            collected_options["artifact_service_endpoint_url"] = ask_if_not_provided(
                collected_options,
                "artifact_service_endpoint_url",
                "S3 endpoint URL (leave empty for AWS S3)",
                AGENT_DEFAULTS.get("artifact_service_endpoint_url", ""),
                skip_interactive,
            )
            collected_options["artifact_service_region"] = ask_if_not_provided(
                collected_options,
                "artifact_service_region",
                "S3 region",
                AGENT_DEFAULTS.get("artifact_service_region", "us-east-1"),
                skip_interactive,
            )
        collected_options["artifact_service_scope"] = ask_if_not_provided(
            collected_options,
            "artifact_service_scope",
            "Artifact service scope",
            AGENT_DEFAULTS["artifact_service_scope"],
            skip_interactive,
            choices=["namespace", "app", "custom"],
        )

    collected_options["artifact_handling_mode"] = ask_if_not_provided(
        collected_options,
        "artifact_handling_mode",
        "Artifact handling mode",
        AGENT_DEFAULTS["artifact_handling_mode"],
        skip_interactive,
        choices=["ignore", "embed", "reference"],
    )
    collected_options["enable_embed_resolution"] = ask_if_not_provided(
        collected_options,
        "enable_embed_resolution",
        "Enable embed resolution?",
        AGENT_DEFAULTS["enable_embed_resolution"],
        skip_interactive,
        is_bool=True,
    )
    collected_options["enable_artifact_content_instruction"] = ask_if_not_provided(
        collected_options,
        "enable_artifact_content_instruction",
        "Enable artifact content instruction?",
        AGENT_DEFAULTS["enable_artifact_content_instruction"],
        skip_interactive,
        is_bool=True,
    )
    collected_options["agent_card_description"] = ask_if_not_provided(
        collected_options,
        "agent_card_description",
        "Agent card description",
        AGENT_DEFAULTS["agent_card_description"],
        skip_interactive,
    )
    default_input_modes_str = ask_if_not_provided(
        collected_options,
        "agent_card_default_input_modes_str",
        "Agent card default input modes (comma-separated)",
        ",".join(AGENT_DEFAULTS["agent_card_default_input_modes"]),
        skip_interactive,
    )
    collected_options["agent_card_default_input_modes"] = [
        mode.strip()
        for mode in (default_input_modes_str or "").split(",")
        if mode.strip()
    ]

    default_output_modes_str = ask_if_not_provided(
        collected_options,
        "agent_card_default_output_modes_str",
        "Agent card default output modes (comma-separated)",
        ",".join(AGENT_DEFAULTS["agent_card_default_output_modes"]),
        skip_interactive,
    )
    collected_options["agent_card_default_output_modes"] = [
        mode.strip()
        for mode in (default_output_modes_str or "").split(",")
        if mode.strip()
    ]

    collected_options["agent_card_skills_str"] = ask_if_not_provided(
        collected_options,
        "agent_card_skills_str",
        "Agent card skills (JSON array string)",
        AGENT_DEFAULTS.get("agent_card_skills_str", "[]"),
        skip_interactive,
    )

    collected_options["agent_discovery_enabled"] = ask_if_not_provided(
        collected_options,
        "agent_discovery_enabled",
        "Enable agent discovery?",
        AGENT_DEFAULTS["agent_discovery_enabled"],
        skip_interactive,
        is_bool=True,
    )
    collected_options["agent_card_publishing_interval"] = ask_if_not_provided(
        collected_options,
        "agent_card_publishing_interval",
        "Agent card publishing interval (seconds)",
        AGENT_DEFAULTS["agent_card_publishing_interval"],
        skip_interactive,
        type=int,
    )
    allow_list_str = ask_if_not_provided(
        collected_options,
        "inter_agent_communication_allow_list_str",
        "Inter-agent allow list (comma-separated)",
        ",".join(AGENT_DEFAULTS["inter_agent_communication_allow_list"]),
        skip_interactive,
    )
    allow_list_items = (allow_list_str or "").split(",")
    collected_options["inter_agent_communication_allow_list"] = [
        item.strip() for item in allow_list_items if item.strip()
    ]

    deny_list_str = ask_if_not_provided(
        collected_options,
        "inter_agent_communication_deny_list_str",
        "Inter-agent deny list (comma-separated)",
        ",".join(AGENT_DEFAULTS["inter_agent_communication_deny_list"]),
        skip_interactive,
    )
    deny_list_items = (deny_list_str or "").split(",")
    collected_options["inter_agent_communication_deny_list"] = [
        item.strip() for item in deny_list_items if item.strip()
    ]

    collected_options["inter_agent_communication_timeout"] = ask_if_not_provided(
        collected_options,
        "inter_agent_communication_timeout",
        "Inter-agent timeout (seconds)",
        AGENT_DEFAULTS["inter_agent_communication_timeout"],
        skip_interactive,
        type=int,
    )

    tools_json_str = ask_if_not_provided(
        collected_options,
        "tools",
        "Tools configuration (JSON string of list)",
        AGENT_DEFAULTS.get("tools", "[]"),
        skip_interactive,
    )
    try:
        tools_list = json.loads(tools_json_str or "[]")
        if not isinstance(tools_list, list):
            tools_list = []
            if not skip_interactive:
                click.echo(
                    "Warning: Tools input was not a valid JSON list. Defaulting to empty.",
                    err=True,
                )
        collected_options["tools"] = tools_list
    except json.JSONDecodeError:
        collected_options["tools"] = []
        if not skip_interactive:
            click.echo(
                f"Warning: Invalid JSON for tools: {tools_json_str}. Defaulting to empty.",
                err=True,
            )

    success, message, _ = _write_agent_yaml_from_data(
        agent_name_input, collected_options, project_root
    )

    if success:
        click.echo(click.style(message, fg="green"))
        return True
    else:
        click.echo(click.style(message, fg="red"), err=True)
        return False


@click.command(name="agent")
@click.argument("name", required=False)
@click.option("--gui", is_flag=True, help="Launch the web UI to configure the agent.")
@click.option(
    "--skip",
    is_flag=True,
    help="Skip interactive prompts and use defaults (CLI mode only).",
)
@click.option("--namespace", help="namespace (e.g., myorg/dev).")
@click.option("--supports-streaming", type=bool, help="Enable streaming support.")
@click.option(
    "--model-type",
    type=click.Choice(
        ["planning", "general", "image_gen", "report_gen", "multimodal", "gemini_pro"]
    ),
    help="Model type for the agent.",
)
@click.option("--instruction", help="Custom instruction for the agent.")
@click.option(
    "--session-service-type",
    type=click.Choice(["sql", "memory", "vertex_rag"]),
    help="Session service type.",
)
@click.option(
    "--session-service-behavior",
    type=click.Choice(["PERSISTENT", "RUN_BASED"]),
    help="Session service behavior.",
)
@click.option(
    "--database-url", help="Database URL for session service (if type is 'sql')."
)
@click.option(
    "--artifact-service-type",
    type=click.Choice(["memory", "filesystem", "gcs", "s3"]),
    help="Artifact service type.",
)
@click.option(
    "--artifact-service-base-path", help="Base path for filesystem artifact service."
)
@click.option(
    "--artifact-service-bucket-name",
    help="S3 bucket name (for s3 artifact service type).",
)
@click.option(
    "--artifact-service-endpoint-url",
    help="S3 endpoint URL (for s3 artifact service type, optional for AWS S3).",
)
@click.option(
    "--artifact-service-region", help="S3 region (for s3 artifact service type)."
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
@click.option("--enable-embed-resolution", type=bool, help="Enable embed resolution.")
@click.option(
    "--enable-artifact-content-instruction",
    type=bool,
    help="Enable artifact content instruction.",
)
@click.option(
    "--enable-builtin-artifact-tools", type=bool, help="Enable built-in artifact tools."
)
@click.option(
    "--enable-builtin-data-tools", type=bool, help="Enable built-in data tools."
)
@click.option("--agent-card-description", help="Description for the agent card.")
@click.option(
    "--agent-card-default-input-modes-str",
    help="Comma-separated default input modes for agent card.",
)
@click.option(
    "--agent-card-default-output-modes-str",
    help="Comma-separated default output modes for agent card.",
)
@click.option(
    "--agent-card-publishing-interval",
    type=int,
    help="Agent card publishing interval in seconds.",
)
@click.option("--agent-discovery-enabled", type=bool, help="Enable agent discovery.")
@click.option(
    "--inter-agent-communication-allow-list-str",
    help="Comma-separated allow list for inter-agent communication.",
)
@click.option(
    "--inter-agent-communication-deny-list-str",
    help="Comma-separated deny list for inter-agent communication.",
)
@click.option(
    "--inter-agent-communication-timeout",
    type=int,
    help="Timeout in seconds for inter-agent communication.",
)
def add_agent(name: str, gui: bool = False, **kwargs):
    """
    Creates a new agent configuration via CLI or Web UI.

    NAME: Name of the agent component to create (e.g., my-new-agent).
    """
    if not gui and not name:
        click.echo(
            click.style(
                "Error: You must provide an agent name when not using the --gui option.",
                fg="red",
            ),
            err=True,
        )
        return
    if gui:
        click.echo(f"Launching Add Agent GUI for '{name}'...")
        cli_options_for_gui = {"name": name}
        agent_name, agent_options, project_root = launch_add_agent_web_portal(
            cli_options_for_gui
        )
        success, message, _ = _write_agent_yaml_from_data(
            agent_name, agent_options, project_root
        )

        if success:
            click.echo(click.style(message, fg="green"))
        else:
            click.echo(click.style(message, fg="red"), err=True)

    else:
        cli_options = {k: v for k, v in kwargs.items() if v is not None}
        skip_interactive = kwargs.get("skip", False)

        if not create_agent_config(name, cli_options, skip_interactive):
            click.echo(
                click.style(
                    f"Failed to create agent configuration for '{name}' using CLI.",
                    fg="red",
                ),
                err=True,
            )
            sys.exit(1)
