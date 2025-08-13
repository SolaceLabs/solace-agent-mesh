"""
Base Component class for Gateway implementations in the Solace AI Connector.
"""

import asyncio
import queue
import re
import threading
import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple, Union
from urllib.parse import urlparse, parse_qs

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from google.adk.artifacts import BaseArtifactService

from ...common.agent_registry import AgentRegistry
from ...core_a2a.service import CoreA2AService
from ...agent.adk.services import initialize_artifact_service
from ...common.services.identity_service import (
    BaseIdentityService,
    create_identity_service,
)
from .task_context import TaskContextManager
from ...common.types import (
    Part as A2APart,
    Message as A2AMessage,
    AgentCard,
    JSONRPCResponse,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    TextPart,
    TaskStatus,
    TaskState,
    FilePart,
    DataPart,
    Artifact as A2AArtifact,
)
from ...common.a2a_protocol import (
    get_gateway_response_topic,
    get_gateway_response_subscription_topic,
    get_gateway_status_topic,
    get_gateway_status_subscription_topic,
    get_discovery_topic,
    _topic_matches_subscription,
    _subscription_to_regex,
)
from ...common.utils import is_text_based_mime_type
from ...common.utils.embeds import (
    resolve_embeds_in_string,
    resolve_embeds_recursively_in_string,
    evaluate_embed,
    LATE_EMBED_TYPES,
    EARLY_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)
from solace_ai_connector.common.message import (
    Message as SolaceMessage,
)
from solace_ai_connector.common.event import Event, EventType
from abc import abstractmethod

from ...common.middleware.registry import MiddlewareRegistry
from ...agent.utils.artifact_helpers import (
    load_artifact_content_or_metadata,
)

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


class BaseGatewayComponent(ComponentBase):
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

    def __init__(self, **kwargs: Any):
        super().__init__(info, **kwargs)
        log.info("%s Initializing Base Gateway Component...", self.log_identifier)

        try:
            self.namespace: str = self.get_config("namespace")
            self.gateway_id: str = self.get_config("gateway_id")
            if not self.namespace or not self.gateway_id:
                raise ValueError(
                    "Namespace and Gateway ID must be configured in the app_config."
                )

            self.enable_embed_resolution: bool = self.get_config(
                "enable_embed_resolution", True
            )
            self.gateway_max_artifact_resolve_size_bytes: int = self.get_config(
                "gateway_max_artifact_resolve_size_bytes"
            )
            self.gateway_recursive_embed_depth: int = self.get_config(
                "gateway_recursive_embed_depth"
            )
            self.gateway_artifact_content_limit_bytes: int = self.get_config(
                "gateway_artifact_content_limit_bytes"
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
        self.core_a2a_service: CoreA2AService = CoreA2AService(
            agent_registry=self.agent_registry, namespace=self.namespace
        )
        self.shared_artifact_service: Optional[BaseArtifactService] = (
            initialize_artifact_service(self)
        )

        self.task_context_manager: TaskContextManager = TaskContextManager()
        self.internal_event_queue: queue.Queue = queue.Queue()
        self.message_processor_thread: Optional[threading.Thread] = None
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None
        self.async_thread: Optional[threading.Thread] = None

        identity_service_config = self.get_config("identity_service")
        self.identity_service: Optional[BaseIdentityService] = create_identity_service(
            identity_service_config
        )

        self._config_resolver = MiddlewareRegistry.get_config_resolver()
        log.info(
            "%s Middleware system initialized (using default configuration resolver).",
            self.log_identifier,
        )

        log.info(
            "%s Base Gateway Component initialized successfully.", self.log_identifier
        )

    def publish_a2a_message(
        self, topic: str, payload: Dict, user_properties: Optional[Dict] = None
    ) -> None:
        log.debug(
            "%s Publishing A2A message to topic: %s via App", self.log_identifier, topic
        )
        try:
            app = self.get_app()
            if app:
                app.send_message(
                    payload=payload, topic=topic, user_properties=user_properties
                )
                log.debug(
                    "%s Successfully published message to %s via App",
                    self.log_identifier,
                    topic,
                )
            else:
                log.error(
                    "%s Cannot publish message: Not running within a SAC App context.",
                    self.log_identifier,
                )
                raise RuntimeError(
                    "Cannot publish message: Not running within a SAC App context."
                )
        except Exception as e:
            log.exception(
                "%s Failed to publish A2A message to topic %s via App: %s",
                self.log_identifier,
                topic,
                e,
            )
            raise

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
        a2a_parts: List[A2APart],
        external_request_context: Dict[str, Any],
        user_identity: Any,
        is_streaming: bool = True,
        api_version: str = "v2",
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
        gateway_context = {"gateway_id": self.gateway_id}

        try:
            user_config = await config_resolver.resolve_user_config(
                user_identity, gateway_context, {}
            )
            log.info(
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

        external_request_context["user_identity"] = user_identity
        external_request_context["a2a_user_config"] = user_config
        external_request_context["api_version"] = api_version
        log.debug(
            "%s Stored user_identity, configuration, and api_version (%s) in external_request_context.",
            log_id_prefix,
            api_version,
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

        if not a2a_session_id:
            a2a_session_id = f"gdk-session-{uuid.uuid4().hex}"
            log.warning(
                "%s 'a2a_session_id' not found in external_request_context, generated: %s",
                self.log_identifier,
                a2a_session_id,
            )
            external_request_context["a2a_session_id"] = a2a_session_id

        a2a_metadata = {}
        invoked_artifacts = external_request_context.get("invoked_with_artifacts")
        if invoked_artifacts:
            a2a_metadata["invoked_with_artifacts"] = invoked_artifacts
            log.debug(
                "%s Found %d artifact identifiers in external context to pass to agent.",
                log_id_prefix,
                len(invoked_artifacts),
            )

        a2a_message = A2AMessage(role="user", parts=a2a_parts, metadata=a2a_metadata)
        reply_topic_pattern = get_gateway_response_topic(
            self.namespace, self.gateway_id, "{task_id}"
        )
        status_topic_pattern = get_gateway_status_topic(
            self.namespace, self.gateway_id, "{task_id}"
        )

        task_metadata_override: Dict[str, Any] = {}
        system_purpose = self.get_config("system_purpose", "")
        response_format = self.get_config("response_format", "")

        if system_purpose:
            task_metadata_override["system_purpose"] = system_purpose
            log.debug("%s Adding system_purpose to task metadata.", log_id_prefix)
        if response_format:
            task_metadata_override["response_format"] = response_format
            log.debug("%s Adding response_format to task metadata.", log_id_prefix)

        if is_streaming:
            target_topic, payload, user_properties = (
                self.core_a2a_service.submit_streaming_task(
                    agent_name=target_agent_name,
                    a2a_message=a2a_message,
                    session_id=a2a_session_id,
                    client_id=self.gateway_id,
                    reply_to_topic=reply_topic_pattern,
                    status_to_topic=status_topic_pattern,
                    user_id=user_id_for_a2a,
                    a2a_user_config=user_config,
                    metadata_override=task_metadata_override,
                )
            )
        else:
            target_topic, payload, user_properties = self.core_a2a_service.submit_task(
                agent_name=target_agent_name,
                a2a_message=a2a_message,
                session_id=a2a_session_id,
                client_id=self.gateway_id,
                reply_to_topic=reply_topic_pattern,
                user_id=user_id_for_a2a,
                a2a_user_config=user_config,
                metadata_override=task_metadata_override,
            )

        task_id = payload.get("params", {}).get("id")
        if not task_id:
            log.error(
                "%s CoreA2AService did not return a task ID in the payload.",
                log_id_prefix,
            )
            raise ValueError("CoreA2AService did not return a task ID in the payload.")

        if user_properties is None:
            user_properties = {}

        user_properties["replyTo"] = get_gateway_response_topic(
            self.namespace, self.gateway_id, task_id
        )
        if is_streaming:
            user_properties["a2aStatusTopic"] = get_gateway_status_topic(
                self.namespace, self.gateway_id, task_id
            )

        self.task_context_manager.store_context(task_id, external_request_context)
        log.info("%s Stored external context for task_id: %s", log_id_prefix, task_id)

        self.publish_a2a_message(
            topic=target_topic, payload=payload, user_properties=user_properties
        )
        log.info(
            "%s Submitted A2A task %s to agent %s. Streaming: %s",
            log_id_prefix,
            task_id,
            target_agent_name,
            is_streaming,
        )
        return task_id

    def process_event(self, event: Event):
        if event.event_type == EventType.MESSAGE:
            original_broker_message: Optional[SolaceMessage] = event.data
            if not original_broker_message:
                log.warning(
                    "%s Received MESSAGE event with no data. Ignoring.",
                    self.log_identifier,
                )
                return

            log.debug(
                "%s Received SolaceMessage on topic: %s. Bridging to internal queue.",
                self.log_identifier,
                original_broker_message.get_topic(),
            )
            try:
                msg_data_for_processor = {
                    "topic": original_broker_message.get_topic(),
                    "payload": original_broker_message.get_payload(),
                    "user_properties": original_broker_message.get_user_properties(),
                    "_original_broker_message": original_broker_message,
                }
                self.internal_event_queue.put_nowait(msg_data_for_processor)
            except queue.Full:
                log.error(
                    "%s Internal event queue full. Cannot bridge message. NACKing.",
                    self.log_identifier,
                )
                original_broker_message.call_negative_acknowledgements()
            except Exception as e:
                log.exception(
                    "%s Error bridging message to internal queue: %s. NACKing.",
                    self.log_identifier,
                    e,
                )
                original_broker_message.call_negative_acknowledgements()
        else:
            log.debug(
                "%s Received non-MESSAGE event type: %s. Passing to super.",
                self.log_identifier,
                event.event_type,
            )
            super().process_event(event)

    async def _handle_resolved_signals(
        self,
        external_request_context: Dict,
        signals: List[Tuple[int, Any]],
        original_rpc_id: Optional[str],
        is_finalizing_context: bool = False,
    ):
        log_id_prefix = f"{self.log_identifier}[SignalHandler]"
        if not signals:
            return

        for _, signal_tuple in signals:
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
                        signal_data_part = DataPart(
                            data={"type": "agent_status", "text": status_text},
                            metadata={"source": "agent_progress_update"},
                        )
                        signal_a2a_message = A2AMessage(
                            role="agent", parts=[signal_data_part]
                        )
                        signal_task_status = TaskStatus(
                            state=TaskState.WORKING, message=signal_a2a_message
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

                        signal_event = TaskStatusUpdateEvent(
                            id=a2a_task_id_for_signal,
                            status=signal_task_status,
                            final=False,
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
                else:
                    log.warning(
                        "%s Received unhandled signal type during embed resolution: %s",
                        log_id_prefix,
                        signal_type,
                    )

    async def _resolve_uri_in_file_part(self, part: A2APart):
        """
        Checks if a part is a FilePart with a resolvable URI and, if so,
        resolves it and mutates the part in-place.
        """
        if not (
            isinstance(part, FilePart)
            and part.file
            and part.file.uri
            and part.file.uri.startswith("artifact://")
        ):
            return

        if not self.shared_artifact_service:
            log.warning(
                "%s Cannot resolve artifact URI, shared_artifact_service is not configured.",
                self.log_identifier,
            )
            return

        uri = part.file.uri
        log_id_prefix = f"{self.log_identifier}[ResolveURI]"
        try:
            log.info("%s Found artifact URI to resolve: %s", log_id_prefix, uri)
            parsed_uri = urlparse(uri)
            app_name = parsed_uri.netloc
            path_parts = parsed_uri.path.strip("/").split("/")

            if not app_name or len(path_parts) != 3:
                raise ValueError(
                    "Invalid URI structure. Expected artifact://app_name/user_id/session_id/filename"
                )

            user_id, session_id, filename = path_parts
            version = int(parse_qs(parsed_uri.query).get("version", [None])[0])

            loaded_artifact = await load_artifact_content_or_metadata(
                artifact_service=self.shared_artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                version=version,
                return_raw_bytes=True,
            )

            if loaded_artifact.get("status") == "success":
                content_bytes = loaded_artifact.get("raw_bytes")
                part.file.bytes = base64.b64encode(content_bytes).decode("utf-8")
                part.file.uri = None
                log.info(
                    "%s Successfully resolved and embedded artifact: %s",
                    log_id_prefix,
                    uri,
                )
            else:
                log.error(
                    "%s Failed to resolve artifact URI '%s': %s",
                    log_id_prefix,
                    uri,
                    loaded_artifact.get("message"),
                )
        except Exception as e:
            log.exception(
                "%s Error resolving artifact URI '%s': %s", log_id_prefix, uri, e
            )

    async def _resolve_uris_in_parts_list(self, parts: List[A2APart]):
        """Iterates over a list of A2APart objects and resolves any FilePart URIs."""
        if not parts:
            return
        for part in parts:
            await self._resolve_uri_in_file_part(part)

    async def _resolve_uris_in_payload(self, parsed_event: Any):
        """
        Dispatcher that calls the appropriate targeted URI resolver based on the
        Pydantic model type of the event.
        """
        if isinstance(parsed_event, TaskStatusUpdateEvent):
            if parsed_event.status and parsed_event.status.message:
                await self._resolve_uris_in_parts_list(
                    parsed_event.status.message.parts
                )
        elif isinstance(parsed_event, TaskArtifactUpdateEvent):
            if parsed_event.artifact:
                await self._resolve_uris_in_parts_list(parsed_event.artifact.parts)
        elif isinstance(parsed_event, Task):
            if parsed_event.status and parsed_event.status.message:
                await self._resolve_uris_in_parts_list(
                    parsed_event.status.message.parts
                )
            if parsed_event.artifacts:
                for artifact in parsed_event.artifacts:
                    await self._resolve_uris_in_parts_list(artifact.parts)
        else:
            log.debug(
                "%s Payload type '%s' does not support targeted URI resolution. Skipping.",
                self.log_identifier,
                type(parsed_event).__name__,
            )

    async def _handle_discovery_message(self, payload: Dict) -> bool:
        """Handles incoming agent discovery messages."""
        try:
            agent_card = AgentCard(**payload)
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

    def _extract_task_id_from_topic(
        self, topic: str, subscription_pattern: str
    ) -> Optional[str]:
        """Extracts the task ID from the end of a topic string based on the subscription."""
        base_regex_str = _subscription_to_regex(subscription_pattern).replace(r".*", "")
        match = re.match(base_regex_str, topic)
        if match:
            task_id_part = topic[match.end() :]
            task_id = task_id_part.lstrip("/")
            if task_id:
                log.debug(
                    "%s Extracted Task ID '%s' from topic '%s'",
                    self.log_identifier,
                    task_id,
                    topic,
                )
                return task_id
        log.warning(
            "%s Could not extract Task ID from topic '%s' using pattern '%s'",
            self.log_identifier,
            topic,
            subscription_pattern,
        )
        return None

    def _parse_a2a_event_from_rpc_result(
        self, rpc_result: Dict, expected_task_id: Optional[str]
    ) -> Optional[Union[Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent]]:
        """
        Parses the result field of a JSONRPCResponse into a specific A2A Pydantic model.
        Verifies task ID if expected_task_id is provided.
        """
        if not isinstance(rpc_result, dict):
            log.error(
                "%s RPC result is not a dictionary. Cannot parse.", self.log_identifier
            )
            return None

        actual_task_id = rpc_result.get("id")
        if expected_task_id and actual_task_id != expected_task_id:
            log.error(
                "%s Task ID mismatch! Expected: %s, Got from payload: %s.",
                self.log_identifier,
                expected_task_id,
                actual_task_id,
            )
            return None

        try:
            if "status" in rpc_result and "final" in rpc_result:
                return TaskStatusUpdateEvent(**rpc_result)
            elif "artifact" in rpc_result:
                return TaskArtifactUpdateEvent(**rpc_result)
            elif "status" in rpc_result and "sessionId" in rpc_result:
                return Task(**rpc_result)
            else:
                log.warning(
                    "%s Unknown result structure in RPC response for task %s: %s",
                    self.log_identifier,
                    actual_task_id or "unknown",
                    rpc_result,
                )
                return None
        except Exception as e:
            log.error(
                "%s Failed to parse RPC result into A2A Pydantic model for task %s: %s. Result: %s",
                self.log_identifier,
                actual_task_id or "unknown",
                e,
                rpc_result,
            )
            return None

    async def _resolve_embeds_and_handle_signals(
        self,
        event_with_parts: Union[TaskStatusUpdateEvent, Task, TaskArtifactUpdateEvent],
        external_request_context: Dict[str, Any],
        a2a_task_id: str,
        original_rpc_id: Optional[str],
        is_finalizing_context: bool = False,
    ) -> bool:
        """
        Resolves embeds and handles signals for an event containing parts.
        Modifies event_with_parts in place if text content changes.
        Manages stream buffer for TaskStatusUpdateEvent.
        Returns True if the event content was modified or signals were handled, False otherwise.
        """
        if not self.enable_embed_resolution:
            return False

        log_id_prefix = f"{self.log_identifier}[EmbedResolve:{a2a_task_id}]"
        content_modified_or_signal_handled = False

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
        is_streaming_status_update = isinstance(event_with_parts, TaskStatusUpdateEvent)

        if isinstance(event_with_parts, (TaskStatusUpdateEvent, Task)):
            if event_with_parts.status and event_with_parts.status.message:
                parts_owner = event_with_parts.status.message
        elif isinstance(event_with_parts, TaskArtifactUpdateEvent):
            if event_with_parts.artifact:
                parts_owner = event_with_parts.artifact

        if parts_owner and parts_owner.parts:
            new_parts_for_owner: List[A2APart] = []
            stream_buffer_key = f"{a2a_task_id}_stream_buffer"
            current_buffer = ""

            if is_streaming_status_update:
                current_buffer = (
                    self.task_context_manager.get_context(stream_buffer_key) or ""
                )

            for part_obj in parts_owner.parts:
                if isinstance(part_obj, TextPart) and part_obj.text is not None:
                    text_to_resolve = part_obj.text
                    original_part_text = part_obj.text

                    if is_streaming_status_update:
                        current_buffer += part_obj.text
                        text_to_resolve = current_buffer

                    resolved_text, processed_idx, signals = (
                        await resolve_embeds_in_string(
                            text=text_to_resolve,
                            context=embed_eval_context,
                            resolver_func=evaluate_embed,
                            types_to_resolve=LATE_EMBED_TYPES.copy(),
                            log_identifier=log_id_prefix,
                            config=embed_eval_config,
                        )
                    )

                    if signals:
                        await self._handle_resolved_signals(
                            external_request_context,
                            signals,
                            original_rpc_id,
                            is_finalizing_context,
                        )
                        content_modified_or_signal_handled = True

                    if resolved_text is not None:
                        new_parts_for_owner.append(TextPart(text=resolved_text))
                        if is_streaming_status_update:
                            if resolved_text != text_to_resolve[:processed_idx]:
                                content_modified_or_signal_handled = True
                        elif resolved_text != original_part_text:
                            content_modified_or_signal_handled = True

                    if is_streaming_status_update:
                        current_buffer = text_to_resolve[processed_idx:]
                    elif (
                        processed_idx < len(text_to_resolve)
                        and not content_modified_or_signal_handled
                    ):
                        log.warning(
                            "%s Unclosed embed in non-streaming TextPart. Remainder: '%s'",
                            log_id_prefix,
                            text_to_resolve[processed_idx:],
                        )
                        content_modified_or_signal_handled = True

                elif (
                    isinstance(part_obj, FilePart)
                    and part_obj.file
                    and part_obj.file.bytes
                ):
                    mime_type = part_obj.file.mimeType or ""
                    is_container = is_text_based_mime_type(mime_type)
                    try:
                        decoded_content_for_check = base64.b64decode(
                            part_obj.file.bytes
                        ).decode("utf-8", errors="ignore")
                        if (
                            is_container
                            and EMBED_DELIMITER_OPEN in decoded_content_for_check
                        ):
                            original_content = decoded_content_for_check
                            resolved_content = (
                                await resolve_embeds_recursively_in_string(
                                    text=original_content,
                                    context=embed_eval_context,
                                    resolver_func=evaluate_embed,
                                    types_to_resolve=LATE_EMBED_TYPES,
                                    log_identifier=log_id_prefix,
                                    config=embed_eval_config,
                                    max_depth=self.gateway_recursive_embed_depth,
                                )
                            )
                            if resolved_content != original_content:
                                new_file_content = part_obj.file.model_copy()
                                new_file_content.bytes = base64.b64encode(
                                    resolved_content.encode("utf-8")
                                ).decode("utf-8")
                                new_parts_for_owner.append(
                                    FilePart(
                                        file=new_file_content,
                                        metadata=part_obj.metadata,
                                    )
                                )
                                content_modified_or_signal_handled = True
                            else:
                                new_parts_for_owner.append(part_obj)
                        else:
                            new_parts_for_owner.append(part_obj)
                    except Exception as e:
                        log.warning(
                            "%s Error during recursive FilePart resolution for %s: %s. Using original.",
                            log_id_prefix,
                            part_obj.file.name,
                            e,
                        )
                        new_parts_for_owner.append(part_obj)
                else:
                    new_parts_for_owner.append(part_obj)

            parts_owner.parts = new_parts_for_owner

            if is_streaming_status_update:
                self.task_context_manager.store_context(
                    stream_buffer_key, current_buffer
                )

        return content_modified_or_signal_handled

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

            if self.get_config("resolve_artifact_uris_in_gateway", False):
                log.debug(
                    "%s Resolving artifact URIs before sending to external...",
                    log_id_prefix,
                )
                await self._resolve_uris_in_payload(parsed_event)

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

            send_this_event_to_external = True
            is_final_chunk_of_status_update = False

            if isinstance(parsed_event, TaskStatusUpdateEvent):
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
                    combined_text = ""
                    non_text_parts = []
                    for part in parsed_event.status.message.parts:
                        if isinstance(part, TextPart) and part.text:
                            combined_text += part.text
                        else:
                            non_text_parts.append(part)

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
                            [TextPart(text=resolved_text)] if resolved_text else []
                        )
                        new_parts.extend(non_text_parts)
                        parsed_event.status.message.parts = new_parts
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
                        "gateway_artifact_content_limit_bytes": self.gateway_artifact_content_limit_bytes,
                        "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
                    }
                    resolved_remaining_text, _, signals = (
                        await resolve_embeds_in_string(
                            remaining_buffer,
                            embed_eval_context,
                            evaluate_embed,
                            LATE_EMBED_TYPES.copy(),
                            log_id_prefix,
                            embed_eval_config,
                        )
                    )
                    await self._handle_resolved_signals(
                        external_request_context,
                        signals,
                        original_rpc_id,
                        is_finalizing_context=True,
                    )
                    if resolved_remaining_text:
                        flush_status = TaskStatus(
                            state=TaskState.WORKING,
                            message=A2AMessage(
                                role="agent",
                                parts=[TextPart(text=resolved_remaining_text)],
                            ),
                        )
                        flush_event = TaskStatusUpdateEvent(
                            id=a2a_task_id,
                            status=flush_status,
                            final=False,
                        )
                        await self._send_update_to_external(
                            external_request_context, flush_event, True
                        )
                    self.task_context_manager.remove_context(final_buffer_key)

            if send_this_event_to_external:
                if isinstance(parsed_event, Task):
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
            rpc_response = JSONRPCResponse(**payload)
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

        original_rpc_id = str(rpc_response.id)

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
        if rpc_response.error:
            parsed_event_obj = rpc_response.error
        elif rpc_response.result:
            parsed_event_obj = self._parse_a2a_event_from_rpc_result(
                rpc_response.result, task_id_from_topic
            )

        if not parsed_event_obj:
            log.error(
                "%s Failed to parse or validate A2A event from RPC result for task %s. Result: %s",
                self.log_identifier,
                task_id_from_topic,
                rpc_response.result,
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

    async def _message_processor_loop(self):
        log.info("%s Starting message processor loop...", self.log_identifier)
        loop = asyncio.get_running_loop()

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

                if _topic_matches_subscription(
                    topic, get_discovery_topic(self.namespace)
                ):
                    processed_successfully = await self._handle_discovery_message(
                        payload
                    )
                elif _topic_matches_subscription(
                    topic,
                    get_gateway_response_subscription_topic(
                        self.namespace, self.gateway_id
                    ),
                ) or _topic_matches_subscription(
                    topic,
                    get_gateway_status_subscription_topic(
                        self.namespace, self.gateway_id
                    ),
                ):
                    task_id_from_topic: Optional[str] = None
                    response_sub = get_gateway_response_subscription_topic(
                        self.namespace, self.gateway_id
                    )
                    status_sub = get_gateway_status_subscription_topic(
                        self.namespace, self.gateway_id
                    )

                    if _topic_matches_subscription(topic, response_sub):
                        task_id_from_topic = self._extract_task_id_from_topic(
                            topic, response_sub
                        )
                    elif _topic_matches_subscription(topic, status_sub):
                        task_id_from_topic = self._extract_task_id_from_topic(
                            topic, status_sub
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

    def _run_async_operations(self):
        log.info(
            "%s Initializing asyncio event loop in dedicated thread...",
            self.log_identifier,
        )
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)

        processor_task = None
        try:
            log.info(
                "%s Starting _message_processor_loop as an asyncio task.",
                self.log_identifier,
            )
            processor_task = self.async_loop.create_task(self._message_processor_loop())

            log.info(
                "%s Calling _start_listener() to initiate external platform connection.",
                self.log_identifier,
            )
            self._start_listener()

            log.info(
                "%s Running asyncio event loop forever (or until stop_signal).",
                self.log_identifier,
            )
            self.async_loop.run_forever()

        except Exception as e:
            log.exception(
                "%s Unhandled exception in _run_async_operations: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
        finally:
            if processor_task and not processor_task.done():
                log.info(
                    "%s Cancelling _message_processor_loop task.", self.log_identifier
                )
                processor_task.cancel()
                try:
                    self.async_loop.run_until_complete(
                        asyncio.gather(processor_task, return_exceptions=True)
                    )
                except RuntimeError as loop_err:
                    log.warning(
                        "%s Error awaiting processor task during cleanup (loop closed?): %s",
                        self.log_identifier,
                        loop_err,
                    )

            if self.async_loop.is_running():
                log.info(
                    "%s Stopping asyncio event loop from _run_async_operations finally block.",
                    self.log_identifier,
                )
                self.async_loop.stop()
            log.info(
                "%s Async operations loop finished in dedicated thread.",
                self.log_identifier,
            )

    def run(self):
        log.info("%s Starting BaseGatewayComponent run method.", self.log_identifier)
        if not self.async_thread or not self.async_thread.is_alive():
            self.async_thread = threading.Thread(
                target=self._run_async_operations,
                name=f"{self.name}_AsyncOpsThread",
                daemon=True,
            )
            self.async_thread.start()
            log.info("%s Async operations thread started.", self.log_identifier)
        else:
            log.warning(
                "%s Async operations thread already running.", self.log_identifier
            )

        super().run()
        log.info("%s BaseGatewayComponent run method finished.", self.log_identifier)

    def cleanup(self):
        log.info("%s Starting cleanup for BaseGatewayComponent...", self.log_identifier)

        log.info("%s Calling _stop_listener()...", self.log_identifier)
        try:
            if (
                self.async_loop
                and not self.async_loop.is_running()
                and self.async_thread
                and self.async_thread.is_alive()
            ):
                log.warning(
                    "%s Async loop not running during cleanup, _stop_listener might face issues if it needs the loop.",
                    self.log_identifier,
                )
            self._stop_listener()
        except Exception as e:
            log.exception(
                "%s Error during _stop_listener(): %s", self.log_identifier, e
            )

        if self.internal_event_queue:
            log.info(
                "%s Signaling _message_processor_loop to stop...", self.log_identifier
            )
            self.internal_event_queue.put(None)

        if self.async_loop and self.async_loop.is_running():
            log.info("%s Requesting asyncio loop to stop...", self.log_identifier)
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)

        if self.async_thread and self.async_thread.is_alive():
            log.info(
                "%s Joining async operations thread (timeout 10s)...",
                self.log_identifier,
            )
            self.async_thread.join(timeout=10)
            if self.async_thread.is_alive():
                log.warning(
                    "%s Async operations thread did not join cleanly.",
                    self.log_identifier,
                )

        if self.async_loop and not self.async_loop.is_closed():
            if self.async_loop.is_running():
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            log.info(
                "%s Closing asyncio event loop (if not already closed by its thread).",
                self.log_identifier,
            )
            if not self.async_loop.is_running():
                self.async_loop.close()
            else:
                self.async_loop.call_soon_threadsafe(self.async_loop.close)

        super().cleanup()
        log.info("%s BaseGatewayComponent cleanup finished.", self.log_identifier)

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
    def _start_listener(self) -> None:
        pass

    @abstractmethod
    def _stop_listener(self) -> None:
        pass

    @abstractmethod
    def _translate_external_input(
        self, external_event: Any
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
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

    def invoke(self, message, data):
        if isinstance(message, SolaceMessage):
            message.call_acknowledgements()
        log.warning("%s Invoke method called unexpectedly.", self.log_identifier)
        return None
