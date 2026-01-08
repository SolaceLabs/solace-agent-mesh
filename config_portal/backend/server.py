import sys
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import os
from pathlib import Path
from .common import (
    INIT_DEFAULT,
    CONTAINER_RUN_COMMAND,
    AGENT_DEFAULTS,
    GATEWAY_DEFAULTS,
    USE_DEFAULT_SHARED_ARTIFACT,
)
from cli.utils import get_formatted_names

import shutil
import litellm
from collections import defaultdict

import logging

log = logging.getLogger("werkzeug")
log.disabled = True
cli_flask = sys.modules["flask.cli"]
cli_flask.show_server_banner = lambda *x: None
litellm.suppress_debug_info = True

config_portal_host = "CONFIG_PORTAL_HOST"

try:
    from solace_agent_mesh.agent.tools.registry import tool_registry
except ImportError as err:
    try:
        from src.solace_agent_mesh.agent.tools.registry import tool_registry
    except ImportError as exc:
        log.error(
            "Importing tool_registry failed. Ensure all the dependencies are installed and the import paths are correct, Error: %s",
            str(err),
        )
        raise err from exc


def get_agent_field_definitions():
    fields = []
    fields.append(
        {
            "name": "agent_name",
            "label": "Agent Name",
            "type": "text",
            "required": True,
            "description": "Unique name for this agent (will be CamelCased).",
            "default": "MyNewAgent",
        }
    )
    fields.append(
        {
            "name": "namespace",
            "label": "Namespace",
            "type": "text",
            "default": AGENT_DEFAULTS["namespace"],
            "description": "A2A topic namespace (e.g., myorg/dev). Can use ${NAMESPACE}.",
        }
    )
    fields.append(
        {
            "name": "supports_streaming",
            "label": "Supports Streaming",
            "type": "boolean",
            "default": AGENT_DEFAULTS["supports_streaming"],
        }
    )
    fields.append(
        {
            "name": "model_type",
            "label": "Model Type",
            "type": "select",
            "options": [
                "planning",
                "general",
                "image_gen",
                "report_gen",
                "multimodal",
                "gemini_pro",
            ],
            "default": AGENT_DEFAULTS["model_type"],
        }
    )
    fields.append(
        {
            "name": "instruction",
            "label": "Instruction",
            "type": "textarea",
            "default": AGENT_DEFAULTS["instruction"].replace(
                "__AGENT_NAME__", "__AGENT_NAME__"
            ),
            "description": "System instruction for the agent.",
        }
    )

    fields.append(
        {
            "name": "session_service_type",
            "label": "Session Service Type",
            "type": "select",
            "options": ["memory", "vertex_rag"],
            "default": AGENT_DEFAULTS["session_service_type"],
        }
    )
    fields.append(
        {
            "name": "session_service_behavior",
            "label": "Session Service Behavior",
            "type": "select",
            "options": ["PERSISTENT", "RUN_BASED"],
            "default": AGENT_DEFAULTS["session_service_behavior"],
        }
    )

    fields.append(
        {
            "name": "artifact_service_type",
            "label": "Artifact Service Type",
            "type": "select",
            "options": ["memory", "filesystem", "gcs"],
            "default": AGENT_DEFAULTS["artifact_service_type"],
        }
    )
    fields.append(
        {
            "name": "artifact_service_base_path",
            "label": "Artifact Service Base Path (if filesystem)",
            "type": "text",
            "default": AGENT_DEFAULTS["artifact_service_base_path"],
            "condition": {"field": "artifact_service_type", "value": "filesystem"},
        }
    )
    fields.append(
        {
            "name": "artifact_service_scope",
            "label": "Artifact Service Scope",
            "type": "select",
            "options": ["namespace", "app", "custom"],
            "default": AGENT_DEFAULTS["artifact_service_scope"],
        }
    )

    fields.append(
        {
            "name": "artifact_handling_mode",
            "label": "Artifact Handling Mode",
            "type": "select",
            "options": ["ignore", "embed", "reference"],
            "default": AGENT_DEFAULTS["artifact_handling_mode"],
        }
    )
    fields.append(
        {
            "name": "enable_embed_resolution",
            "label": "Enable Embed Resolution",
            "type": "boolean",
            "default": AGENT_DEFAULTS["enable_embed_resolution"],
        }
    )
    fields.append(
        {
            "name": "enable_artifact_content_instruction",
            "label": "Enable Artifact Content Instruction",
            "type": "boolean",
            "default": AGENT_DEFAULTS["enable_artifact_content_instruction"],
        }
    )
    fields.append(
        {
            "name": "agent_card_description",
            "label": "Agent Card Description",
            "type": "textarea",
            "default": AGENT_DEFAULTS["agent_card_description"],
        }
    )
    fields.append(
        {
            "name": "agent_card_default_input_modes_str",
            "label": "Agent Card Default Input Modes (comma-sep)",
            "type": "text",
            "default": ",".join(AGENT_DEFAULTS["agent_card_default_input_modes"]),
        }
    )
    fields.append(
        {
            "name": "agent_card_default_output_modes_str",
            "label": "Agent Card Default Output Modes (comma-sep)",
            "type": "text",
            "default": ",".join(AGENT_DEFAULTS["agent_card_default_output_modes"]),
        }
    )

    fields.append(
        {
            "name": "agent_card_publishing_interval",
            "label": "Agent Card Publishing Interval (s)",
            "type": "number",
            "default": AGENT_DEFAULTS["agent_card_publishing_interval"],
        }
    )
    fields.append(
        {
            "name": "agent_discovery_enabled",
            "label": "Enable Agent Discovery",
            "type": "boolean",
            "default": AGENT_DEFAULTS["agent_discovery_enabled"],
        }
    )

    fields.append(
        {
            "name": "inter_agent_communication_allow_list_str",
            "label": "Inter-Agent Allow List (comma-sep)",
            "type": "text",
            "default": ",".join(AGENT_DEFAULTS["inter_agent_communication_allow_list"]),
        }
    )
    fields.append(
        {
            "name": "inter_agent_communication_deny_list_str",
            "label": "Inter-Agent Deny List (comma-sep)",
            "type": "text",
            "default": ",".join(AGENT_DEFAULTS["inter_agent_communication_deny_list"]),
        }
    )
    fields.append(
        {
            "name": "inter_agent_communication_timeout",
            "label": "Inter-Agent Timeout (s)",
            "type": "number",
            "default": AGENT_DEFAULTS["inter_agent_communication_timeout"],
        }
    )

    return fields


def create_app(shared_config=None):
    """Factory function that creates the Flask application with configuration injected"""
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    EXCLUDE_OPTIONS = ["container_engine"]

    @app.route("/api/default_options", methods=["GET"])
    def get_default_options():
        """Endpoint that returns the default options for form initialization (init flow)"""
        path = request.args.get("path", "advanced")

        modified_default_options = INIT_DEFAULT.copy()

        base_exclude_options = EXCLUDE_OPTIONS.copy()
        quick_path_exclude_options = [
            "broker_url",
            "broker_vpn",
            "broker_username",
            "broker_password",
            "container_engine",
        ]

        exclude_options = base_exclude_options.copy()
        if path == "quick":
            exclude_options.extend(quick_path_exclude_options)
            modified_default_options["dev_mode"] = True
            modified_default_options["broker_type"] = "3"
        for option in exclude_options:
            modified_default_options.pop(option, None)

        return jsonify(
            {"default_options": modified_default_options, "status": "success"}
        )

    @app.route("/api/form_schema", methods=["GET"])
    def get_form_schema():
        """
        Endpoint that returns defaults and field definitions for a given component type.
        """
        component_type = request.args.get("type", "agent")

        if component_type == "agent":
            return jsonify(
                {
                    "status": "success",
                    "schema_type": "agent",
                    "defaults": AGENT_DEFAULTS,
                    "field_definitions": get_agent_field_definitions(),
                }
            )
        elif component_type == "gateway":
            return jsonify(
                {
                    "status": "success",
                    "schema_type": "gateway",
                    "defaults": GATEWAY_DEFAULTS,
                    "meta": {
                        "artifact_service_types": [
                            USE_DEFAULT_SHARED_ARTIFACT,
                            "memory",
                            "filesystem",
                            "gcs",
                        ],
                        "artifact_service_scopes": ["namespace", "app", "custom"],
                    },
                }
            )
        else:
            return (
                jsonify({"status": "error", "message": "Invalid component type"}),
                400,
            )

    @app.route("/api/available_tools", methods=["GET"])
    def get_available_tools():
        """
        Endpoint that returns a structured list of all available built-in tools and groups.
        """
        try:
            all_tools = tool_registry.get_all_tools()

            groups = defaultdict(lambda: {"description": "", "tools": []})
            tools_map = {}

            group_descriptions = {
                "artifact_management": "Creating, loading, and managing files and artifacts.",
                "data_analysis": "Querying, transforming, and visualizing data.",
                "general": "General purpose utilities like file conversion and diagram generation.",
                "web": "Interacting with web resources via HTTP requests.",
                "audio": "Generating and transcribing audio content.",
                "image": "Generating, describing, and editing images.",
                "test": "Tools for testing and development purposes.",
            }

            for tool in sorted(all_tools, key=lambda t: (t.category, t.name)):
                groups[tool.category]["tools"].append(tool.name)
                if not groups[tool.category]["description"]:
                    groups[tool.category]["description"] = group_descriptions.get(
                        tool.category,
                        f"Tools related to {tool.category.replace('_', ' ').title()}.",
                    )
                tools_map[tool.name] = {
                    "description": tool.description,
                    "category": tool.category,
                }

            return jsonify(
                {"status": "success", "groups": dict(groups), "tools": tools_map}
            )
        except Exception as e:
            app.logger.error(f"Error in get_available_tools: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/save_gateway_config", methods=["POST"])
    def save_gateway_config_route():
        """
        Accepts gateway configuration from frontend and passes it back to CLI via shared_config.
        """
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data received"}), 400

            gateway_name_input = data.get("gateway_name_input")
            config_options = data.get("config")

            if not gateway_name_input or not isinstance(config_options, dict):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Missing gateway_name_input or config data",
                        }
                    ),
                    400,
                )

            if "namespace" not in config_options:
                config_options["namespace"] = GATEWAY_DEFAULTS.get(
                    "namespace", "${NAMESPACE}"
                )

            if shared_config is not None:
                shared_config["status"] = "success_from_gui_save"
                shared_config["gateway_name_input"] = gateway_name_input
                shared_config["config"] = config_options

            return jsonify(
                {
                    "status": "success",
                    "message": "Gateway configuration data received by server. CLI will process.",
                }
            )

        except Exception as e:
            app.logger.error(f"Error in save_gateway_config_route: {e}", exc_info=True)
            if shared_config is not None:
                shared_config["status"] = "error_in_gui_save"
                shared_config["message"] = str(e)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/save_agent_config", methods=["POST"])
    def save_agent_config_route():
        """
        Accepts agent configuration from frontend and passes it back to CLI via shared_config.
        """
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data received"}), 400

            agent_name_input = data.get("agent_name_input")
            config_options = data.get("config")

            if not agent_name_input or not config_options:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Missing agent_name_input or config data",
                        }
                    ),
                    400,
                )

            str_list_keys_to_process = {
                "agent_card_default_input_modes_str": "agent_card_default_input_modes",
                "agent_card_default_output_modes_str": "agent_card_default_output_modes",
                "inter_agent_communication_allow_list_str": "inter_agent_communication_allow_list",
                "inter_agent_communication_deny_list_str": "inter_agent_communication_deny_list",
            }
            processed_options = config_options.copy()
            for key_str, original_key in str_list_keys_to_process.items():
                if key_str in processed_options and isinstance(
                    processed_options[key_str], str
                ):
                    processed_options[original_key] = [
                        s.strip()
                        for s in processed_options[key_str].split(",")
                        if s.strip()
                    ]
                elif original_key not in processed_options:
                    processed_options[original_key] = []

            if "agent_card_skills" in processed_options and isinstance(
                processed_options["agent_card_skills"], list
            ):
                if "agent_card_skills_str" in processed_options:
                    del processed_options["agent_card_skills_str"]
            elif "agent_card_skills_str" in processed_options and isinstance(
                processed_options["agent_card_skills_str"], str
            ):
                try:
                    import json

                    parsed_skills = json.loads(
                        processed_options["agent_card_skills_str"]
                    )
                    if isinstance(parsed_skills, list):
                        processed_options["agent_card_skills"] = parsed_skills
                    else:
                        app.logger.warn(
                            f"Parsed agent_card_skills_str was not a list: {parsed_skills}. Defaulting to empty list."
                        )
                        processed_options["agent_card_skills"] = []
                except json.JSONDecodeError:
                    app.logger.warn(
                        f"Could not parse agent_card_skills_str: {processed_options['agent_card_skills_str']}. Defaulting to empty list."
                    )
                    processed_options["agent_card_skills"] = []
            elif "agent_card_skills" not in processed_options:
                processed_options["agent_card_skills"] = []

            formatted_names = get_formatted_names(agent_name_input)
            processed_options["agent_name"] = formatted_names["PASCAL_CASE_NAME"]
            if shared_config is not None:
                shared_config["status"] = "success_from_gui_save"
                shared_config["agent_name_input"] = agent_name_input
                shared_config["config"] = processed_options
            return jsonify(
                {
                    "status": "success",
                    "message": "Agent configuration data received by server. CLI will process.",
                }
            )

        except Exception as e:
            app.logger.error(f"Error in save_agent_config_route: {e}", exc_info=True)
            if shared_config is not None:
                shared_config["status"] = "error_in_gui_save"
                shared_config["message"] = str(e)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/save_config", methods=["POST"])
    def save_config():
        try:
            received_data = request.json
            force = received_data.pop("force", False)

            if not received_data:
                return jsonify({"status": "error", "message": "No data received"}), 400

            complete_config = INIT_DEFAULT.copy()
            for key, value in received_data.items():
                if key in complete_config or key:
                    complete_config[key] = value

            if shared_config is not None:
                for key, value in complete_config.items():
                    shared_config[key] = value

            return jsonify({"status": "success"})

        except Exception as e:
            app.logger.error(f"Error in save_config: {e}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/test_llm_config", methods=["POST"])
    def test_llm_config():
        llm_config = request.json
        if (
            not llm_config.get("model")
            or not llm_config.get("api_key")
            or not llm_config.get("base_url")
        ):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Please provide all the required values",
                    }
                ),
                400,
            )
        try:
            response = litellm.completion(
                model=llm_config.get("model"),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                messages=[{"role": "user", "content": "Say OK"}],
            )
            message = response.get("choices")[0].get("message")
            if message is not None:
                return jsonify({"status": "success", "message": message.content}), 200
            else:
                raise ValueError("No response from LLM")
        except Exception:
            return jsonify({"status": "error", "message": "No response from LLM."}), 400

    @app.route("/api/runcontainer", methods=["POST"])
    def runcontainer():
        try:
            data = request.json or {}
            has_podman = shutil.which("podman") is not None
            has_docker = shutil.which("docker") is not None
            if not has_podman and not has_docker:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "You need to have either podman or docker installed.",
                        }
                    ),
                    400,
                )

            container_engine = data.get("container_engine")
            if not container_engine and has_podman and has_docker:
                container_engine = "podman"
            elif not container_engine:
                container_engine = "podman" if has_podman else "docker"

            if container_engine not in ["podman", "docker"]:
                return jsonify({"status": "error", "message": "Invalid engine."}), 400
            if container_engine == "podman" and not has_podman:
                return (
                    jsonify({"status": "error", "message": "Podman not installed."}),
                    400,
                )
            if container_engine == "docker" and not has_docker:
                return (
                    jsonify({"status": "error", "message": "Docker not installed."}),
                    400,
                )

            command = container_engine + CONTAINER_RUN_COMMAND
            response_status = os.system(command)

            if response_status != 0:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "The creation of a new container failed. You can try switching to dev mode or existing broker mode. You can also check this url to find possible solutions https://docs.solace.com/Software-Broker/Container-Tasks/rootless-containers.htm#rootful-versus-rootless-containers",
                        }
                    ),
                    500,
                )
            return jsonify(
                {
                    "status": "success",
                    "message": f"Started container via {container_engine}",
                    "container_engine": container_engine,
                }
            )
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        """Kills this Flask process immediately"""
        response = jsonify({"message": "Server shutting down...", "status": "success"})
        os._exit(0)
        return response

    frontend_static_dir = (
        Path(__file__).resolve().parent.parent / "frontend" / "static" / "client"
    )

    @app.route("/assets/<path:path>")
    def serve_assets(path):
        return send_from_directory(frontend_static_dir / "assets", path)

    @app.route("/static/client/<path:path>")
    def serve_client_files(path):
        return send_from_directory(frontend_static_dir, path)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_index(path):
        if os.path.splitext(path)[1] and os.path.exists(frontend_static_dir / path):
            return send_from_directory(frontend_static_dir, path)
        return send_file(frontend_static_dir / "index.html")

    return app


def run_flask(host="127.0.0.1", port=5002, shared_config=None):
    host = os.environ.get(config_portal_host, host)
    app = create_app(shared_config)
    app.logger.setLevel(logging.INFO)
    app.logger.info(f"Starting Flask app on {host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)
