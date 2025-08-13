import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from common.utils.asyncio_macos_fix import ensure_asyncio_compatibility
from .patch_adk import patch_adk
from solace_ai_connector.common.log import log

ensure_asyncio_compatibility()
patch_adk()

from typing import Any, Dict
from solace_ai_connector.flow.app import App
from solace_ai_connector.common.log import log

from ...common.a2a_protocol import (
    get_agent_request_topic,
    get_discovery_topic,
    get_agent_response_subscription_topic,
    get_agent_status_subscription_topic,
)
from ...common.constants import DEFAULT_COMMUNICATION_TIMEOUT
from ...agent.sac.component import SamAgentComponent
from ...agent.utils.artifact_helpers import DEFAULT_SCHEMA_MAX_KEYS

info = {
    "class_name": "SamAgentApp",
    "description": "Custom App class for SAM Agent Host with namespace prefixing and automatic subscription generation.",
}


class SamAgentApp(App):
    """
    Custom App class for SAM Agent Host that automatically generates
    the required Solace subscriptions based on namespace and agent name,
    and programmatically defines the single SamAgentComponent instance.
    It also defines the expected configuration structure via `app_schema`.
    """

    app_schema = {
        "config_parameters": [
            # --- A2A Config (Flattened) ---
            {
                "name": "namespace",
                "required": True,
                "type": "string",
                "description": "Absolute topic prefix for A2A communication (e.g., 'myorg/dev').",
            },
            {
                "name": "supports_streaming",
                "required": False,
                "type": "boolean",
                "default": False,
                "description": "Whether this host supports A2A streaming (tasks/sendSubscribe).",
            },
            # --- Core ADK Agent Definition ---
            {
                "name": "agent_name",
                "required": True,
                "type": "string",
                "description": "Unique name for this ADK agent instance.",
            },
            {
                "name": "model",
                "required": True,
                "type": "any",
                "description": "ADK model name (string) or BaseLlm config dict.",
            },
            {
                "name": "instruction",
                "required": False,
                "type": "any",
                "default": "",
                "description": "User-provided instructions for the ADK agent (string or invoke block).",
            },
            {
                "name": "global_instruction",
                "required": False,
                "type": "any",
                "default": "",
                "description": "User-provided global instructions for the agent tree (string or invoke block).",
            },
            {
                "name": "tools",
                "required": False,
                "type": "list",
                "default": [],
                "description": "List of tool configurations (python, mcp, built-in). Each tool can have 'required_scopes'.",
                "items": {  # Schema for each item in the tools list
                    "type": "object",
                    "properties": {
                        "tool_type": {
                            "type": "string",
                            "required": True,
                            "enum": ["python", "mcp", "builtin", "builtin-group"],
                            "description": "Type of the tool.",
                        },
                        "tool_name": {
                            "type": "string",
                            "required": False,  # Required for mcp/builtin, optional for python
                            "description": "Name of the tool (e.g., ADK built-in name, specific MCP tool name). Overwrite function_name for python tools.",
                        },
                        "tool_description": {
                            "type": "string",
                            "required": False,  # Optional, Only for python
                            "description": "Description of the tool to overwrite for python tools. Overwrite the python function description",
                        },
                        "component_module": {  # For python tools
                            "type": "string",
                            "required": False,
                            "description": "Python module for 'python' tool type.",
                        },
                        "function_name": {  # For python tools
                            "type": "string",
                            "required": False,
                            "description": "Function name within the module for 'python' tool type.",
                        },
                        "component_base_path": {  # For python tools
                            "type": "string",
                            "required": False,
                            "description": "Base path for 'python' tool module resolution.",
                        },
                        "connection_params": {  # For mcp tools
                            "type": "object",
                            "required": False,
                            "description": "Connection parameters for 'mcp' tool type.",
                        },
                        "environment_variables": {  # For mcp tools (stdio)
                            "type": "object",
                            "required": False,
                            "description": "Environment variables for 'mcp' tool type with stdio connection.",
                        },
                        "required_scopes": {
                            "type": "list",
                            "required": False,
                            "default": [],
                            "description": "List of scope strings required to use this specific tool.",
                            "items": {"type": "string"},
                        },
                        "tool_config": {
                            "type": "object",
                            "required": False,
                            "default": {},
                            "description": "A dictionary holding specific configuration for this tool instance (e.g., API keys, model names for an image generation tool).",
                            "additionalProperties": True,
                        },
                    },
                },
            },
            {
                "name": "data_tools_config",
                "required": False,
                "type": "object",
                "default": {},
                "description": "Runtime configuration parameters for built-in data analysis tools.",
                "properties": {
                    "sqlite_memory_threshold_mb": {
                        "type": "integer",
                        "required": False,
                        "default": 100,
                        "description": "Size threshold (MB) for using in-memory vs. temp file SQLite DB for CSV input.",
                    },
                    "max_result_preview_rows": {
                        "type": "integer",
                        "required": False,
                        "default": 50,
                        "description": "Max rows to return in preview for SQL/JQ results.",
                    },
                    "max_result_preview_bytes": {
                        "type": "integer",
                        "required": False,
                        "default": 4096,
                        "description": "Max bytes to return in preview for SQL/JQ results (if row limit not hit first).",
                    },
                },
            },
            {
                "name": "planner",
                "required": False,
                "type": "object",
                "default": None,
                "description": "Optional configuration for an ADK planner.",
            },
            {
                "name": "code_executor",
                "required": False,
                "type": "object",
                "default": None,
                "description": "Optional configuration for an ADK code executor.",
            },
            {
                "name": "inject_current_time",
                "required": False,
                "type": "boolean",
                "default": True,
                "description": "Whether to inject the current time into the agent's instruction.",
            },
            # --- ADK Services Configuration ---
            {
                "name": "session_service",
                "required": True,
                "type": "object",
                "description": "Configuration for ADK Session Service (e.g., { type: 'memory' }).",
                "default": {"type": "memory", "default_behavior": "PERSISTENT"},
                "properties": {
                    "type": {
                        "type": "string",
                        "required": True,
                        "description": "Service type (e.g., 'memory', 'vertex_rag').",
                    },
                    "default_behavior": {
                        "type": "string",
                        "required": False,
                        "default": "PERSISTENT",
                        "enum": ["PERSISTENT", "RUN_BASED"],
                        "description": "Default behavior for session service: 'PERSISTENT' (default) or 'RUN_BASED' for how long to keep the session history.",
                    },
                },
            },
            {
                "name": "artifact_service",
                "required": False,
                "type": "object",
                "default": {"type": "memory"},
                "description": "Configuration for ADK Artifact Service (defaults to memory).",
                "properties": {
                    "type": {
                        "type": "string",
                        "required": True,
                        "description": "Service type (e.g., 'memory', 'gcs', 'filesystem').",
                    },
                    "base_path": {
                        "type": "string",
                        "required": False,  # Required only if type is filesystem
                        "description": "Base directory path (required for type 'filesystem').",
                    },
                    "bucket_name": {
                        "type": "string",
                        "required": False,  # Required only if type is gcs
                        "description": "GCS bucket name (required for type 'gcs').",
                    },
                    "artifact_scope": {
                        "type": "string",
                        "required": False,
                        "default": "namespace",
                        "enum": ["namespace", "app"],
                        "description": "Process-wide scope for all artifact services. 'namespace' (default): shared by all components in the namespace. 'app': isolated by agent/gateway name. This setting must be consistent for all components in the same process.",
                    },
                    "artifact_scope_value": {
                        "type": "string",
                        "required": False,
                        "default": None,
                        "description": "Custom identifier for artifact scope (required if artifact_scope is 'custom').",
                    },
                },
            },
            {
                "name": "memory_service",
                "required": False,
                "type": "object",
                "default": {"type": "memory"},
                "description": "Configuration for ADK Memory Service (defaults to memory).",
            },
            # --- Tool Output Handling (Generalized) ---
            {
                "name": "tool_output_save_threshold_bytes",
                "required": False,
                "type": "integer",
                "default": 2048,  # 2KB
                "description": "If any tool's processed output (e.g., extracted content from an artifact, MCP response) exceeds this size (bytes), its full content is saved as a new ADK artifact. This threshold should generally be less than or equal to tool_output_llm_return_max_bytes.",
            },
            {
                "name": "tool_output_llm_return_max_bytes",
                "required": False,
                "type": "integer",
                "default": 4096,  # 4KB
                "description": "Maximum size (bytes) of any tool's (potentially summarized or original) output content returned directly to the LLM. If exceeded, the content will be truncated, and the full original output will be saved as an artifact if not already.",
            },
            # --- LLM-Powered Artifact Extraction Tool Config ---
            {
                "name": "extract_content_from_artifact_config",
                "required": False,
                "type": "object",
                "default": {},
                "description": "Configuration for the LLM-powered artifact extraction tool.",
                "properties": {
                    "supported_binary_mime_types": {
                        "type": "list",
                        "required": False,
                        "default": [],
                        "items": {"type": "string"},
                        "description": "List of binary MIME type patterns (e.g., 'image/png', 'image/*', 'video/mp4') that the tool should attempt to process using its internal LLM.",
                    },
                    "model": {
                        "type": "any",  # Union[str, Dict[str, Any]]
                        "required": False,
                        "default": None,
                        "description": "Specifies the LLM for extraction. String (ADK LLMRegistry name) or dict (LiteLlm config). Defaults to agent's LLM.",
                    },
                },
            },
            # --- Artifact Handling ---
            {
                "name": "artifact_handling_mode",
                "required": False,
                "type": "string",
                "default": "ignore",
                "description": "How to represent created artifacts in A2A messages: 'ignore' (default), 'embed' (include base64 data), 'reference' (include fetch URI).",
            },
            # --- Schema Inference Config ---
            {
                "name": "schema_max_keys",
                "required": False,
                "type": "integer",
                "default": DEFAULT_SCHEMA_MAX_KEYS,
                "description": "Maximum number of dictionary keys to inspect during schema inference.",
            },
            # --- Embed Resolution Config ---
            {
                "name": "enable_embed_resolution",
                "required": False,
                "type": "boolean",
                "default": True,
                "description": "Enable early-stage processing (state, math, etc.) of dynamic embeds and inject related instructions.",
            },
            {
                "name": "enable_auto_continuation",
                "required": False,
                "type": "boolean",
                "default": True,
                "description": "If true, automatically attempts to continue LLM generation if it is interrupted by a token limit.",
            },
            {
                "name": "stream_batching_threshold_bytes",
                "required": False,
                "type": "integer",
                "default": 0,
                "description": "Minimum size in bytes for accumulated text from LLM stream before sending a status update. If 0 or less, batching is disabled and updates are sent per chunk. Final LLM chunks are always sent regardless of this threshold.",
            },
            {
                "name": "max_message_size_bytes",
                "required": False,
                "type": "integer",
                "default": 10_000_000,
                "description": "Maximum allowed message size in bytes before rejecting publication to prevent broker disconnections. Default: 10MB",
            },
            {
                "name": "enable_artifact_content_instruction",
                "required": False,
                "type": "boolean",
                "default": True,
                "description": "Inject instructions about the 'artifact_content' embed type (resolved late-stage, typically by a gateway).",
            },
            # --- Agent Card Definition (Simplified) ---
            {
                "name": "agent_card",
                "required": True,
                "type": "object",
                "description": "Static definition of this agent's capabilities for discovery.",
                "properties": {
                    "description": {
                        "type": "string",
                        "required": False,
                        "default": "",
                        "description": "Concise agent description for discovery.",
                    },
                    "defaultInputModes": {
                        "type": "list",
                        "required": False,
                        "default": ["text"],
                        "description": "Supported input content types.",
                    },
                    "defaultOutputModes": {
                        "type": "list",
                        "required": False,
                        "default": ["text"],
                        "description": "Supported output content types.",
                    },
                    "skills": {
                        "type": "list",
                        "required": False,
                        "default": [],
                        "description": "List of advertised agent skills (A2A AgentSkill structure).",
                    },
                    "documentationUrl": {
                        "type": "string",
                        "required": False,
                        "default": None,
                        "description": "Optional URL for agent documentation.",
                    },
                    "provider": {
                        "type": "object",
                        "required": False,
                        "default": None,
                        "description": "Optional provider information (A2A AgentProvider structure).",
                        "properties": {
                            "organization": {"type": "string", "required": True},
                            "url": {"type": "string", "required": False},
                        },
                    },
                },
            },
            # --- Agent Discovery & Communication ---
            {
                "name": "agent_card_publishing",
                "required": True,
                "type": "object",
                "description": "Settings for publishing the agent card.",
                "properties": {
                    "interval_seconds": {
                        "type": "integer",
                        "required": True,
                        "description": "Publish interval (seconds). <= 0 disables periodic publish.",
                    }
                },
            },
            {
                "name": "agent_discovery",
                "required": True,
                "type": "object",
                "description": "Settings for discovering other agents and injecting related instructions.",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "required": False,
                        "default": True,
                        "description": "Enable discovery and instruction injection.",
                    }
                },
            },
            {
                "name": "inter_agent_communication",
                "required": True,
                "type": "object",
                "description": "Configuration for interacting with peer agents.",
                "properties": {
                    "allow_list": {
                        "type": "list",
                        "required": False,
                        "default": ["*"],
                        "description": "Agent name patterns to allow delegation to.",
                    },
                    "deny_list": {
                        "type": "list",
                        "required": False,
                        "default": [],
                        "description": "Agent name patterns to deny delegation to.",
                    },
                    "request_timeout_seconds": {
                        "type": "integer",
                        "required": False,
                        "default": DEFAULT_COMMUNICATION_TIMEOUT,
                        "description": "Timeout for peer requests (seconds).",
                    },
                },
            },
            {
                "name": "inject_system_purpose",
                "required": False,
                "type": "boolean",
                "default": False,
                "description": "If true, injects the system_purpose received from the gateway (via task metadata) into the agent's prompt.",
            },
            {
                "name": "inject_response_format",
                "required": False,
                "type": "boolean",
                "default": False,
                "description": "If true, injects the response_format received from the gateway (via task metadata) into the agent's prompt.",
            },
            {
                "name": "inject_user_profile",
                "required": False,
                "type": "boolean",
                "default": False,
                "description": "If true, injects the user_profile received from the gateway (via task metadata) into the agent's prompt.",
            },
            # --- Configurable Agent Initialization ---
            {
                "name": "agent_init_function",
                "required": False,
                "type": "object",
                "description": "Configuration for the agent's custom initialization function.",
                "properties": {
                    "module": {
                        "type": "string",
                        "required": True,
                        "description": "Python module path for the init function (e.g., 'my_plugin.initializers').",
                    },
                    "name": {
                        "type": "string",
                        "required": True,
                        "description": "Name of the init function within the module.",
                    },
                    "base_path": {
                        "type": "string",
                        "required": False,
                        "description": "Optional base path for module resolution if not in PYTHONPATH.",
                    },
                    "config": {
                        "type": "object",
                        "required": False,
                        "default": {},
                        "additionalProperties": True,
                        "description": "Configuration dictionary for the init function, validated by its Pydantic model.",
                    },
                },
            },
            # --- Configurable Agent Cleanup ---
            {
                "name": "agent_cleanup_function",
                "required": False,
                "type": "object",
                "description": "Configuration for the agent's custom cleanup function.",
                "properties": {
                    "module": {
                        "type": "string",
                        "required": True,
                        "description": "Python module path for the cleanup function.",
                    },
                    "name": {
                        "type": "string",
                        "required": True,
                        "description": "Name of the cleanup function within the module.",
                    },
                    "base_path": {
                        "type": "string",
                        "required": False,
                        "description": "Optional base path for module resolution.",
                    },
                },
            },
            {
                "name": "text_artifact_content_max_length",
                "required": False,
                "type": "integer",
                "default": 1000,
                "minimum": 100,
                "maximum": 100000,
                "description": "Maximum character length for text-based artifact content (100-100000 characters). Binary artifacts are unaffected.",
            },
            {
                "name": "max_llm_calls_per_task",
                "required": False,
                "type": "integer",
                "default": 20,
                "description": "Maximum number of LLM calls allowed for a single A2A task. A value of 0 or less means unlimited.",
            },
        ]
    }

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log.debug("Initializing A2A_ADK_App...")

        app_config = app_info.get("app_config", {})
        namespace = app_config.get("namespace")
        agent_name = app_config.get("agent_name")
        broker_request_response = app_info.get("broker_request_response")

        if not namespace or not isinstance(namespace, str):
            raise ValueError(
                "Internal Error: Namespace missing or invalid after validation."
            )
        if not agent_name or not isinstance(agent_name, str):
            raise ValueError(
                "Internal Error: Agent name missing or invalid after validation."
            )

        artifact_mode = app_config.get("artifact_handling_mode", "ignore").lower()
        if artifact_mode not in ["ignore", "embed", "reference"]:
            log.warning(
                "Invalid 'artifact_handling_mode' value '%s' in app_config. Using 'ignore'. Allowed values: 'ignore', 'embed', 'reference'.",
                artifact_mode,
            )
            app_config["artifact_handling_mode"] = "ignore"

        schema_max_keys = app_config.get("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
        if not isinstance(schema_max_keys, int) or schema_max_keys < 0:
            log.warning(
                "Invalid 'schema_max_keys' value '%s' in app_config. Using default: %d.",
                schema_max_keys,
                DEFAULT_SCHEMA_MAX_KEYS,
            )
            app_config["schema_max_keys"] = DEFAULT_SCHEMA_MAX_KEYS

        artifact_service_config = app_config.get("artifact_service", {})
        if artifact_service_config.get("type") == "filesystem":
            artifact_scope = artifact_service_config.get("artifact_scope", "namespace")
            if artifact_scope == "custom" and not artifact_service_config.get(
                "artifact_scope_value"
            ):
                raise ValueError(
                    "Configuration Error: 'artifact_scope_value' is required when 'artifact_scope' is 'custom'."
                )
            if artifact_scope != "custom" and artifact_service_config.get(
                "artifact_scope_value"
            ):
                log.warning(
                    "Configuration Warning: 'artifact_scope_value' is ignored when 'artifact_scope' is not 'custom'."
                )

        log.info(
            "Configuring A2A_ADK_App for Agent: '%s' in Namespace: '%s'",
            agent_name,
            namespace,
        )

        required_topics = [
            get_agent_request_topic(namespace, agent_name),
            get_discovery_topic(namespace),
            get_agent_response_subscription_topic(namespace, agent_name),
            get_agent_status_subscription_topic(namespace, agent_name),
        ]
        generated_subs = [{"topic": topic} for topic in required_topics]
        log.info(
            "Automatically generated subscriptions for Agent '%s': %s",
            agent_name,
            generated_subs,
        )

        component_definition = {
            "name": f"{agent_name}_host",
            "component_class": SamAgentComponent,
            "component_config": {},
            "subscriptions": generated_subs,
        }
        if broker_request_response:
            component_definition["broker_request_response"] = broker_request_response

        app_info["components"] = [component_definition]
        log.debug("Replaced 'components' in app_info with programmatic definition.")

        broker_config = app_info.setdefault("broker", {})

        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True
        log.debug("Injected broker.input_enabled=True and broker.output_enabled=True")

        generated_queue_name = f"{namespace.strip('/')}/q/a2a/{agent_name}"
        broker_config["queue_name"] = generated_queue_name
        log.debug("Injected generated broker.queue_name: %s", generated_queue_name)

        broker_config["temporary_queue"] = True
        log.debug("Set broker_config.temporary_queue = True")

        super().__init__(app_info, **kwargs)
        log.debug("A2A_ADK_App initialization complete.")
