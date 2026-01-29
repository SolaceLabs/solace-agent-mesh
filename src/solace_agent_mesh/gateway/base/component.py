"""
Base Component class for Gateway implementations in the Solace AI Connector.
"""

import logging
import asyncio
import base64
import queue
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple, Union

from google.adk.artifacts import BaseArtifactService

from ...common.agent_registry import AgentRegistry
from ...common.gateway_registry import GatewayRegistry
from ...common.sac.sam_component_base import SamComponentBase
from ...core_a2a.service import CoreA2AService
from ...agent.adk.services import initialize_artifact_service
from ...common.services.identity_service import (
    BaseIdentityService,
    create_identity_service,
)
from .task_context import TaskContextManager
from .auth_interface import AuthHandler
from ...common.a2a.types import ContentPart
from ...common.utils.rbac_utils import validate_agent_access
from a2a.types import (
    Message as A2AMessage,
    AgentCard,
    JSONRPCResponse,
    Task,
    TaskState,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    TextPart,
    DataPart,
    FilePart,
    FileWithBytes,
    Artifact as A2AArtifact,
)
from ...common import a2a
from ...common.a2a.utils import is_gateway_card
from ...common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    LATE_EMBED_TYPES,
    EARLY_EMBED_TYPES,
    resolve_embeds_recursively_in_string,
)
from ...common.utils.embeds.types import ResolutionMode
from ...agent.utils.artifact_helpers import (
    load_artifact_content_or_metadata,
    format_artifact_uri,
)
from ...common.utils.mime_helpers import is_text_based_mime_type
from solace_ai_connector.common.message import (
    Message as SolaceMessage,
)
from solace_ai_connector.common.event import Event, EventType
from abc import abstractmethod

from ...common.middleware.registry import MiddlewareRegistry

log = logging.getLogger(__name__)

info = {
    "class_name": "BaseGatewayComponent",
    "description": (
        "Abstract base component for A2A gateways. Handles common service "
        "initialization and provides a framework for platform-specific logic. "
        "Configuration is typically derived from the parent BaseGatewayApp's app_config."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "description": "Not typically used directly; component reacts to events from its input queue.",
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used directly; component sends data to external systems.",
    },
}


class BaseGatewayComponent(SamComponentBase):
    """
    Abstract base class for Gateway components.

    Initializes shared services and manages the core lifecycle for processing
    A2A messages and interacting with an external communication platform.
    """

    _RESOLVE_EMBEDS_IN_FINAL_RESPONSE = False

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Overrides the default get_config to first look inside the nested
        'app_config' dictionary that BaseGatewayApp places in the component_config.
        This is the primary way gateway components should access their configuration.
        """
        if "app_config" in self.component_config:
            value = self.component_config["app_config"].get(key)
            if value is not None:
                return value

        return super().get_config(key, default)

    def __init__(
        self,
        resolve_artifact_uris_in_gateway: bool = True,
        supports_inline_artifact_resolution: bool = False,
        filter_tool_data_parts: bool = True,
        **kwargs: Any
    ):
        """
        Initialize the BaseGatewayComponent.

        Args:
            resolve_artifact_uris_in_gateway: If True, resolves artifact URIs before sending to external.
            supports_inline_artifact_resolution: If True, SIGNAL_ARTIFACT_RETURN embeds are converted
                to FileParts during embed resolution. If False (default), signals are passed through
                for the gateway to handle manually. Use False for legacy gateways (e.g., Slack),
                True for modern gateways that support inline artifact rendering (e.g., HTTP SSE).
            filter_tool_data_parts: If True (default), filters out tool-related DataParts (tool_call,
                tool_result, etc.) from final Task messages before sending to gateway. Use True for
                gateways that don't want to display internal tool execution details (e.g., Slack),
                False for gateways that display all parts (e.g., HTTP SSE Web UI).
            **kwargs: Additional arguments passed to parent class.
        """
        super().__init__(info, **kwargs)
        self.resolve_artifact_uris_in_gateway = resolve_artifact_uris_in_gateway
        self.supports_inline_artifact_resolution = supports_inline_artifact_resolution
        self.filter_tool_data_parts = filter_tool_data_parts
        log.info("%s Initializing Base Gateway Component...", self.log_identifier)

        try:
            # Note: self.namespace and self.max_message_size_bytes are initialized in SamComponentBase
            self.gateway_id: str = self.get_config("gateway_id")
            if not self.gateway_id:
                raise ValueError("Gateway ID must be configured in the app_config.")

            self.enable_embed_resolution: bool = self.get_config(
                "enable_embed_resolution", True
            )
            self.gateway_max_artifact_resolve_size_bytes: int = self.get_config(
                "gateway_max_artifact_resolve_size_bytes"
            )
            self.gateway_recursive_embed_depth: int = self.get_config(
                "gateway_recursive_embed_depth"
            )
            self.artifact_handling_mode: str = self.get_config(
                "artifact_handling_mode", "embed"
            )
            _ = self.get_config("artifact_service")

            log.info(
                "%s Retrieved common configs: Namespace=%s, GatewayID=%s",
                self.log_identifier,
                self.namespace,
                self.gateway_id,
            )

        except Exception as e:
            log.error(
                "%s Failed to retrieve essential configuration: %s",
                self.log_identifier,
                e,
            )
            raise ValueError(f"Configuration retrieval error: {e}") from e

        self.agent_registry: AgentRegistry = AgentRegistry()
        self.gateway_registry: GatewayRegistry = GatewayRegistry()
        self.core_a2a_service: CoreA2AService = CoreA2AService(
            agent_registry=self.agent_registry,
            namespace=self.namespace,
            component_id="WebUI"
        )
        self.shared_artifact_service: Optional[BaseArtifactService] = (
            initialize_artifact_service(self)
        )

        self.task_context_manager: TaskContextManager = TaskContextManager()
        self.internal_event_queue: queue.Queue = queue.Queue()

        identity_service_config = self.get_config("identity_service")
        self.identity_service: Optional[BaseIdentityService] = create_identity_service(
            identity_service_config, self
        )

        self._config_resolver = MiddlewareRegistry.get_config_resolver()
        log.info(
            "%s Middleware system initialized (using default configuration resolver).",
            self.log_identifier,
        )

        self._gateway_card_publishing_config = self.get_config(
            "gateway_card_publishing",
            {"enabled": True, "interval_seconds": 30}
        )
        self._gateway_card_config = self.get_config("gateway_card", {})
        self._gateway_card_timer_id = f"publish_gateway_card_{self.gateway_id}"

        # Authentication handler (optional, enterprise feature)
        self.auth_handler: Optional[AuthHandler] = None

        # Setup authentication if enabled (subclasses override _setup_auth)
        self._setup_auth()

        log.info(
            "%s Initialized Base Gateway Component.", self.log_identifier
        )

    def _setup_auth(self) -> None:
        """
        Setup authentication handler if enabled.

        This method is called during initialization and can be overridden
        by subclasses to customize auth setup. The default implementation
        does nothing - subclasses should override to enable auth.

        Example override in subclass:
            def _setup_auth(self):
                if self.get_config('enable_auth', False):
                    from enterprise.auth import SAMOAuth2Handler
                    self.auth_handler = SAMOAuth2Handler(self.config)
        """
        # Base implementation: no auth
        # Subclasses (like GenericGateway) override to enable auth
        pass

    async def _inject_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Inject authentication headers if authenticated.

        This helper method should be called before making outgoing HTTP requests
        to add authentication headers (e.g., Bearer tokens) to the request.

        Args:
            headers: Existing headers dictionary

        Returns:
            Headers dictionary with auth headers added (if authenticated)

        Example:
            headers = {"Content-Type": "application/json"}
            headers = await self._inject_auth_headers(headers)
            # headers now includes Authorization if authenticated
        """
        if self.auth_handler:
            try:
                auth_headers = await self.auth_handler.get_auth_headers()
                headers.update(auth_headers)
            except Exception as e:
                log.warning(
                    "%s Failed to get auth headers: %s",
                    self.log_identifier,
                    e
                )

        return headers

    async def authenticate_and_enrich_user(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Orchestrates the full authentication and identity enrichment flow.
        This method should be called by gateway handlers.
        """
        log_id_prefix = f"{self.log_identifier}[AuthAndEnrich]"

        auth_claims = await self._extract_initial_claims(external_event_data)
        if not auth_claims:
            log.warning(
                "%s Initial claims extraction failed or returned no identity.",
                log_id_prefix,
            )
            return None

        if self.identity_service:
            enriched_profile = await self.identity_service.get_user_profile(auth_claims)
            if enriched_profile:
                final_profile = enriched_profile.copy()
                final_profile.update(auth_claims)
                log.info(
                    "%s Successfully merged auth claims and enriched profile for user: %s",
                    log_id_prefix,
                    auth_claims.get("id"),
                )
                return final_profile
            else:
                log.debug(
                    "%s IdentityService found no profile for user: %s. Using claims only.",
                    log_id_prefix,
                    auth_claims.get("id"),
                )

        return auth_claims

    async def submit_a2a_task(
        self,
        target_agent_name: str,
        a2a_parts: List[ContentPart],
        external_request_context: Dict[str, Any],
        user_identity: Any,
        is_streaming: bool = True,
        api_version: str = "v2",
        task_id_override: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        log_id_prefix = f"{self.log_identifier}[SubmitA2ATask]"
        log.info(
            "%s Submitting task for user_identity: %s",
            log_id_prefix,
            user_identity.get("id", user_identity),
        )

        if not isinstance(user_identity, dict) or not user_identity.get("id"):
            log.error(
                "%s Authentication failed or returned invalid profile. Denying task submission.",
                log_id_prefix,
            )
            raise PermissionError("User not authenticated or identity is invalid.")

        force_identity_str = self.get_config("force_user_identity")
        if force_identity_str:
            original_identity_id = user_identity.get("id")
            user_identity = {"id": force_identity_str, "name": force_identity_str}
            log.warning(
                "%s DEVELOPMENT MODE: Forcing user_identity from '%s' to '%s'",
                log_id_prefix,
                original_identity_id,
                force_identity_str,
            )

        config_resolver = MiddlewareRegistry.get_config_resolver()
        gateway_context = {
            "gateway_id": self.gateway_id,
            "gateway_app_config": self.component_config.get("app_config", {}),
        }

        try:
            user_config = await config_resolver.resolve_user_config(
                user_identity, gateway_context, {}
            )
            log.debug(
                "%s Resolved user configuration for user_identity '%s': %s",
                log_id_prefix,
                user_identity.get("id"),
                {k: v for k, v in user_config.items() if not k.startswith("_")},
            )
        except Exception as config_err:
            log.exception(
                "%s Error resolving user configuration for '%s': %s. Proceeding with default configuration.",
                log_id_prefix,
                user_identity.get("id"),
                config_err,
            )
            user_config = {}

        user_config["user_profile"] = user_identity

        # Validate user has permission to access this target agent
        validate_agent_access(
            user_config=user_config,
            target_agent_name=target_agent_name,
            validation_context={
                "gateway_id": self.gateway_id,
                "source": "gateway_request",
            },
            log_identifier=log_id_prefix,
        )

        external_request_context["user_identity"] = user_identity
        external_request_context["a2a_user_config"] = user_config
        external_request_context["api_version"] = api_version
        external_request_context["is_streaming"] = is_streaming
        log.debug(
            "%s Stored user_identity, configuration, api_version (%s), and is_streaming (%s) in external_request_context.",
            log_id_prefix,
            api_version,
            is_streaming,
        )

        now = datetime.now(timezone.utc)
        timestamp_str = now.isoformat()
        timestamp_header_part = TextPart(
            text=f"Request received by gateway at: {timestamp_str}"
        )
        if not isinstance(a2a_parts, list):
            a2a_parts = list(a2a_parts)
        a2a_parts.insert(0, timestamp_header_part)
        log.debug("%s Prepended timestamp to a2a_parts.", log_id_prefix)

        a2a_session_id = external_request_context.get("a2a_session_id")
        user_id_for_a2a = external_request_context.get(
            "user_id_for_a2a", user_identity.get("id")
        )

        system_purpose = self.get_config("system_purpose", "")
        response_format = self.get_config("response_format", "")

        if not a2a_session_id:
            a2a_session_id = f"gdk-session-{uuid.uuid4().hex}"
            log.warning(
                "%s 'a2a_session_id' not found in external_request_context, generated: %s",
                self.log_identifier,
                a2a_session_id,
            )
            external_request_context["a2a_session_id"] = a2a_session_id

        a2a_metadata = {
            "agent_name": target_agent_name,
            "system_purpose": system_purpose,
            "response_format": response_format,
        }

        # Add session behavior if provided by adapter
        session_behavior = external_request_context.get("session_behavior")
        if session_behavior:
            a2a_metadata["sessionBehavior"] = session_behavior
            log.debug(
                "%s Setting sessionBehavior to: %s", log_id_prefix, session_behavior
            )

        invoked_artifacts = external_request_context.get("invoked_with_artifacts")
        if invoked_artifacts:
            a2a_metadata["invoked_with_artifacts"] = invoked_artifacts
            log.debug(
                "%s Found %d artifact identifiers in external context to pass to agent.",
                log_id_prefix,
                len(invoked_artifacts),
            )
        
        if metadata:
            a2a_metadata.update(metadata)

        # This correlation ID is used by the gateway to track the task
        if task_id_override:
            task_id = task_id_override
        else:
            task_id = f"gdk-task-{uuid.uuid4().hex}"

        prepared_a2a_parts = await self._prepare_parts_for_publishing(
            parts=a2a_parts,
            user_id=user_id_for_a2a,
            session_id=a2a_session_id,
            target_agent_name=target_agent_name,
        )

        a2a_message = a2a.create_user_message(
            parts=prepared_a2a_parts,
            metadata=a2a_metadata,
            context_id=a2a_session_id,
        )

        if is_streaming:
            a2a_request = a2a.create_send_streaming_message_request(
                message=a2a_message, task_id=task_id
            )
        else:
            a2a_request = a2a.create_send_message_request(
                message=a2a_message, task_id=task_id
            )

        payload = a2a_request.model_dump(by_alias=True, exclude_none=True)
        target_topic = a2a.get_agent_request_topic(self.namespace, target_agent_name)

        user_properties = {
            "clientId": self.gateway_id,
            "userId": user_id_for_a2a,
        }
        if user_config:
            user_properties["a2aUserConfig"] = user_config

        # Enterprise feature: Add signed user claims if trust manager available
        if hasattr(self, "trust_manager") and self.trust_manager:
            log.debug(
                "%s Attempting to sign user claims for task %s",
                log_id_prefix,
                task_id,
            )
            try:
                auth_token = self.trust_manager.sign_user_claims(
                    user_info=user_identity, task_id=task_id
                )
                user_properties["authToken"] = auth_token
                log.debug(
                    "%s Successfully signed user claims for task %s",
                    log_id_prefix,
                    task_id,
                )
            except Exception as e:
                log.error(
                    "%s Failed to sign user claims for task %s: %s",
                    log_id_prefix,
                    task_id,
                    e,
                )
                # Continue without token - enterprise feature is optional
        else:
            log.debug(
                "%s Trust Manager not available, proceeding without authentication token",
                log_id_prefix,
            )

        user_properties["replyTo"] = a2a.get_gateway_response_topic(
            self.namespace, self.gateway_id, task_id
        )
        if is_streaming:
            user_properties["a2aStatusTopic"] = a2a.get_gateway_status_topic(
                self.namespace, self.gateway_id, task_id
            )

        self.task_context_manager.store_context(task_id, external_request_context)
        log.info("%s Stored external context for task_id: %s", log_id_prefix, task_id)

        self.publish_a2a_message(
            payload=payload, topic=target_topic, user_properties=user_properties
        )
        log.info(
            "%s Submitted A2A task %s to agent %s. Streaming: %s",
            log_id_prefix,
            task_id,
            target_agent_name,
            is_streaming,
        )
        return task_id

    def _handle_message(self, message: SolaceMessage, topic: str) -> None:
        """
        Override to use queue-based pattern instead of direct async.

        Gateway uses an internal queue for message processing to ensure
        strict ordering and backpressure handling.

        Args:
            message: The Solace message
            topic: The topic the message was received on
        """
        log.debug(
            "%s Received SolaceMessage on topic: %s. Bridging to internal queue.",
            self.log_identifier,
            topic,
        )

        try:
            msg_data_for_processor = {
                "topic": topic,
                "payload": message.get_payload(),
                "user_properties": message.get_user_properties(),
                "_original_broker_message": message,
            }
            self.internal_event_queue.put_nowait(msg_data_for_processor)
        except queue.Full:
            log.error(
                "%s Internal event queue full. Cannot bridge message.",
                self.log_identifier,
            )
            raise
        except Exception as e:
            log.exception(
                "%s Error bridging message to internal queue: %s",
                self.log_identifier,
                e,
            )
            raise

    async def _handle_message_async(self, message, topic: str) -> None:
        """
        Not used by gateway - we override _handle_message() instead.

        This is here to satisfy the abstract method requirement, but the
        gateway uses the queue-based pattern via _handle_message() override.
        """
        raise NotImplementedError(
            "Gateway uses queue-based message handling via _handle_message() override"
        )

    async def _handle_resolved_signals(
        self,
        external_request_context: Dict,
        signals: List[Tuple[None, str, Any]],
        original_rpc_id: Optional[str],
        is_finalizing_context: bool = False,
    ):
        log_id_prefix = f"{self.log_identifier}[SignalHandler]"
        if not signals:
            return

        for signal_tuple in signals:
            if (
                isinstance(signal_tuple, tuple)
                and len(signal_tuple) == 3
                and signal_tuple[0] is None
            ):
                signal_type = signal_tuple[1]
                signal_data = signal_tuple[2]

                if signal_type == "SIGNAL_STATUS_UPDATE":
                    status_text = signal_data
                    log.info(
                        "%s Handling SIGNAL_STATUS_UPDATE: '%s'",
                        log_id_prefix,
                        status_text,
                    )
                    if is_finalizing_context:
                        log.debug(
                            "%s Suppressing SIGNAL_STATUS_UPDATE ('%s') during finalizing context.",
                            log_id_prefix,
                            status_text,
                        )
                        continue
                    try:
                        signal_a2a_message = a2a.create_agent_data_message(
                            data={
                                "type": "agent_progress_update",
                                "status_text": status_text,
                            },
                            part_metadata={"source": "gateway_signal"},
                        )
                        a2a_task_id_for_signal = external_request_context.get(
                            "a2a_task_id_for_event", original_rpc_id
                        )
                        if not a2a_task_id_for_signal:
                            log.error(
                                "%s Cannot determine A2A task ID for signal event. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        signal_event = a2a.create_status_update(
                            task_id=a2a_task_id_for_signal,
                            context_id=external_request_context.get("a2a_session_id"),
                            message=signal_a2a_message,
                            is_final=False,
                        )
                        await self._send_update_to_external(
                            external_request_context=external_request_context,
                            event_data=signal_event,
                            is_final_chunk_of_update=True,
                        )
                        log.debug(
                            "%s Sent status signal as TaskStatusUpdateEvent.",
                            log_id_prefix,
                        )
                    except Exception as e:
                        log.exception(
                            "%s Error sending status signal: %s", log_id_prefix, e
                        )
                elif signal_type == "SIGNAL_ARTIFACT_RETURN":
                    # Handle artifact return signal for legacy gateways
                    # During finalizing context (final Task), suppress this to avoid duplicates
                    # since the same signal might appear in both streaming and final responses
                    if is_finalizing_context:
                        log.debug(
                            "%s Suppressing SIGNAL_ARTIFACT_RETURN during finalizing context to avoid duplicate: %s",
                            log_id_prefix,
                            signal_data,
                        )
                        continue

                    log.info(
                        "%s Handling SIGNAL_ARTIFACT_RETURN for legacy gateway: %s",
                        log_id_prefix,
                        signal_data,
                    )
                    try:
                        filename = signal_data.get("filename")
                        version = signal_data.get("version")

                        if not filename:
                            log.error(
                                "%s SIGNAL_ARTIFACT_RETURN missing filename. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        # Load artifact content (not just metadata) for legacy gateways
                        # Legacy gateways like Slack need the actual bytes to upload files
                        artifact_data = await load_artifact_content_or_metadata(
                            self.shared_artifact_service,
                            app_name=external_request_context.get(
                                "app_name_for_artifacts", self.gateway_id
                            ),
                            user_id=external_request_context.get("user_id_for_artifacts"),
                            session_id=external_request_context.get("a2a_session_id"),
                            filename=filename,
                            version=version,
                            load_metadata_only=False,  # Load full content for legacy gateways
                        )

                        if artifact_data.get("status") != "success":
                            log.error(
                                "%s Failed to load artifact content for %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        # Get content and ensure it's bytes
                        content = artifact_data.get("content")
                        if not content:
                            log.error(
                                "%s No content found in artifact %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        # Convert to bytes if it's a string (text-based artifacts)
                        if isinstance(content, str):
                            content_bytes = content.encode("utf-8")
                        elif isinstance(content, bytes):
                            content_bytes = content
                        else:
                            log.error(
                                "%s Artifact content is neither string nor bytes: %s",
                                log_id_prefix,
                                type(content),
                            )
                            continue

                        # Resolve any late embeds inside the artifact content before returning.
                        content_bytes = await self._resolve_embeds_in_artifact_content(
                            content_bytes=content_bytes,
                            mime_type=artifact_data.get("metadata", {}).get(
                                "mime_type"
                            ),
                            filename=filename,
                            external_request_context=external_request_context,
                            log_id_prefix=log_id_prefix,
                        )

                        # Create FilePart with bytes for legacy gateway to upload
                        file_part = a2a.create_file_part_from_bytes(
                            content_bytes=content_bytes,
                            name=filename,
                            mime_type=artifact_data.get("metadata", {}).get(
                                "mime_type"
                            ),
                        )

                        # Create artifact with the file part
                        # Import Part type for wrapping
                        from a2a.types import Artifact, Part
                        artifact = Artifact(
                            artifact_id=str(uuid.uuid4().hex),
                            parts=[Part(root=file_part)],
                            name=filename,
                            description=f"Artifact: {filename}",
                        )

                        # Send as TaskArtifactUpdateEvent
                        a2a_task_id_for_signal = external_request_context.get(
                            "a2a_task_id_for_event", original_rpc_id
                        )

                        if not a2a_task_id_for_signal:
                            log.error(
                                "%s Cannot determine A2A task ID for artifact signal. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        artifact_event = a2a.create_artifact_update(
                            task_id=a2a_task_id_for_signal,
                            context_id=external_request_context.get("a2a_session_id"),
                            artifact=artifact,
                        )

                        await self._send_update_to_external(
                            external_request_context=external_request_context,
                            event_data=artifact_event,
                            is_final_chunk_of_update=False,
                        )
                        log.info(
                            "%s Sent artifact signal as TaskArtifactUpdateEvent for %s",
                            log_id_prefix,
                            filename,
                        )
                    except Exception as e:
                        log.exception(
                            "%s Error sending artifact signal: %s", log_id_prefix, e
                        )
                elif signal_type == "SIGNAL_ARTIFACT_CREATION_COMPLETE":
                    # Handle artifact creation completion for legacy gateways
                    # This is similar to SIGNAL_ARTIFACT_RETURN but for newly created artifacts
                    log.info(
                        "%s Handling SIGNAL_ARTIFACT_CREATION_COMPLETE for legacy gateway: %s",
                        log_id_prefix,
                        signal_data,
                    )
                    try:
                        filename = signal_data.get("filename")
                        version = signal_data.get("version")

                        if not filename:
                            log.error(
                                "%s SIGNAL_ARTIFACT_CREATION_COMPLETE missing filename. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        # Load artifact content (not just metadata) for legacy gateways
                        # Legacy gateways like Slack need the actual bytes to upload files
                        artifact_data = await load_artifact_content_or_metadata(
                            self.shared_artifact_service,
                            app_name=external_request_context.get(
                                "app_name_for_artifacts", self.gateway_id
                            ),
                            user_id=external_request_context.get("user_id_for_artifacts"),
                            session_id=external_request_context.get("a2a_session_id"),
                            filename=filename,
                            version=version,
                            load_metadata_only=False,  # Load full content for legacy gateways
                        )

                        if artifact_data.get("status") != "success":
                            log.error(
                                "%s Failed to load artifact content for %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        # Get content and ensure it's bytes
                        content = artifact_data.get("content")
                        if not content:
                            log.error(
                                "%s No content found in artifact %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        # Convert to bytes if it's a string (text-based artifacts)
                        if isinstance(content, str):
                            content_bytes = content.encode("utf-8")
                        elif isinstance(content, bytes):
                            content_bytes = content
                        else:
                            log.error(
                                "%s Artifact content is neither string nor bytes: %s",
                                log_id_prefix,
                                type(content),
                            )
                            continue

                        # Create FilePart with bytes for legacy gateway to upload
                        file_part = a2a.create_file_part_from_bytes(
                            content_bytes=content_bytes,
                            name=filename,
                            mime_type=signal_data.get("mime_type") or artifact_data.get("metadata", {}).get("mime_type"),
                        )

                        # Create artifact with the file part
                        # Import Part type for wrapping
                        from a2a.types import Artifact, Part
                        artifact = Artifact(
                            artifact_id=str(uuid.uuid4().hex),
                            parts=[Part(root=file_part)],
                            name=filename,
                            description=f"Artifact: {filename}",
                        )

                        # Send as TaskArtifactUpdateEvent
                        a2a_task_id_for_signal = external_request_context.get(
                            "a2a_task_id_for_event", original_rpc_id
                        )

                        if not a2a_task_id_for_signal:
                            log.error(
                                "%s Cannot determine A2A task ID for artifact creation signal. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        artifact_event = a2a.create_artifact_update(
                            task_id=a2a_task_id_for_signal,
                            context_id=external_request_context.get("a2a_session_id"),
                            artifact=artifact,
                        )

                        await self._send_update_to_external(
                            external_request_context=external_request_context,
                            event_data=artifact_event,
                            is_final_chunk_of_update=False,
                        )
                        log.info(
                            "%s Sent artifact creation completion as TaskArtifactUpdateEvent for %s",
                            log_id_prefix,
                            filename,
                        )
                    except Exception as e:
                        log.exception(
                            "%s Error sending artifact creation completion signal: %s", log_id_prefix, e
                        )
                elif signal_type == "SIGNAL_DEEP_RESEARCH_REPORT":
                    # Handle deep research report signal for legacy gateways
                    # For legacy gateways, we send the report as a file attachment
                    if is_finalizing_context:
                        log.debug(
                            "%s Suppressing SIGNAL_DEEP_RESEARCH_REPORT during finalizing context to avoid duplicate: %s",
                            log_id_prefix,
                            signal_data,
                        )
                        continue

                    try:
                        filename = signal_data.get("filename")
                        version = signal_data.get("version")

                        if not filename:
                            log.error(
                                "%s SIGNAL_DEEP_RESEARCH_REPORT missing filename. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        # Load artifact content for legacy gateways
                        artifact_data = await load_artifact_content_or_metadata(
                            self.shared_artifact_service,
                            app_name=external_request_context.get(
                                "app_name_for_artifacts", self.gateway_id
                            ),
                            user_id=external_request_context.get("user_id_for_artifacts"),
                            session_id=external_request_context.get("a2a_session_id"),
                            filename=filename,
                            version=version,
                            load_metadata_only=False,
                        )

                        if artifact_data.get("status") != "success":
                            log.error(
                                "%s Failed to load deep research report content for %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        content = artifact_data.get("content")
                        if not content:
                            log.error(
                                "%s No content found in deep research report %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            continue

                        # Convert to bytes if it's a string
                        if isinstance(content, str):
                            content_bytes = content.encode("utf-8")
                        elif isinstance(content, bytes):
                            content_bytes = content
                        else:
                            log.error(
                                "%s Deep research report content is neither string nor bytes: %s",
                                log_id_prefix,
                                type(content),
                            )
                            continue

                        # Create FilePart with bytes for legacy gateway to upload
                        file_part = a2a.create_file_part_from_bytes(
                            content_bytes=content_bytes,
                            name=filename,
                            mime_type=artifact_data.get("metadata", {}).get(
                                "mime_type", "text/markdown"
                            ),
                        )

                        # Create artifact with the file part
                        from a2a.types import Artifact, Part
                        artifact = Artifact(
                            artifact_id=str(uuid.uuid4().hex),
                            parts=[Part(root=file_part)],
                            name=filename,
                            description=f"Deep Research Report: {filename}",
                        )

                        # Send as TaskArtifactUpdateEvent
                        a2a_task_id_for_signal = external_request_context.get(
                            "a2a_task_id_for_event", original_rpc_id
                        )

                        if not a2a_task_id_for_signal:
                            log.error(
                                "%s Cannot determine A2A task ID for deep research report signal. Skipping.",
                                log_id_prefix,
                            )
                            continue

                        artifact_event = a2a.create_artifact_update(
                            task_id=a2a_task_id_for_signal,
                            context_id=external_request_context.get("a2a_session_id"),
                            artifact=artifact,
                        )

                        await self._send_update_to_external(
                            external_request_context=external_request_context,
                            event_data=artifact_event,
                            is_final_chunk_of_update=False,
                        )
                        log.info(
                            "%s Sent deep research report as TaskArtifactUpdateEvent for %s",
                            log_id_prefix,
                            filename,
                        )
                    except Exception as e:
                        log.exception(
                            "%s Error sending deep research report signal: %s", log_id_prefix, e
                        )
                else:
                    log.warning(
                        "%s Received unhandled signal type during embed resolution: %s",
                        log_id_prefix,
                        signal_type,
                    )

    async def _resolve_embeds_in_artifact_content(
        self,
        content_bytes: bytes,
        mime_type: Optional[str],
        filename: str,
        external_request_context: Dict[str, Any],
        log_id_prefix: str,
    ) -> bytes:
        """
        Checks if content is text-based and, if so, resolves late embeds within it.
        Returns the (potentially modified) content as bytes.
        """
        if is_text_based_mime_type(mime_type):
            log.info(
                "%s Artifact '%s' is text-based (%s). Resolving late embeds.",
                log_id_prefix,
                filename,
                mime_type,
            )
            try:
                decoded_content = content_bytes.decode("utf-8")

                # Construct context and config for the resolver
                embed_eval_context = {
                    "artifact_service": self.shared_artifact_service,
                    "session_context": {
                        "app_name": external_request_context.get(
                            "app_name_for_artifacts", self.gateway_id
                        ),
                        "user_id": external_request_context.get(
                            "user_id_for_artifacts"
                        ),
                        "session_id": external_request_context.get("a2a_session_id"),
                    },
                }
                embed_eval_config = {
                    "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
                    "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
                }

                resolved_string = await resolve_embeds_recursively_in_string(
                    text=decoded_content,
                    context=embed_eval_context,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES,
                    resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                    log_identifier=f"{log_id_prefix}[RecursiveResolve]",
                    config=embed_eval_config,
                    max_depth=self.gateway_recursive_embed_depth,
                )
                resolved_bytes = resolved_string.encode("utf-8")
                log.info(
                    "%s Successfully resolved embeds in '%s'. New size: %d bytes.",
                    log_id_prefix,
                    filename,
                    len(resolved_bytes),
                )
                return resolved_bytes
            except Exception as resolve_err:
                log.error(
                    "%s Failed to resolve embeds within artifact '%s': %s. Returning raw content.",
                    log_id_prefix,
                    filename,
                    resolve_err,
                )
        return content_bytes

    async def _resolve_uri_in_file_part(
        self, file_part: FilePart, external_request_context: Dict[str, Any]
    ):
        """
        Checks if a FilePart has a resolvable URI and, if so,
        resolves it and mutates the part in-place by calling the common utility.
        After resolving the URI, it also resolves any late embeds within the content.
        """
        await a2a.resolve_file_part_uri(
            part=file_part,
            artifact_service=self.shared_artifact_service,
            log_identifier=self.log_identifier,
        )

        # After resolving the URI to get the content, resolve any late embeds inside it.
        if file_part.file and isinstance(file_part.file, FileWithBytes):
            # The content is a base64 encoded string in the `bytes` attribute.
            # We need to decode it to raw bytes for processing.
            try:
                content_bytes = base64.b64decode(file_part.file.bytes)
            except Exception as e:
                log.error(
                    "%s Failed to base64 decode file content for embed resolution: %s",
                    f"{self.log_identifier}[UriResolve]",
                    e,
                )
                return

            resolved_bytes = await self._resolve_embeds_in_artifact_content(
                content_bytes=content_bytes,
                mime_type=file_part.file.mime_type,
                filename=file_part.file.name,
                external_request_context=external_request_context,
                log_id_prefix=f"{self.log_identifier}[UriResolve]",
            )
            # Re-encode the resolved content back to a base64 string for the FileWithBytes model.
            file_part.file.bytes = base64.b64encode(resolved_bytes).decode("utf-8")

    async def _resolve_uris_in_parts_list(
        self, parts: List[ContentPart], external_request_context: Dict[str, Any]
    ):
        """Iterates over a list of part objects and resolves any FilePart URIs."""
        if not parts:
            return
        for part in parts:
            if isinstance(part, FilePart):
                await self._resolve_uri_in_file_part(part, external_request_context)

    async def _resolve_uris_in_payload(
        self, parsed_event: Any, external_request_context: Dict[str, Any]
    ):
        """
        Dispatcher that calls the appropriate targeted URI resolver based on the
        Pydantic model type of the event.
        """
        parts_to_resolve: List[ContentPart] = []
        if isinstance(parsed_event, TaskStatusUpdateEvent):
            message = a2a.get_message_from_status_update(parsed_event)
            if message:
                parts_to_resolve.extend(a2a.get_parts_from_message(message))
        elif isinstance(parsed_event, TaskArtifactUpdateEvent):
            artifact = a2a.get_artifact_from_artifact_update(parsed_event)
            if artifact:
                parts_to_resolve.extend(a2a.get_parts_from_artifact(artifact))
        elif isinstance(parsed_event, Task):
            if parsed_event.status and parsed_event.status.message:
                parts_to_resolve.extend(
                    a2a.get_parts_from_message(parsed_event.status.message)
                )
            if parsed_event.artifacts:
                for artifact in parsed_event.artifacts:
                    parts_to_resolve.extend(a2a.get_parts_from_artifact(artifact))

        if parts_to_resolve:
            await self._resolve_uris_in_parts_list(
                parts_to_resolve, external_request_context
            )
        else:
            log.debug(
                "%s Payload type '%s' did not yield any parts for URI resolution. Skipping.",
                self.log_identifier,
                type(parsed_event).__name__,
            )

    async def _handle_discovery_message(self, payload: Dict) -> bool:
        """Handles incoming agent and gateway discovery messages."""
        try:
            agent_card = AgentCard(**payload)

            # Route to appropriate registry based on card type
            if is_gateway_card(agent_card):
                # This is a gateway card - track in gateway registry
                is_new = self.gateway_registry.add_or_update_gateway(agent_card)
                if is_new:
                    gateway_type = self.gateway_registry.get_gateway_type(agent_card.name)
                    log.info(
                        "%s New gateway discovered: %s (type: %s)",
                        self.log_identifier,
                        agent_card.name,
                        gateway_type or "unknown"
                    )
                else:
                    log.debug(
                        "%s Gateway heartbeat received: %s",
                        self.log_identifier,
                        agent_card.name
                    )
            else:
                # This is an agent card - use existing logic
                self.core_a2a_service.process_discovery_message(agent_card)

            return True
        except Exception as e:
            log.error(
                "%s Failed to process discovery message: %s. Payload: %s",
                self.log_identifier,
                e,
                payload,
            )
            return False

    async def _prepare_parts_for_publishing(
        self,
        parts: List[ContentPart],
        user_id: str,
        session_id: str,
        target_agent_name: str,
    ) -> List[ContentPart]:
        """
        Prepares message parts for publishing according to the configured artifact_handling_mode
        by calling the common utility function.
        """
        processed_parts: List[ContentPart] = []
        for part in parts:
            if isinstance(part, FilePart):
                processed_part = await a2a.prepare_file_part_for_publishing(
                    part=part,
                    mode=self.artifact_handling_mode,
                    artifact_service=self.shared_artifact_service,
                    user_id=user_id,
                    session_id=session_id,
                    target_agent_name=target_agent_name,
                    log_identifier=self.log_identifier,
                )
                if processed_part:
                    processed_parts.append(processed_part)
            else:
                processed_parts.append(part)
        return processed_parts

    def _should_include_data_part_in_final_output(self, part: Any) -> bool:
        """
        Determines if a DataPart should be included in the final output sent to the gateway.

        This filters out internal/tool-related DataParts that shouldn't be shown to end users.
        Gateways can override this method for custom filtering logic.

        Args:
            part: The part to check (expected to be a DataPart)

        Returns:
            True if the part should be included, False if it should be filtered out
        """
        from a2a.types import DataPart

        if not isinstance(part, DataPart):
            return True

        # Check if this is a tool result by looking at metadata
        # Tool results have metadata.tool_name set
        if part.metadata and part.metadata.get("tool_name"):
            # This is a tool result - filter it out
            return False

        # Get the type of the data part
        data_type = part.data.get("type") if part.data else None

        # Filter out tool-related data parts that are internal
        tool_related_types = {
            "tool_call",
            "tool_result",
            "tool_error",
            "tool_execution",
        }

        if data_type in tool_related_types:
            return False

        # Handle artifact_creation_progress based on gateway capabilities
        if data_type == "artifact_creation_progress":
            # For modern gateways (HTTP SSE), keep these to display progress bubbles
            # For legacy gateways (Slack), filter them out as they'll be converted to FileParts
            if self.supports_inline_artifact_resolution:
                return True  # Keep for HTTP SSE
            else:
                return False  # Filter for Slack (will be converted to FileParts instead)

        # Keep user-facing data parts like general progress updates
        user_facing_types = {
            "agent_progress_update",
        }

        if data_type in user_facing_types:
            return True

        # Default: include unknown types (to avoid hiding potentially useful info)
        return True

    async def _resolve_embeds_and_handle_signals(
        self,
        event_with_parts: Union[TaskStatusUpdateEvent, Task, TaskArtifactUpdateEvent],
        external_request_context: Dict[str, Any],
        a2a_task_id: str,
        original_rpc_id: Optional[str],
        is_finalizing_context: bool = False,
    ) -> bool:
        if not self.enable_embed_resolution:
            return False

        log_id_prefix = f"{self.log_identifier}[EmbedResolve:{a2a_task_id}]"
        content_modified = False

        embed_eval_context = {
            "artifact_service": self.shared_artifact_service,
            "session_context": {
                "app_name": external_request_context.get(
                    "app_name_for_artifacts", self.gateway_id
                ),
                "user_id": external_request_context.get("user_id_for_artifacts"),
                "session_id": external_request_context.get("a2a_session_id"),
            },
        }
        embed_eval_config = {
            "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
            "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
        }

        parts_owner: Optional[Union[A2AMessage, A2AArtifact]] = None
        if isinstance(event_with_parts, (TaskStatusUpdateEvent, Task)):
            if event_with_parts.status and event_with_parts.status.message:
                parts_owner = event_with_parts.status.message
        elif isinstance(event_with_parts, TaskArtifactUpdateEvent):
            if event_with_parts.artifact:
                parts_owner = event_with_parts.artifact

        if not (parts_owner and parts_owner.parts):
            return False

        is_streaming_status_update = isinstance(event_with_parts, TaskStatusUpdateEvent)
        stream_buffer_key = f"{a2a_task_id}_stream_buffer"
        current_buffer = ""
        if is_streaming_status_update:
            current_buffer = (
                self.task_context_manager.get_context(stream_buffer_key) or ""
            )

        original_parts: List[ContentPart] = (
            a2a.get_parts_from_message(parts_owner)
            if isinstance(parts_owner, A2AMessage)
            else a2a.get_parts_from_artifact(parts_owner)
        )

        new_parts: List[ContentPart] = []
        other_signals = []

        for part in original_parts:
            if isinstance(part, TextPart) and part.text:
                text_to_resolve = current_buffer + part.text
                current_buffer = ""  # Buffer is now being processed

                (
                    resolved_text,
                    processed_idx,
                    signals_with_placeholders,
                ) = await resolve_embeds_in_string(
                    text=text_to_resolve,
                    context=embed_eval_context,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES.union({"status_update"}),
                    resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
                    log_identifier=log_id_prefix,
                    config=embed_eval_config,
                )

                if not signals_with_placeholders:
                    new_parts.append(a2a.create_text_part(text=resolved_text))
                else:
                    placeholder_map = {p: s for _, s, p in signals_with_placeholders}
                    split_pattern = (
                        f"({'|'.join(re.escape(p) for p in placeholder_map.keys())})"
                    )
                    text_fragments = re.split(split_pattern, resolved_text)

                    for i, fragment in enumerate(text_fragments):
                        if not fragment:
                            continue
                        if fragment in placeholder_map:
                            signal_tuple = placeholder_map[fragment]
                            signal_type, signal_data = signal_tuple[1], signal_tuple[2]
                            if signal_type == "SIGNAL_ARTIFACT_RETURN":
                                # Only convert to FilePart if gateway supports inline artifact resolution
                                if self.supports_inline_artifact_resolution:
                                    try:
                                        filename, version = (
                                            signal_data["filename"],
                                            signal_data["version"],
                                        )
                                        artifact_data = (
                                            await load_artifact_content_or_metadata(
                                                self.shared_artifact_service,
                                                **embed_eval_context["session_context"],
                                                filename=filename,
                                                version=version,
                                                load_metadata_only=True,
                                            )
                                        )
                                        if artifact_data.get("status") == "success":
                                            uri = format_artifact_uri(
                                                **embed_eval_context["session_context"],
                                                filename=filename,
                                                version=artifact_data.get("version"),
                                            )
                                            new_parts.append(
                                                a2a.create_file_part_from_uri(
                                                    uri,
                                                    filename,
                                                    artifact_data.get("metadata", {}).get(
                                                        "mime_type"
                                                    ),
                                                )
                                            )
                                        else:
                                            new_parts.append(
                                                a2a.create_text_part(
                                                    f"[Error: Artifact '{filename}' v{version} not found.]"
                                                )
                                            )
                                    except Exception as e:
                                        log.exception(
                                            "%s Error handling SIGNAL_ARTIFACT_RETURN: %s",
                                            log_id_prefix,
                                            e,
                                        )
                                        new_parts.append(
                                            a2a.create_text_part(
                                                f"[Error: Could not retrieve artifact '{signal_data.get('filename')}'.]"
                                            )
                                        )
                                else:
                                    # Legacy gateway mode: pass signal through for gateway to handle
                                    other_signals.append(signal_tuple)
                            elif signal_type == "SIGNAL_DEEP_RESEARCH_REPORT":
                                # Deep research reports should be rendered by the frontend component
                                # For modern gateways (HTTP SSE), create a DataPart with artifact reference
                                # For legacy gateways, pass through as signal
                                if self.supports_inline_artifact_resolution:
                                    try:
                                        filename = signal_data["filename"]
                                        version = signal_data["version"]
                                        log.info(
                                            "%s Converting SIGNAL_DEEP_RESEARCH_REPORT to DataPart for frontend rendering: %s v%s",
                                            log_id_prefix,
                                            filename,
                                            version,
                                        )
                                        # Create a DataPart that the frontend can use to render DeepResearchReportBubble
                                        # The frontend will fetch the artifact content separately
                                        artifact_data = (
                                            await load_artifact_content_or_metadata(
                                                self.shared_artifact_service,
                                                **embed_eval_context["session_context"],
                                                filename=filename,
                                                version=version,
                                                load_metadata_only=True,
                                            )
                                        )
                                        if artifact_data.get("status") == "success":
                                            uri = format_artifact_uri(
                                                **embed_eval_context["session_context"],
                                                filename=filename,
                                                version=artifact_data.get("version"),
                                            )
                                            # Create a DataPart with deep_research_report type
                                            # This will be rendered by DeepResearchReportBubble in the frontend
                                            data_part = a2a.create_data_part(
                                                data={
                                                    "type": "deep_research_report",
                                                    "filename": filename,
                                                    "version": artifact_data.get("version"),
                                                    "uri": uri,
                                                },
                                                metadata={"source": "deep_research_tool"},
                                            )
                                            new_parts.append(data_part)
                                        else:
                                            new_parts.append(
                                                a2a.create_text_part(
                                                    f"[Error: Deep research report '{filename}' v{version} not found.]"
                                                )
                                            )
                                    except Exception as e:
                                        log.exception(
                                            "%s Error handling SIGNAL_DEEP_RESEARCH_REPORT: %s",
                                            log_id_prefix,
                                            e,
                                        )
                                        new_parts.append(
                                            a2a.create_text_part(
                                                f"[Error: Could not retrieve deep research report '{signal_data.get('filename')}'.]"
                                            )
                                        )
                                else:
                                    # Legacy gateway mode: pass signal through for gateway to handle
                                    other_signals.append(signal_tuple)
                            elif signal_type == "SIGNAL_INLINE_BINARY_CONTENT":
                                signal_data["content_bytes"] = signal_data.get("bytes")
                                del signal_data["bytes"]
                                new_parts.append(
                                    a2a.create_file_part_from_bytes(**signal_data)
                                )
                            else:
                                other_signals.append(signal_tuple)
                        else:
                            # Check if the non-placeholder fragment is just whitespace
                            # and is between two placeholders. If so, drop it.
                            is_just_whitespace = not fragment.strip()
                            prev_fragment_was_placeholder = (
                                i > 0 and text_fragments[i - 1] in placeholder_map
                            )
                            next_fragment_is_placeholder = (
                                i < len(text_fragments) - 1
                                and text_fragments[i + 1] in placeholder_map
                            )

                            if (
                                is_just_whitespace
                                and prev_fragment_was_placeholder
                                and next_fragment_is_placeholder
                            ):
                                log.debug(
                                    "%s Dropping whitespace fragment between two file signals.",
                                    log_id_prefix,
                                )
                                continue

                            new_parts.append(a2a.create_text_part(text=fragment))

                if is_streaming_status_update:
                    current_buffer = text_to_resolve[processed_idx:]

            elif isinstance(part, FilePart) and part.file:
                # Handle recursive embeds in text-based FileParts
                new_parts.append(part)  # Placeholder for now
            elif isinstance(part, DataPart):
                # Handle special DataPart types
                data_type = part.data.get("type") if part.data else None

                if data_type == "template_block":
                    # Resolve template block and replace with resolved text
                    try:
                        from ...common.utils.templates import resolve_template_blocks_in_string

                        # Reconstruct the template block syntax
                        data_artifact = part.data.get("data_artifact", "")
                        jsonpath = part.data.get("jsonpath")
                        limit = part.data.get("limit")
                        template_content = part.data.get("template_content", "")

                        # Build params string
                        params_parts = [f'data="{data_artifact}"']
                        if jsonpath:
                            params_parts.append(f'jsonpath="{jsonpath}"')
                        if limit is not None:
                            params_parts.append(f'limit="{limit}"')
                        params_str = " ".join(params_parts)

                        # Reconstruct full template block
                        template_block = f"«««template: {params_str}\n{template_content}\n»»»"

                        log.debug(
                            "%s Resolving template block inline: data=%s",
                            log_id_prefix,
                            data_artifact,
                        )

                        # Resolve the template
                        resolved_text = await resolve_template_blocks_in_string(
                            text=template_block,
                            artifact_service=self.shared_artifact_service,
                            session_context={
                                "app_name": external_request_context.get(
                                    "app_name_for_artifacts", self.gateway_id
                                ),
                                "user_id": external_request_context.get("user_id_for_artifacts"),
                                "session_id": external_request_context.get("a2a_session_id"),
                            },
                            log_identifier=f"{log_id_prefix}[TemplateResolve]",
                        )

                        log.info(
                            "%s Template resolved successfully. Output length: %d",
                            log_id_prefix,
                            len(resolved_text),
                        )

                        # Replace the DataPart with a TextPart containing the resolved content
                        new_parts.append(a2a.create_text_part(text=resolved_text))

                    except Exception as e:
                        log.error(
                            "%s Failed to resolve template block: %s",
                            log_id_prefix,
                            e,
                            exc_info=True,
                        )
                        # Send error message as TextPart
                        error_text = f"[Template rendering error: {str(e)}]"
                        new_parts.append(a2a.create_text_part(text=error_text))

                elif (
                    data_type == "artifact_creation_progress"
                    and not self.supports_inline_artifact_resolution
                ):
                    # Legacy gateway mode: convert completed artifact creation to FilePart
                    status = part.data.get("status")
                    if status == "completed" and not is_finalizing_context:
                        # Extract artifact info from the DataPart
                        filename = part.data.get("filename")
                        version = part.data.get("version")
                        mime_type = part.data.get("mime_type")

                        if filename and version is not None:
                            log.info(
                                "%s Converting artifact creation completion to FilePart for legacy gateway: %s v%s",
                                log_id_prefix,
                                filename,
                                version,
                            )
                            # This will be sent as an artifact signal, so don't add to new_parts
                            # Instead, add to other_signals for processing
                            signal_tuple = (
                                None,
                                "SIGNAL_ARTIFACT_CREATION_COMPLETE",
                                {
                                    "filename": filename,
                                    "version": version,
                                    "mime_type": mime_type,
                                },
                            )
                            other_signals.append(signal_tuple)
                        else:
                            # Missing required info, keep the DataPart as-is
                            new_parts.append(part)
                    elif status == "completed" and is_finalizing_context:
                        # Suppress during finalizing to avoid duplicates
                        log.debug(
                            "%s Suppressing artifact creation completion during finalizing context for %s",
                            log_id_prefix,
                            part.data.get("filename"),
                        )
                        continue
                    else:
                        # Keep in-progress or failed status DataParts
                        new_parts.append(part)
                else:
                    # Not an artifact creation DataPart, or modern gateway - keep as-is
                    new_parts.append(part)
            else:
                new_parts.append(part)

        if other_signals:
            await self._handle_resolved_signals(
                external_request_context,
                other_signals,
                original_rpc_id,
                is_finalizing_context,
            )

        if new_parts != original_parts:
            content_modified = True
            if isinstance(parts_owner, A2AMessage):
                if isinstance(event_with_parts, TaskStatusUpdateEvent):
                    event_with_parts.status.message = a2a.update_message_parts(
                        parts_owner, new_parts
                    )
                elif isinstance(event_with_parts, Task):
                    event_with_parts.status.message = a2a.update_message_parts(
                        parts_owner, new_parts
                    )
            elif isinstance(parts_owner, A2AArtifact):
                event_with_parts.artifact = a2a.update_artifact_parts(
                    parts_owner, new_parts
                )

        if is_streaming_status_update:
            self.task_context_manager.store_context(stream_buffer_key, current_buffer)

        return content_modified or bool(other_signals)

    async def _process_parsed_a2a_event(
        self,
        parsed_event: Union[
            Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError
        ],
        external_request_context: Dict[str, Any],
        a2a_task_id: str,
        original_rpc_id: Optional[str],
    ) -> None:
        """
        Processes a parsed A2A event: resolves embeds, handles signals,
        sends to external, and manages context.
        """
        log_id_prefix = f"{self.log_identifier}[ProcessParsed:{a2a_task_id}]"
        is_truly_final_event_for_context_cleanup = False
        is_finalizing_context_for_embeds = False

        if isinstance(parsed_event, JSONRPCError):
            log.warning(
                "%s Handling JSONRPCError for task %s.", log_id_prefix, a2a_task_id
            )
            await self._send_error_to_external(external_request_context, parsed_event)
            is_truly_final_event_for_context_cleanup = True
        else:
            content_was_modified_or_signals_handled = False

            if isinstance(parsed_event, TaskStatusUpdateEvent) and parsed_event.final:
                is_finalizing_context_for_embeds = True
            elif isinstance(parsed_event, Task):
                is_finalizing_context_for_embeds = True

            if not isinstance(parsed_event, JSONRPCError):
                content_was_modified_or_signals_handled = (
                    await self._resolve_embeds_and_handle_signals(
                        parsed_event,
                        external_request_context,
                        a2a_task_id,
                        original_rpc_id,
                        is_finalizing_context=is_finalizing_context_for_embeds,
                    )
                )

            if self.resolve_artifact_uris_in_gateway:
                log.debug(
                    "%s Resolving artifact URIs before sending to external...",
                    log_id_prefix,
                )
                await self._resolve_uris_in_payload(
                    parsed_event, external_request_context
                )

            send_this_event_to_external = True
            is_final_chunk_of_status_update = False

            if isinstance(parsed_event, TaskStatusUpdateEvent):
                # Try enterprise handling for input_required state (OAuth authentication)
                if parsed_event.status and parsed_event.status.state == TaskState.input_required:
                    try:
                        from solace_agent_mesh_enterprise.auth.input_required import (
                            handle_input_required_request,
                        )
                        parsed_event = handle_input_required_request(
                            parsed_event,
                            a2a_task_id,
                            self  # Gateway component for caching
                        )
                    except ImportError:
                        pass  # Enterprise not installed

                is_final_chunk_of_status_update = parsed_event.final
                if (
                    not (
                        parsed_event.status
                        and parsed_event.status.message
                        and parsed_event.status.message.parts
                    )
                    and not parsed_event.metadata
                    and not is_final_chunk_of_status_update
                    and not content_was_modified_or_signals_handled
                ):
                    send_this_event_to_external = False
                    log.debug(
                        "%s Suppressing empty intermediate status update.",
                        log_id_prefix,
                    )
            elif isinstance(parsed_event, TaskArtifactUpdateEvent):
                if (
                    not (parsed_event.artifact and parsed_event.artifact.parts)
                    and not content_was_modified_or_signals_handled
                ):
                    send_this_event_to_external = False
                    log.debug("%s Suppressing empty artifact update.", log_id_prefix)
            elif isinstance(parsed_event, Task):
                is_truly_final_event_for_context_cleanup = True

                if (
                    self._RESOLVE_EMBEDS_IN_FINAL_RESPONSE
                    and parsed_event.status
                    and parsed_event.status.message
                    and parsed_event.status.message.parts
                ):
                    log.debug(
                        "%s Resolving embeds in final task response...", log_id_prefix
                    )
                    message = parsed_event.status.message
                    combined_text = a2a.get_text_from_message(message)
                    data_parts = a2a.get_data_parts_from_message(message)
                    file_parts = a2a.get_file_parts_from_message(message)
                    non_text_parts = data_parts + file_parts

                    if combined_text:
                        embed_eval_context = {
                            "artifact_service": self.shared_artifact_service,
                            "session_context": {
                                "app_name": external_request_context.get(
                                    "app_name_for_artifacts", self.gateway_id
                                ),
                                "user_id": external_request_context.get(
                                    "user_id_for_artifacts"
                                ),
                                "session_id": external_request_context.get(
                                    "a2a_session_id"
                                ),
                            },
                        }
                        embed_eval_config = {
                            "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
                            "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
                        }
                        all_embed_types = EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES)
                        resolved_text, _, signals = await resolve_embeds_in_string(
                            text=combined_text,
                            context=embed_eval_context,
                            resolver_func=evaluate_embed,
                            types_to_resolve=all_embed_types,
                            resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
                            log_identifier=log_id_prefix,
                            config=embed_eval_config,
                        )
                        if signals:
                            log.debug(
                                "%s Handling %d signals found during final response embed resolution.",
                                log_id_prefix,
                                len(signals),
                            )
                            await self._handle_resolved_signals(
                                external_request_context,
                                signals,
                                original_rpc_id,
                                is_finalizing_context=True,
                            )

                        new_parts = (
                            [a2a.create_text_part(text=resolved_text)]
                            if resolved_text
                            else []
                        )
                        new_parts.extend(non_text_parts)
                        parsed_event.status.message = a2a.update_message_parts(
                            message=parsed_event.status.message,
                            new_parts=new_parts,
                        )
                        log.info(
                            "%s Final response text updated with resolved embeds.",
                            log_id_prefix,
                        )

                final_buffer_key = f"{a2a_task_id}_stream_buffer"
                remaining_buffer = self.task_context_manager.get_context(
                    final_buffer_key
                )
                if remaining_buffer:
                    log.info(
                        "%s Flushing remaining buffer for task %s before final response.",
                        log_id_prefix,
                        a2a_task_id,
                    )
                    embed_eval_context = {
                        "artifact_service": self.shared_artifact_service,
                        "session_context": {
                            "app_name": external_request_context.get(
                                "app_name_for_artifacts", self.gateway_id
                            ),
                            "user_id": external_request_context.get(
                                "user_id_for_artifacts"
                            ),
                            "session_id": external_request_context.get(
                                "a2a_session_id"
                            ),
                        },
                    }
                    embed_eval_config = {
                        "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
                        "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
                    }
                    resolved_remaining_text, _, signals = (
                        await resolve_embeds_in_string(
                            text=remaining_buffer,
                            context=embed_eval_context,
                            resolver_func=evaluate_embed,
                            types_to_resolve=LATE_EMBED_TYPES.copy(),
                            resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
                            log_identifier=log_id_prefix,
                            config=embed_eval_config,
                        )
                    )
                    await self._handle_resolved_signals(
                        external_request_context,
                        signals,
                        original_rpc_id,
                        is_finalizing_context=True,
                    )
                    if resolved_remaining_text:
                        flush_message = a2a.create_agent_text_message(
                            text=resolved_remaining_text
                        )
                        flush_event = a2a.create_status_update(
                            task_id=a2a_task_id,
                            context_id=external_request_context.get("a2a_session_id"),
                            message=flush_message,
                            is_final=False,
                        )
                        await self._send_update_to_external(
                            external_request_context, flush_event, True
                        )
                    self.task_context_manager.remove_context(final_buffer_key)

            if send_this_event_to_external:
                if isinstance(parsed_event, Task):
                    # Filter DataParts from final Task if gateway has filtering enabled
                    # This prevents tool results and other internal data from appearing in user-facing output
                    if (
                        self.filter_tool_data_parts
                        and parsed_event.status
                        and parsed_event.status.message
                        and parsed_event.status.message.parts
                    ):
                        original_parts = a2a.get_parts_from_message(
                            parsed_event.status.message
                        )
                        filtered_parts = [
                            part
                            for part in original_parts
                            if self._should_include_data_part_in_final_output(part)
                        ]
                        if len(filtered_parts) != len(original_parts):
                            log.debug(
                                "%s Filtered %d DataParts from final Task message",
                                log_id_prefix,
                                len(original_parts) - len(filtered_parts),
                            )
                            parsed_event.status.message = a2a.update_message_parts(
                                parsed_event.status.message, filtered_parts
                            )

                    await self._send_final_response_to_external(
                        external_request_context, parsed_event
                    )
                elif isinstance(
                    parsed_event, (TaskStatusUpdateEvent, TaskArtifactUpdateEvent)
                ):
                    final_chunk_flag = (
                        is_final_chunk_of_status_update
                        if isinstance(parsed_event, TaskStatusUpdateEvent)
                        else False
                    )
                    await self._send_update_to_external(
                        external_request_context, parsed_event, final_chunk_flag
                    )

        if is_truly_final_event_for_context_cleanup:
            log.info(
                "%s Truly final event processed for task %s. Removing context.",
                log_id_prefix,
                a2a_task_id,
            )
            self.task_context_manager.remove_context(a2a_task_id)
            self.task_context_manager.remove_context(f"{a2a_task_id}_stream_buffer")

    async def _handle_agent_event(
        self, topic: str, payload: Dict, task_id_from_topic: str
    ) -> bool:
        """
        Handles messages received on gateway response and status topics.
        Parses the payload, retrieves context using task_id_from_topic, and dispatches for processing.
        """
        try:
            rpc_response = JSONRPCResponse.model_validate(payload)
        except Exception as e:
            log.error(
                "%s Failed to parse payload as JSONRPCResponse for topic %s (Task ID from topic: %s): %s. Payload: %s",
                self.log_identifier,
                topic,
                task_id_from_topic,
                e,
                payload,
            )
            return False

        original_rpc_id = str(a2a.get_response_id(rpc_response))

        external_request_context = self.task_context_manager.get_context(
            task_id_from_topic
        )
        if not external_request_context:
            log.warning(
                "%s No external context found for A2A Task ID: %s (from topic). Ignoring message. Topic: %s, RPC ID: %s",
                self.log_identifier,
                task_id_from_topic,
                topic,
                original_rpc_id,
            )
            return True

        external_request_context["a2a_task_id_for_event"] = task_id_from_topic
        external_request_context["original_rpc_id"] = original_rpc_id

        parsed_event_obj: Union[
            Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError, None
        ] = None
        error = a2a.get_response_error(rpc_response)
        if error:
            parsed_event_obj = error
        else:
            result = a2a.get_response_result(rpc_response)
            if result:
                # The result is already a parsed Pydantic model.
                parsed_event_obj = result

            # Validate task ID match
            actual_task_id = None
            if isinstance(parsed_event_obj, Task):
                actual_task_id = parsed_event_obj.id
            elif isinstance(
                parsed_event_obj, (TaskStatusUpdateEvent, TaskArtifactUpdateEvent)
            ):
                actual_task_id = parsed_event_obj.task_id

            if (
                task_id_from_topic
                and actual_task_id
                and actual_task_id != task_id_from_topic
            ):
                log.error(
                    "%s Task ID mismatch! Expected: %s, Got from payload: %s.",
                    self.log_identifier,
                    task_id_from_topic,
                    actual_task_id,
                )
                parsed_event_obj = None

        if not parsed_event_obj:
            log.error(
                "%s Failed to parse or validate A2A event from RPC result for task %s. Result: %s",
                self.log_identifier,
                task_id_from_topic,
                a2a.get_response_result(rpc_response) or "N/A",
            )
            generic_error = JSONRPCError(
                code=-32000, message="Invalid event structure received from agent."
            )
            await self._send_error_to_external(external_request_context, generic_error)
            self.task_context_manager.remove_context(task_id_from_topic)
            self.task_context_manager.remove_context(
                f"{task_id_from_topic}_stream_buffer"
            )
            return False

        try:
            await self._process_parsed_a2a_event(
                parsed_event_obj,
                external_request_context,
                task_id_from_topic,
                original_rpc_id,
            )
            return True
        except Exception as e:
            log.exception(
                "%s Error in _process_parsed_a2a_event for task %s: %s",
                self.log_identifier,
                task_id_from_topic,
                e,
            )
            error_obj = JSONRPCError(
                code=-32000, message=f"Gateway processing error: {e}"
            )
            await self._send_error_to_external(external_request_context, error_obj)
            self.task_context_manager.remove_context(task_id_from_topic)
            self.task_context_manager.remove_context(
                f"{task_id_from_topic}_stream_buffer"
            )
            return False

    async def _async_setup_and_run(self) -> None:
        """Main async logic for the gateway component."""
        # Call base class to initialize Trust Manager
        await super()._async_setup_and_run()

        if self._gateway_card_publishing_config.get("enabled", True):
            self._start_gateway_card_publishing()

        log.info(
            "%s Starting _start_listener() to initiate external platform connection.",
            self.log_identifier,
        )
        self._start_listener()

        await self._message_processor_loop()

    def _pre_async_cleanup(self) -> None:
        """Pre-cleanup actions for the gateway component."""
        # Cleanup Trust Manager if present (ENTERPRISE FEATURE)
        if self.trust_manager:
            try:
                log.info("%s Cleaning up Trust Manager...", self.log_identifier)
                self.trust_manager.cleanup(self.cancel_timer)
                log.info("%s Trust Manager cleanup complete", self.log_identifier)
            except Exception as e:
                log.error(
                    "%s Error during Trust Manager cleanup: %s", self.log_identifier, e
                )

        log.info("%s Calling _stop_listener()...", self.log_identifier)
        self._stop_listener()

        if self.internal_event_queue:
            log.info(
                "%s Signaling _message_processor_loop to stop by putting sentinel on queue...",
                self.log_identifier,
            )
            # This unblocks the `self.internal_event_queue.get()` call in the loop
            self.internal_event_queue.put(None)

    async def _message_processor_loop(self):
        log.debug("%s Starting message processor loop as an asyncio task...", self.log_identifier)
        loop = self.get_async_loop()

        while not self.stop_signal.is_set():
            original_broker_message: Optional[SolaceMessage] = None
            item = None
            processed_successfully = False
            topic = None

            try:
                item = await loop.run_in_executor(None, self.internal_event_queue.get)

                if item is None:
                    log.info(
                        "%s Received shutdown sentinel. Exiting message processor loop.",
                        self.log_identifier,
                    )
                    break

                topic = item.get("topic")
                payload = item.get("payload")
                original_broker_message = item.get("_original_broker_message")

                if not topic or payload is None or not original_broker_message:
                    log.warning(
                        "%s Invalid item received from internal queue: %s",
                        self.log_identifier,
                        item,
                    )
                    processed_successfully = False
                    continue

                if a2a.topic_matches_subscription(
                    topic, a2a.get_discovery_subscription_topic(self.namespace)
                ):
                    processed_successfully = await self._handle_discovery_message(
                        payload
                    )
                elif (
                    hasattr(self, "trust_manager")
                    and self.trust_manager
                    and self.trust_manager.is_trust_card_topic(topic)
                ):
                    await self.trust_manager.handle_trust_card_message(payload, topic)
                    processed_successfully = True
                elif a2a.topic_matches_subscription(
                    topic,
                    a2a.get_gateway_response_subscription_topic(
                        self.namespace, self.gateway_id
                    ),
                ) or a2a.topic_matches_subscription(
                    topic,
                    a2a.get_gateway_status_subscription_topic(
                        self.namespace, self.gateway_id
                    ),
                ):
                    task_id_from_topic: Optional[str] = None
                    response_sub = a2a.get_gateway_response_subscription_topic(
                        self.namespace, self.gateway_id
                    )
                    status_sub = a2a.get_gateway_status_subscription_topic(
                        self.namespace, self.gateway_id
                    )

                    if a2a.topic_matches_subscription(topic, response_sub):
                        task_id_from_topic = a2a.extract_task_id_from_topic(
                            topic, response_sub, self.log_identifier
                        )
                    elif a2a.topic_matches_subscription(topic, status_sub):
                        task_id_from_topic = a2a.extract_task_id_from_topic(
                            topic, status_sub, self.log_identifier
                        )

                    if task_id_from_topic:
                        processed_successfully = await self._handle_agent_event(
                            topic, payload, task_id_from_topic
                        )
                    else:
                        log.error(
                            "%s Could not extract task_id from topic %s for _handle_agent_event. Ignoring.",
                            self.log_identifier,
                            topic,
                        )
                        processed_successfully = False
                else:
                    log.warning(
                        "%s Received message on unhandled topic: %s. Acknowledging.",
                        self.log_identifier,
                        topic,
                    )
                    processed_successfully = True

            except queue.Empty:
                continue
            except asyncio.CancelledError:
                log.info("%s Message processor loop cancelled.", self.log_identifier)
                break
            except Exception as e:
                log.exception(
                    "%s Unhandled error in message processor loop: %s",
                    self.log_identifier,
                    e,
                )
                processed_successfully = False
                await asyncio.sleep(1)
            finally:
                if original_broker_message:
                    if processed_successfully:
                        original_broker_message.call_acknowledgements()
                    else:
                        original_broker_message.call_negative_acknowledgements()
                        log.warning(
                            "%s NACKed SolaceMessage for topic: %s",
                            self.log_identifier,
                            topic or "unknown",
                        )

                if item and item is not None:
                    self.internal_event_queue.task_done()

        log.info("%s Message processor loop finished.", self.log_identifier)

    @abstractmethod
    async def _extract_initial_claims(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the primary identity claims from a platform-specific event.
        This method MUST be implemented by derived gateway components.

        Args:
            external_event_data: Raw event data from the external platform
                                 (e.g., FastAPIRequest, Slack event dictionary).

        Returns:
            A dictionary of initial claims, which MUST include an 'id' key.
            Example: {"id": "user@example.com", "source": "slack_api"}
            Return None if authentication fails.
        """
        pass

    @abstractmethod
    async def _translate_external_input(
        self, external_event: Any
    ) -> Tuple[str, List[ContentPart], Dict[str, Any]]:
        """
        Translates raw platform-specific event data into A2A task parameters.

        Args:
            external_event: Raw event data from the external platform
                            (e.g., FastAPIRequest, Slack event dictionary).

        Returns:
            A tuple containing:
            - target_agent_name (str): The name of the A2A agent to target.
            - a2a_parts (List[ContentPart]): A list of A2A Part objects.
            - external_request_context (Dict[str, Any]): Context for TaskContextManager.
        """
        pass

    @abstractmethod
    def _start_listener(self) -> None:
        pass

    @abstractmethod
    def _stop_listener(self) -> None:
        pass

    @abstractmethod
    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        pass

    @abstractmethod
    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        pass

    @abstractmethod
    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        pass

    def _detect_gateway_type(self) -> str:
        """Auto-detect gateway type from component class or configuration."""
        configured_type = self.get_config("gateway_type")
        if configured_type:
            return configured_type

        class_name = self.__class__.__name__
        if "WebUI" in class_name or "HttpSse" in class_name:
            return "http_sse"

        if hasattr(self, 'adapter') and self.adapter:
            adapter_name = self.adapter.__class__.__name__.lower()
            if "rest" in adapter_name:
                return "rest"
            if "slack" in adapter_name:
                return "slack"
            if "teams" in adapter_name:
                return "teams"

        return "generic"

    def _build_gateway_card(self) -> AgentCard:
        """Build gateway discovery card as AgentCard with gateway extension."""
        from a2a.types import AgentCapabilities, AgentExtension

        gateway_type = self._detect_gateway_type()
        gateway_url = f"solace:{self.namespace}/a2a/v1/gateway/request/{self.gateway_id}"
        description = self._gateway_card_config.get(
            "description",
            f"{gateway_type.upper()} Gateway"
        )

        gateway_role_extension = AgentExtension(
            uri="https://solace.com/a2a/extensions/sam/gateway-role",
            required=False,
            params={
                "gateway_id": self.gateway_id,
                "gateway_type": gateway_type,
                "namespace": self.namespace,
            }
        )

        extensions = [gateway_role_extension]

        deployment_config = self.get_config("deployment", {})
        deployment_id = deployment_config.get("id") if isinstance(deployment_config, dict) else None
        if deployment_id:
            deployment_extension = AgentExtension(
                uri="https://solace.com/a2a/extensions/sam/deployment",
                required=False,
                params={
                    "deployment_id": deployment_id,
                }
            )
            extensions.append(deployment_extension)

        try:
            from solace_agent_mesh import __version__ as sam_version
        except ImportError:
            sam_version = "unknown"

        gateway_card = AgentCard(
            name=self.gateway_id,
            url=gateway_url,
            description=description,
            version=sam_version,
            protocol_version="1.0",
            capabilities=AgentCapabilities(
                supports_streaming=True,
                supports_cancellation=True,
                extensions=extensions
            ),
            default_input_modes=self._gateway_card_config.get("defaultInputModes", ["text"]),
            default_output_modes=self._gateway_card_config.get("defaultOutputModes", ["text"]),
            skills=self._gateway_card_config.get("skills", []),
        )

        return gateway_card

    def _publish_gateway_card(self) -> None:
        """Publish gateway card to gateway discovery topic."""
        try:
            gateway_card = self._build_gateway_card()
            discovery_topic = a2a.get_gateway_discovery_topic(self.namespace)

            payload = gateway_card.model_dump(by_alias=True, exclude_none=True)
            self.publish_a2a_message(payload, discovery_topic)

            log.debug(
                "%s Published gateway card: gateway_id=%s, type=%s, topic=%s",
                self.log_identifier,
                self.gateway_id,
                self._detect_gateway_type(),
                discovery_topic
            )
        except Exception as e:
            log.error(
                "%s Failed to publish gateway card: %s",
                self.log_identifier,
                e,
                exc_info=True
            )

    def _start_gateway_card_publishing(self) -> None:
        """Start periodic gateway card publishing."""
        interval_seconds = self._gateway_card_publishing_config.get("interval_seconds", 30)

        if interval_seconds <= 0:
            log.info(
                "%s Gateway card publishing disabled (interval_seconds=%d)",
                self.log_identifier,
                interval_seconds
            )
            return

        log.info(
            "%s Starting gateway card publishing every %d seconds",
            self.log_identifier,
            interval_seconds
        )

        SamComponentBase.add_timer(
            self,
            delay_ms=1000,
            timer_id=self._gateway_card_timer_id,
            interval_ms=interval_seconds * 1000,
            callback=lambda timer_data: self._publish_gateway_card()
        )

    def _get_component_id(self) -> str:
        """Returns the gateway ID as the component identifier."""
        return self.gateway_id

    def _get_component_type(self) -> str:
        """Returns 'gateway' as the component type."""
        return "gateway"

    def invoke(self, message, data):
        if isinstance(message, SolaceMessage):
            message.call_acknowledgements()
        log.warning("%s Invoke method called unexpectedly.", self.log_identifier)
        return None
