import click
from pathlib import Path

from config_portal.backend.common import GATEWAY_DEFAULTS, USE_DEFAULT_SHARED_ARTIFACT
from ...utils import (
    get_formatted_names,
    load_template,
    error_exit,
    ask_if_not_provided,
    indent_multiline_string,
)
from .web_add_gateway_step import launch_add_gateway_web_portal


def create_gateway_files(
    gateway_name_input: str,
    cli_options: dict,
    project_root: Path,
    skip_interactive: bool,
):
    """
    Generates the gateway skeleton files based on templates and collected options.
    """
    collected_options = cli_options.copy()
    formatted_names = get_formatted_names(gateway_name_input)
    gateway_name_snake_case = formatted_names["SNAKE_CASE_NAME"]
    gateway_name_pascal_case = formatted_names["PASCAL_CASE_NAME"]
    gateway_name_upper_case = formatted_names["SNAKE_UPPER_CASE_NAME"]
    gateway_name_kebab_case = formatted_names["KEBAB_CASE_NAME"]

    collected_options["namespace"] = ask_if_not_provided(
        collected_options,
        "namespace",
        "Enter namespace for the gateway (e.g., myorg/dev, or leave for ${NAMESPACE})",
        GATEWAY_DEFAULTS["namespace"],
        skip_interactive,
    )
    default_gateway_id = (
        f"{gateway_name_kebab_case}{GATEWAY_DEFAULTS['gateway_id_suffix']}"
    )
    collected_options["gateway_id"] = ask_if_not_provided(
        collected_options,
        "gateway_id",
        f"Enter Gateway ID (default: {default_gateway_id})",
        default_gateway_id,
        skip_interactive,
    )

    collected_options["artifact_service_type"] = ask_if_not_provided(
        collected_options,
        "artifact_service_type",
        "Artifact service type for the gateway",
        GATEWAY_DEFAULTS["artifact_service_type"],
        skip_interactive,
        choices=[USE_DEFAULT_SHARED_ARTIFACT, "memory", "filesystem", "gcs"],
    )

    if collected_options["artifact_service_type"] != USE_DEFAULT_SHARED_ARTIFACT:
        if collected_options.get("artifact_service_type") == "filesystem":
            default_artifact_base_path = GATEWAY_DEFAULTS[
                "artifact_service_base_path"
            ].replace("__GATEWAY_NAME_SNAKE_CASE__", gateway_name_snake_case)
            collected_options["artifact_service_base_path"] = ask_if_not_provided(
                collected_options,
                "artifact_service_base_path",
                f"Artifact service base path (default: {default_artifact_base_path})",
                default_artifact_base_path,
                skip_interactive,
            )
        collected_options["artifact_service_scope"] = ask_if_not_provided(
            collected_options,
            "artifact_service_scope",
            "Artifact service scope",
            GATEWAY_DEFAULTS["artifact_service_scope"],
            skip_interactive,
            choices=["namespace", "app", "custom"],
        )

    if (
        "system_purpose" not in collected_options
        or collected_options["system_purpose"] is None
    ):
        if skip_interactive:
            collected_options["system_purpose"] = GATEWAY_DEFAULTS["system_purpose"]
        else:
            click.echo("Define system purpose for the gateway (opens editor):")
            edited_purpose = click.edit(text=GATEWAY_DEFAULTS["system_purpose"])
            collected_options["system_purpose"] = (
                edited_purpose
                if edited_purpose is not None
                else GATEWAY_DEFAULTS["system_purpose"]
            )

    if (
        "response_format" not in collected_options
        or collected_options["response_format"] is None
    ):
        if skip_interactive:
            collected_options["response_format"] = GATEWAY_DEFAULTS["response_format"]
        else:
            click.echo("Define response format for the gateway (opens editor):")
            edited_format = click.edit(text=GATEWAY_DEFAULTS["response_format"])
            collected_options["response_format"] = (
                edited_format
                if edited_format is not None
                else GATEWAY_DEFAULTS["response_format"]
            )

    configs_gateway_dir = project_root / "configs" / "gateways"
    src_gateway_dir = project_root / "src" / gateway_name_snake_case

    if (
        src_gateway_dir.exists()
        or (configs_gateway_dir / f"{gateway_name_snake_case}_config.yaml").exists()
    ):
        if not skip_interactive:
            if not click.confirm(
                click.style(
                    f"Warning: Gateway '{gateway_name_snake_case}' already exists or has conflicting files. Overwrite?",
                    fg="yellow",
                )
            ):
                click.echo("Operation cancelled by user.")
                return False, "Operation cancelled."

    try:
        configs_gateway_dir.mkdir(parents=True, exist_ok=True)
        src_gateway_dir.mkdir(parents=True, exist_ok=True)

        artifact_service_type_opt = collected_options.get("artifact_service_type")
        if (
            artifact_service_type_opt
            and artifact_service_type_opt != USE_DEFAULT_SHARED_ARTIFACT
        ):
            type_val = artifact_service_type_opt
            scope_val = collected_options.get(
                "artifact_service_scope", GATEWAY_DEFAULTS["artifact_service_scope"]
            )
            custom_artifact_lines = [f'type: "{type_val}"']
            if type_val == "filesystem":
                base_path_val = collected_options.get("artifact_service_base_path")
                if (
                    "ARTIFACT_BASE_PATH" not in base_path_val
                    and "${" not in base_path_val
                ):
                    base_path_val_processed = (
                        f"${{ARTIFACT_BASE_PATH, {base_path_val}}}"
                    )
                else:
                    base_path_val_processed = f'"{base_path_val}"'

                custom_artifact_lines.append(f"base_path: {base_path_val_processed}")

            custom_artifact_lines.append(f"artifact_scope: {scope_val}")
            artifact_service_block = "\n" + "\n".join(
                [f"        {line}" for line in custom_artifact_lines]
            )
        else:
            artifact_service_block = "*default_artifact_service"

        system_purpose_value = collected_options.get("system_purpose", "")
        if system_purpose_value is None:
            system_purpose_value = ""
        formatted_system_purpose = indent_multiline_string(system_purpose_value, 8)

        response_format_value = collected_options.get("response_format", "")
        if response_format_value is None:
            response_format_value = ""
        formatted_response_format = indent_multiline_string(response_format_value, 8)

        placeholders = {
            "__GATEWAY_NAME_SNAKE_CASE__": gateway_name_snake_case,
            "__GATEWAY_NAME_PASCAL_CASE__": gateway_name_pascal_case,
            "__GATEWAY_NAME_UPPER_CASE__": gateway_name_upper_case,
            "__GATEWAY_NAME_KEBAB_CASE__": gateway_name_kebab_case,
            "__APP_CONFIG_NAMESPACE__": collected_options["namespace"],
            "__GATEWAY_ID__": collected_options["gateway_id"],
            "__ARTIFACT_SERVICE__": artifact_service_block,
            "__SYSTEM_PURPOSE__": formatted_system_purpose,
            "__RESPONSE_FORMAT__": formatted_response_format,
        }

        template_files_map = {
            "gateway_config_template.yaml": configs_gateway_dir
            / f"{gateway_name_snake_case}_config.yaml",
            "gateway_app_template.py": src_gateway_dir / "app.py",
            "gateway_component_template.py": src_gateway_dir / "component.py",
        }

        generated_files_relative_paths = []

        for template_name, target_path in template_files_map.items():
            template_content = load_template(template_name)
            processed_content = template_content
            for placeholder, value in placeholders.items():
                processed_content = processed_content.replace(placeholder, value)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(processed_content)
            generated_files_relative_paths.append(
                str(target_path.relative_to(project_root))
            )

        py_init_file = src_gateway_dir / "__init__.py"
        with open(py_init_file, "w", encoding="utf-8") as f:
            f.write("")
        generated_files_relative_paths.append(
            str(py_init_file.relative_to(project_root))
        )

        success_message = f"Gateway '{gateway_name_snake_case}' skeleton created successfully.\nGenerated files:\n"
        for rel_path in generated_files_relative_paths:
            success_message += f"  - {rel_path}\n"
        success_message += "\nNext steps:\n"
        success_message += f"1. Review and customize the specific parameters in '{generated_files_relative_paths[0]}'.\n"
        success_message += f"2. Define your gateway's specific schema in '{generated_files_relative_paths[2]}'.\n"
        success_message += (
            f"3. Implement the core logic in '{generated_files_relative_paths[3]}'."
        )

        return True, success_message

    except FileNotFoundError as fnf_error:
        error_message = (
            f"Error creating gateway files: Template file not found. {fnf_error}"
        )
        click.echo(click.style(error_message, fg="red"), err=True)
        return False, error_message
    except Exception as e:
        import traceback

        error_message = f"An unexpected error occurred: {e}\n{traceback.format_exc()}"
        click.echo(click.style(error_message, fg="red"), err=True)
        return False, error_message


@click.command(name="gateway")
@click.argument("name", required=False)
@click.option("--namespace", help="namespace for the gateway (e.g., myorg/dev).")
@click.option("--gateway-id", help="Custom Gateway ID for the gateway.")
@click.option(
    "--artifact-service-type",
    type=click.Choice([USE_DEFAULT_SHARED_ARTIFACT, "memory", "filesystem", "gcs"]),
    help="Artifact service type for the gateway.",
)
@click.option(
    "--artifact-service-base-path",
    help="Base path for filesystem artifact service (if type is 'filesystem').",
)
@click.option(
    "--artifact-service-scope",
    type=click.Choice(["namespace", "app", "custom"]),
    help="Artifact service scope (if not using default shared artifact service).",
)
@click.option(
    "--system-purpose", help="System purpose for the gateway (can be multi-line)."
)
@click.option(
    "--response-format", help="Response format for the gateway (can be multi-line)."
)
@click.option(
    "--skip",
    is_flag=True,
    help="Skip interactive prompts and use defaults (CLI mode only).",
)
@click.option("--gui", is_flag=True, help="Launch the web UI to configure the gateway.")
def add_gateway(name: str | None, gui: bool = False, **kwargs):
    """
    Creates a new gateway skeleton structure via CLI or Web UI.

    NAME: Name of the gateway component to create (e.g., my-new-gateway).
          Required if not using --gui.
    """
    project_root = Path.cwd()
    gui_initial_options = {
        k: v for k, v in kwargs.items() if v is not None and k not in ["gui", "skip"]
    }
    if name:
        gui_initial_options["name"] = name

    if gui:
        click.echo("Launching Add Gateway GUI...")
        gui_result = launch_add_gateway_web_portal(cli_options=gui_initial_options)

        if gui_result:
            gateway_name_from_gui, collected_options_from_gui, project_root_from_gui = (
                gui_result
            )
            success, message = create_gateway_files(
                gateway_name_input=gateway_name_from_gui,
                cli_options=collected_options_from_gui,
                project_root=project_root_from_gui,
                skip_interactive=True,
            )
            if success:
                click.echo(click.style(message, fg="green"))
        else:
            click.echo(
                click.style(
                    "Gateway creation via GUI was cancelled or failed.", fg="yellow"
                ),
                err=True,
            )
        return

    if not name:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        error_exit("Error: Gateway NAME is required when not using the --gui option.")

    cli_options_for_creation = {
        k: v for k, v in kwargs.items() if v is not None and k not in ["gui", "skip"]
    }
    skip_interactive_cli = kwargs.get("skip", False)

    click.echo(f"Creating gateway skeleton for '{name}' via CLI...")
    success, message = create_gateway_files(
        name, cli_options_for_creation, project_root, skip_interactive_cli
    )

    if success:
        click.echo(click.style(message, fg="green"))
