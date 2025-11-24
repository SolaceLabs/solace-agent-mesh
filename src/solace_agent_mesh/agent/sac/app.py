import logging
import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from common.utils.asyncio_macos_fix import ensure_asyncio_compatibility
from .patch_adk import patch_adk

ensure_asyncio_compatibility()
patch_adk()

from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import Field, ValidationError, model_validator
from solace_ai_connector.flow.app import App

from ...common.a2a import (
    get_agent_request_topic,
    get_discovery_topic,
    get_agent_response_subscription_topic,
    get_agent_status_subscription_topic,
    get_sam_events_subscription_topic,
)
from ...common.constants import (
    DEFAULT_COMMUNICATION_TIMEOUT,
    TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY,
    TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH,
    HEALTH_CHECK_TTL_SECONDS,
    HEALTH_CHECK_INTERVAL_SECONDS,
)
from ...agent.sac.component import SamAgentComponent
from ...agent.utils.artifact_helpers import DEFAULT_SCHEMA_MAX_KEYS
from ...common.utils.pydantic_utils import SamConfigBase
from ..tools.tool_config_types import AnyToolConfig

log = logging.getLogger(__name__)

# Try to import TrustManagerConfig from enterprise repo
try:
    from solace_agent_mesh_enterprise.common.trust.config import TrustManagerConfig

except ImportError:
    # Enterprise features not available - create a placeholder type
    TrustManagerConfig = Dict[str, Any]  # type: ignore

info = {
    "class_name": "SamAgentApp",
    "description": "Custom App class for SAM Agent Host with namespace prefixing and automatic subscription generation.",
}


# --- Pydantic Models for Configuration Validation ---


class AgentCardConfig(SamConfigBase):
    """Configuration for the agent's self-description card."""

    description: str = Field(
        default="", description="Concise agent description for discovery."
    )
    defaultInputModes: List[str] = Field(
        default=["text"], description="Supported input content types."
    )
    defaultOutputModes: List[str] = Field(
        default=["text"], description="Supported output content types."
    )
    skills: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of advertised agent skills (A2A AgentSkill structure).",
    )
    documentationUrl: Optional[str] = Field(
        default=None, description="Optional URL for agent documentation."
    )
    provider: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional provider information (A2A AgentProvider structure).",
    )


class AgentCardPublishingConfig(SamConfigBase):
    """Configuration for publishing the agent card."""

    interval_seconds: int = Field(
        ..., description="Publish interval (seconds). <= 0 disables periodic publish."
    )


class AgentDiscoveryConfig(SamConfigBase):
    """Configuration for discovering other agents."""

    enabled: bool = Field(
        default=True, description="Enable discovery and instruction injection."
    )
    health_check_ttl_seconds: int = Field(
        default=HEALTH_CHECK_TTL_SECONDS,
        description="Time-to-live in seconds after which an unresponsive agent is de-registered.",
    )
    health_check_interval_seconds: int = Field(
        default=HEALTH_CHECK_INTERVAL_SECONDS,
        description="Interval in seconds between health checks.",
    )


class InterAgentCommunicationConfig(SamConfigBase):
    """Configuration for interacting with peer agents."""

    allow_list: List[str] = Field(
        default=["*"], description="Agent name patterns to allow delegation to."
    )
    deny_list: List[str] = Field(
        default_factory=list, description="Agent name patterns to deny delegation to."
    )
    request_timeout_seconds: int = Field(
        default=DEFAULT_COMMUNICATION_TIMEOUT,
        description="Timeout for peer requests (seconds).",
    )


class AgentInitCleanupConfig(SamConfigBase):
    """Configuration for custom agent initialization or cleanup functions."""

    module: str = Field(
        ...,
        description="Python module path for the function (e.g., 'my_plugin.initializers').",
    )
    name: str = Field(..., description="Name of the function within the module.")
    base_path: Optional[str] = Field(
        default=None,
        description="Optional base path for module resolution if not in PYTHONPATH.",
    )
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Configuration dictionary for the function."
    )


class DataToolsConfig(SamConfigBase):
    """Configuration for built-in data analysis tools."""

    sqlite_memory_threshold_mb: int = Field(
        default=100,
        description="Size threshold (MB) for using in-memory vs. temp file SQLite DB for CSV input.",
    )
    max_result_preview_rows: int = Field(
        default=50, description="Max rows to return in preview for SQL/JQ results."
    )
    max_result_preview_bytes: int = Field(
        default=4096,
        description="Max bytes to return in preview for SQL/JQ results (if row limit not hit first).",
    )


class ExtractContentConfig(SamConfigBase):
    """Configuration for the LLM-powered artifact extraction tool."""

    supported_binary_mime_types: List[str] = Field(
        default_factory=list,
        description="List of binary MIME type patterns (e.g., 'image/png', 'image/*', 'video/mp4') that the tool should attempt to process using its internal LLM.",
    )
    model: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Specifies the LLM for extraction. String (ADK LLMRegistry name) or dict (LiteLlm config). Defaults to agent's LLM.",
    )


class McpProcessingConfig(SamConfigBase):
    """Configuration for intelligent processing of MCP tool responses."""

    enable_intelligent_processing: bool = Field(
        default=True,
        description="Enable intelligent content-aware processing of MCP responses. When disabled, falls back to raw JSON saving.",
    )
    enable_text_format_detection: bool = Field(
        default=True,
        description="Enable detection and parsing of structured text formats (CSV, JSON, YAML) within text content.",
    )
    enable_content_parsing: bool = Field(
        default=True,
        description="Enable parsing and validation of detected content formats for enhanced metadata.",
    )
    fallback_to_raw_on_error: bool = Field(
        default=True,
        description="Fall back to raw JSON saving if intelligent processing fails.",
    )
    save_raw_alongside_intelligent: bool = Field(
        default=False,
        description="Save both intelligent artifacts and raw JSON response for debugging/comparison.",
    )
    max_content_items: int = Field(
        default=50,
        description="Maximum number of content items to process from a single MCP response.",
    )
    max_single_item_size_mb: int = Field(
        default=100,
        description="Maximum size in MB for a single content item before skipping intelligent processing.",
    )


class ArtifactServiceConfig(SamConfigBase):
    """Configuration for the ADK Artifact Service."""

    type: str = Field(
        ..., description="Service type (e.g., 'memory', 'gcs', 'filesystem')."
    )
    base_path: Optional[str] = Field(
        default=None,
        description="Base directory path (required for type 'filesystem').",
    )
    bucket_name: Optional[str] = Field(
        default=None, description="GCS bucket name (required for type 'gcs')."
    )
    artifact_scope: Literal["namespace", "app", "custom"] = Field(
        default="namespace", description="Process-wide scope for all artifact services."
    )
    artifact_scope_value: Optional[str] = Field(
        default=None,
        description="Custom identifier for artifact scope (required if artifact_scope is 'custom').",
    )

    @model_validator(mode="after")
    def check_artifact_scope(self) -> "ArtifactServiceConfig":
        if self.artifact_scope == "custom" and not self.artifact_scope_value:
            raise ValueError(
                "'artifact_scope_value' is required when 'artifact_scope' is 'custom'."
            )
        if self.artifact_scope != "custom" and self.artifact_scope_value:
            log.warning(
                "Configuration Warning: 'artifact_scope_value' is ignored when 'artifact_scope' is not 'custom'."
            )
        return self

class AgentIdentityConfig(SamConfigBase):
    """Configuration for agent identity and key management."""
    key_mode: Literal["auto", "manual"] = Field(
        default="auto",
        description="Key mode for agent identity: 'auto' for automatic generation, 'manual' for user-provided."
    )
    key_identity: Optional[str] = Field(
        default=None,
        description="Actual key value when key_mode is 'manual'."
    )
    key_persistence: Optional[str] = Field(
        default=None,
        description="Path to the key file, e.g. '/path/to/keys/agent_{name}.key'."
    )

    @model_validator(mode="after")
    def check_key_mode_and_identity(self) -> "AgentIdentityConfig":
        if self.key_mode == "manual" and not self.key_identity:
            raise ValueError(
                "'key_identity' is required when 'key_mode' is 'manual'."
            )
        if self.key_mode == "auto" and self.key_identity:
            log.warning(
                "Configuration Warning: 'key_identity' is ignored when 'key_mode' is 'auto'."
            )
        return self

class SessionServiceConfig(SamConfigBase):
    """Configuration for the ADK Session Service."""

    type: str = Field(
        ..., description="Service type (e.g., 'memory', 'sql', 'vertex_rag')."
    )
    default_behavior: Literal["PERSISTENT", "RUN_BASED"] = Field(
        default="PERSISTENT", description="Default behavior for session service."
    )
    database_url: Optional[str] = Field(
        default=None, description="Database URL for SQL session services."
    )


class CredentialServiceConfig(SamConfigBase):
    """Configuration for the ADK Credential Service."""

    type: str = Field(..., description="Service type (e.g., 'memory').")


class SamAgentAppConfig(SamConfigBase):
    """Pydantic model for the complete agent application configuration."""

    namespace: str = Field(
        ...,
        description="Absolute topic prefix for A2A communication (e.g., 'myorg/dev').",
    )
    agent_name: str = Field(..., description="Unique name for this ADK agent instance.")
    display_name: str = Field(
        default=None,
        description="Human-friendly display name for this ADK agent instance.",
    )
    deployment: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deployment tracking information for rolling updates and version control.",
    )
    model: Union[str, Dict[str, Any]] = Field(
        ..., description="ADK model name (string) or BaseLlm config dict."
    )
    agent_identity: Optional[AgentIdentityConfig] = Field(
        default_factory=lambda: AgentIdentityConfig(key_mode="auto"),
        description="Configuration for agent identity and key management."
    )
    trust_manager: Optional[Union[TrustManagerConfig, Dict[str, Any]]] = Field(
        default=None,
        description="Configuration for the Trust Manager (enterprise feature)",
    )
    instruction: Any = Field(
        default="",
        description="User-provided instructions for the ADK agent (string or invoke block).",
    )
    global_instruction: Any = Field(
        default="",
        description="User-provided global instructions for the agent tree (string or invoke block).",
    )
    tools: List[AnyToolConfig] = Field(
        default_factory=list,
        description="List of tool configurations (python, mcp, built-in). Each tool can have 'required_scopes'.",
    )
    supports_streaming: bool = Field(
        default=False,
        description="Whether this host supports A2A streaming (tasks/sendSubscribe).",
    )
    planner: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional configuration for an ADK planner."
    )
    code_executor: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional configuration for an ADK code executor."
    )
    inject_current_time: bool = Field(
        default=True,
        description="Whether to inject the current time into the agent's instruction.",
    )
    session_service: SessionServiceConfig = Field(
        default_factory=lambda: SessionServiceConfig(type="memory"),
        description="Configuration for ADK Session Service.",
    )
    artifact_service: ArtifactServiceConfig = Field(
        default_factory=lambda: ArtifactServiceConfig(type="memory"),
        description="Configuration for ADK Artifact Service.",
    )
    memory_service: Dict[str, Any] = Field(
        default={"type": "memory"},
        description="Configuration for ADK Memory Service (defaults to memory).",
    )
    credential_service: Optional[CredentialServiceConfig] = Field(
        default=None,
        description="Configuration for ADK Credential Service (optional).",
    )
    multi_session_request_response: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True},
        description="Enables multi-session request/response capabilities for the agent, required for peer delegation.",
    )
    tool_output_save_threshold_bytes: int = Field(
        default=2048,
        description="If any tool's processed output exceeds this size (bytes), its full content is saved as a new ADK artifact.",
    )
    tool_output_llm_return_max_bytes: int = Field(
        default=4096,
        description="Maximum size (bytes) of any tool's output content returned directly to the LLM.",
    )
    mcp_tool_response_save_threshold_bytes: int = Field(
        default=2048,
        description="Threshold in bytes above which MCP tool responses are saved as artifacts.",
    )
    mcp_tool_llm_return_max_bytes: int = Field(
        default=4096,
        description="Maximum size in bytes of MCP tool response content returned directly to the LLM.",
    )
    artifact_handling_mode: Literal["ignore", "embed", "reference"] = Field(
        default="ignore",
        description="How to represent created artifacts in A2A messages.",
    )
    schema_max_keys: int = Field(
        default=DEFAULT_SCHEMA_MAX_KEYS,
        ge=0,
        description="Maximum number of dictionary keys to inspect during schema inference.",
    )
    enable_embed_resolution: bool = Field(
        default=True,
        description="Enable early-stage processing of dynamic embeds and inject related instructions.",
    )
    enable_auto_continuation: bool = Field(
        default=True,
        description="If true, automatically attempts to continue LLM generation if it is interrupted by a token limit.",
    )
    stream_batching_threshold_bytes: int = Field(
        default=0,
        description="Minimum size in bytes for accumulated text from LLM stream before sending a status update.",
    )
    max_message_size_bytes: int = Field(
        default=10_000_000,
        description="Maximum allowed message size in bytes before rejecting publication.",
    )
    enable_artifact_content_instruction: bool = Field(
        default=True,
        description="Inject instructions about the 'artifact_content' embed type.",
    )
    agent_card: AgentCardConfig = Field(
        ..., description="Static definition of this agent's capabilities for discovery."
    )
    agent_card_publishing: AgentCardPublishingConfig = Field(
        ..., description="Settings for publishing the agent card."
    )
    agent_discovery: AgentDiscoveryConfig = Field(
        default_factory=AgentDiscoveryConfig,
        description="Settings for discovering other agents and injecting related instructions.",
    )
    inter_agent_communication: InterAgentCommunicationConfig = Field(
        default_factory=InterAgentCommunicationConfig,
        description="Configuration for interacting with peer agents.",
    )
    inject_system_purpose: bool = Field(
        default=False,
        description="If true, injects the system_purpose received from the gateway into the agent's prompt.",
    )
    inject_response_format: bool = Field(
        default=False,
        description="If true, injects the response_format received from the gateway into the agent's prompt.",
    )
    inject_user_profile: bool = Field(
        default=False,
        description="If true, injects the user_profile received from the gateway into the agent's prompt.",
    )
    agent_init_function: Optional[AgentInitCleanupConfig] = Field(
        default=None,
        description="Configuration for the agent's custom initialization function.",
    )
    agent_cleanup_function: Optional[AgentInitCleanupConfig] = Field(
        default=None,
        description="Configuration for the agent's custom cleanup function.",
    )
    text_artifact_content_max_length: int = Field(
        default=TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH,
        ge=100,
        le=TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY,
        description="Maximum character length for text-based artifact content.",
    )
    max_llm_calls_per_task: int = Field(
        default=20,
        description="Maximum number of LLM calls allowed for a single A2A task.",
    )
    data_tools_config: DataToolsConfig = Field(
        default_factory=DataToolsConfig,
        description="Runtime configuration parameters for built-in data analysis tools.",
    )
    extract_content_from_artifact_config: ExtractContentConfig = Field(
        default_factory=ExtractContentConfig,
        description="Configuration for the LLM-powered artifact extraction tool.",
    )
    mcp_intelligent_processing: McpProcessingConfig = Field(
        default_factory=McpProcessingConfig,
        description="Configuration for intelligent processing of MCP tool responses.",
    )


class SamAgentApp(App):
    """
    Custom App class for SAM Agent Host that automatically generates
    the required Solace subscriptions based on namespace and agent name,
    and programmatically defines the single SamAgentComponent instance.
    It also defines the expected configuration structure via `app_schema`.
    """

    # The app_schema dictionary is now redundant for validation but can be kept for documentation
    # or for frameworks that might inspect it. For now, we will remove it.
    app_schema = {}

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log.debug("Initializing A2A_ADK_App...")

        app_config_dict = app_info.get("app_config", {})

        try:
            # Validate the raw dict, cleaning None values to allow defaults to apply
            app_config = SamAgentAppConfig.model_validate_and_clean(app_config_dict)
            # Overwrite the raw dict with the validated object for downstream use
            app_info["app_config"] = app_config
        except ValidationError as e:
            message = SamAgentAppConfig.format_validation_error_message(e, app_info['name'], app_config_dict.get('agent_name'))
            log.error("Invalid Agent configuration:\n%s", message)
            raise

        # The rest of the method can now safely use .get() on the app_config object,
        # ensuring full backward compatibility.
        namespace = app_config.get("namespace")
        agent_name = app_config.get("agent_name")
        broker_request_response = app_info.get("broker_request_response")

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
            get_sam_events_subscription_topic(namespace, "session"),
        ]

        # Add trust card subscription if trust manager is enabled
        trust_config = app_config.get("trust_manager")
        if trust_config and trust_config.get("enabled", False):
            from ...common.a2a.protocol import get_trust_card_subscription_topic

            trust_card_topic = get_trust_card_subscription_topic(namespace)
            required_topics.append(trust_card_topic)
            log.info(
                "Trust Manager enabled for agent '%s', added trust card subscription: %s",
                agent_name,
                trust_card_topic,
            )

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

        broker_config["temporary_queue"] = app_info.get("broker", {}).get(
            "temporary_queue", True
        )
        log.debug(
            "Set broker_config.temporary_queue = %s", broker_config["temporary_queue"]
        )

        super().__init__(app_info, **kwargs)
        log.debug("%s Agent initialization complete.", agent_name)

    def run(self):
        """
        Override run to ensure component initialization failures cause application failure.

        This is critical for containerized deployments where the process must exit with
        a non-zero code if initialization fails. By re-raising the exception, we allow
        the SAC framework's main() to handle cleanup (component.cleanup(), broker
        disconnection, etc.) before exiting with code 1.
        """
        try:
            super().run()
        except Exception as e:
            log.critical(
                "Failed to start agent application '%s': %s",
                self.name,
                e,
                exc_info=e
            )
            raise

    def get_component(self, component_name: str = None) -> "SamAgentComponent":
        """
        Retrieves the running SamAgentComponent instance from the app's flow.
        
        Args:
            component_name: Optional component name (for compatibility, but ignored since there's only one component)
            
        Returns:
            The SamAgentComponent instance or None if not found
        """
        if self.flows and self.flows[0].component_groups:
            for group in self.flows[0].component_groups:
                for component_wrapper in group:
                    component = (
                        component_wrapper.component
                        if hasattr(component_wrapper, "component")
                        else component_wrapper
                    )
                    if isinstance(component, SamAgentComponent):
                        return component
        return None
