"""
Solace Agent Mesh - Event Mesh Gateway Plugin: Component Definition
"""

import asyncio
import queue
import uuid
import base64
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import jsonschema
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.transforms.transforms import Transforms
from solace_ai_connector.flow.app import App as SACApp
from solace_ai_connector.components.inputs_outputs.broker_input import (
    BrokerInput,
)
from solace_ai_connector.components.inputs_outputs.broker_output import (
    BrokerOutput,
)
from solace_ai_connector.common.utils import (
    decode_payload,
    encode_payload,
)
from solace_ai_connector.common.event import Event, EventType


from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.common.types import (
    Part as A2APart,
    TextPart,
    FilePart,
    DataPart,
    Task,
    JSONRPCError,
    FileContent,
)

from solace_agent_mesh.common.a2a_protocol import _topic_matches_subscription
from solace_agent_mesh.agent.utils.artifact_helpers import (
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)
from solace_agent_mesh.common.utils import is_text_based_mime_type


info = {
    "class_name": "EventMeshGatewayComponent",
    "description": (
        "Core component for the SAM Event Mesh Gateway. Handles data plane "
        "communication with Solace, message transformation, and A2A task submission."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "description": "Not typically used directly; component reacts to events from its input queue (A2A control plane) or data plane client.",
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used directly; component sends data to Solace data plane or A2A control plane.",
    },
}


class EventMeshGatewayComponent(BaseGatewayComponent):
    """
    Core component for the SAM Event Mesh Gateway.
    - Manages a data plane Solace client (via an internal SAC flow).
    - Subscribes to external Solace topics based on 'event_handlers'.
    - Transforms incoming Solace messages and submits them as A2A tasks.
    - Processes A2A task responses and publishes them back to Solace based on 'output_handlers'.
    """

    _RESOLVE_EMBEDS_IN_FINAL_RESPONSE = True

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        log.info("%s Initializing Event Mesh Gateway Component...", self.log_identifier)

        try:
            self.event_mesh_broker_config: Dict[str, Any] = self.get_config(
                "event_mesh_broker_config"
            )
            self.event_handlers_config: List[Dict[str, Any]] = self.get_config(
                "event_handlers"
            )
            self.output_handlers_config: List[Dict[str, Any]] = self.get_config(
                "output_handlers", []
            )

            if not self.event_mesh_broker_config:
                raise ValueError(
                    "'event_mesh_broker_config' is required and was not found."
                )
            if not self.event_handlers_config:
                raise ValueError("'event_handlers' must be a non-empty list.")

            log.info(
                "%s Event Mesh specific configuration retrieved.", self.log_identifier
            )

            self.output_handler_map: Dict[str, Dict[str, Any]] = {
                handler_conf.get("name"): handler_conf
                for handler_conf in self.output_handlers_config
            }
            self.event_handler_map: Dict[str, Dict[str, Any]] = {
                handler_conf.get("name"): handler_conf
                for handler_conf in self.event_handlers_config
            }
            log.debug(
                "%s Created output_handler_map with %d entries.",
                self.log_identifier,
                len(self.output_handler_map),
            )

            self.output_handler_transforms: Dict[str, Transforms] = {}
            for handler_conf in self.output_handlers_config:
                handler_name = handler_conf.get("name")
                if handler_name:
                    transforms_config = handler_conf.get("output_transforms", [])

                    for transform in transforms_config:
                        if "source_expression" in transform and isinstance(
                            transform["source_expression"], str
                        ):
                            if transform["source_expression"].startswith(
                                "task_response:"
                            ):
                                transform["source_expression"] = transform[
                                    "source_expression"
                                ].replace("task_response:", "input.payload:", 1)

                    self.output_handler_transforms[handler_name] = Transforms(
                        transforms_config,
                        log_identifier=f"{self.log_identifier}[OutputTransform:{handler_name}]",
                    )
            log.debug("%s Initialized output_handler_transforms.", self.log_identifier)

            self.data_plane_internal_app: Optional[SACApp] = None
            self.data_plane_broker_input: Optional[BrokerInput] = None
            self.data_plane_broker_output: Optional[BrokerOutput] = None
            self.data_plane_client_lock = asyncio.Lock()

            self.data_plane_message_queue: queue.Queue = queue.Queue(maxsize=200)
            self.data_plane_processor_task: Optional[asyncio.Task] = None

            log.info(
                "%s Event Mesh Gateway Component initialized successfully.",
                self.log_identifier,
            )

        except Exception as e:
            log.exception(
                "%s Failed to initialize EventMeshGatewayComponent: %s",
                self.log_identifier,
                e,
            )
            raise

    async def _process_file_part_for_output(
        self, part: FilePart, context: Dict, handler_config: Dict
    ) -> Dict:
        file_info = {
            "name": part.file.name,
            "mimeType": part.file.mimeType,
            "content": None,
            "bytes": None,
            "error": None,
        }

        if not part.file.uri:
            file_info["error"] = "FilePart has no URI to load content from."
            return file_info

        max_size = handler_config.get("max_file_size_for_base64_bytes", 1048576)

        try:
            load_result = await load_artifact_content_or_metadata(
                artifact_service=self.shared_artifact_service,
                app_name=context.get("app_name_for_artifacts"),
                user_id=context.get("user_id_for_artifacts"),
                session_id=context.get("a2a_session_id"),
                filename=part.file.name,
                version="latest",
                return_raw_bytes=True,
            )

            if load_result.get("status") != "success":
                file_info["error"] = (
                    f"Failed to load artifact: {load_result.get('message')}"
                )
                return file_info

            content_bytes = load_result.get("raw_bytes")
            if len(content_bytes) > max_size:
                file_info["error"] = (
                    f"File size ({len(content_bytes)} bytes) exceeds handler limit ({max_size} bytes)."
                )
                return file_info

            if is_text_based_mime_type(part.file.mimeType):
                file_info["content"] = content_bytes.decode("utf-8")
            else:
                file_info["bytes"] = base64.b64encode(content_bytes).decode("utf-8")

        except Exception as e:
            file_info["error"] = f"Error processing artifact: {str(e)}"
            log.exception("Failed to process file part for output: %s", e)

        return file_info

    async def _start_data_plane_client(self):
        """
        Initializes and starts the internal SAC App with dedicated flows for
        data plane input (BrokerInput) and output (BrokerOutput).
        """
        log_id_prefix = f"{self.log_identifier}[DataPlaneClient]"
        async with self.data_plane_client_lock:
            if self.data_plane_internal_app is not None:
                log.info(
                    "%s Data plane client (internal app) already started.",
                    log_id_prefix,
                )
                return

            log.info(
                "%s Starting data plane client (internal SAC app)...", log_id_prefix
            )
            try:
                main_app = self.get_app()
                if (
                    not main_app
                    or not hasattr(main_app, "connector")
                    or not main_app.connector
                ):
                    raise RuntimeError(
                        "Main SAC App or Connector instance not available."
                    )

                _event_forwarder_info = {
                    "class_name": "EventForwarderComponent",
                    "description": "Forwards SolaceMessages to an internal queue.",
                    "config_parameters": [
                        {
                            "name": "target_queue_ref",
                            "required": True,
                            "type": "queue.Queue",
                        }
                    ],
                    "input_schema": {"type": "object"},
                    "output_schema": None,
                }

                class EventForwarderComponent(ComponentBase):
                    def __init__(self, **kwargs: Any):
                        super().__init__(_event_forwarder_info, **kwargs)
                        self.target_queue: queue.Queue = self.get_config(
                            "target_queue_ref"
                        )

                    def invoke(
                        self, message: SolaceMessage, data: Dict[str, Any]
                    ) -> None:
                        try:
                            self.target_queue.put_nowait(message)
                            message.call_acknowledgements()
                        except queue.Full:
                            log.error(
                                "%s Target queue full. Message NACKed.",
                                self.log_identifier,
                            )
                            message.call_negative_acknowledgements()
                        except Exception as e:
                            log.exception(
                                "%s Error putting message to target queue: %s",
                                self.log_identifier,
                                e,
                            )
                            message.call_negative_acknowledgements()
                        return None

                broker_input_config = {
                    "component_module": "broker_input",
                    "component_name": f"{self.gateway_id}_data_plane_broker_input",
                    "broker_queue_name": f"{self.namespace.strip('/')}/q/gdk/event-mesh-gw/data/{self.gateway_id}/{uuid.uuid4().hex}",
                    "create_queue_on_start": True,
                    "temporary_queue": True,
                    "component_config": {
                        **self.event_mesh_broker_config,
                        "broker_subscriptions": [],
                        "payload_format": "binary",
                    },
                }
                forwarder_config = {
                    "component_class": EventForwarderComponent,
                    "component_name": f"{self.gateway_id}_data_plane_forwarder",
                    "component_config": {
                        "target_queue_ref": self.data_plane_message_queue
                    },
                }
                input_flow_config = {
                    "name": f"{self.gateway_id}_data_plane_input_flow",
                    "components": [broker_input_config, forwarder_config],
                }

                broker_output_config = {
                    "component_module": "broker_output",
                    "component_name": f"{self.gateway_id}_data_plane_broker_output",
                    "component_config": {
                        **self.event_mesh_broker_config,
                        "payload_format": "binary",
                    },
                }
                output_flow_config = {
                    "name": f"{self.gateway_id}_data_plane_output_flow",
                    "components": [broker_output_config],
                }

                self.data_plane_internal_app = main_app.connector.create_internal_app(
                    app_name=f"{self.gateway_id}_data_plane_sac_app",
                    flows=[input_flow_config, output_flow_config],
                )

                if (
                    not self.data_plane_internal_app
                    or not self.data_plane_internal_app.flows
                ):
                    raise RuntimeError("Failed to create internal data plane app/flow.")

                self.data_plane_internal_app.run()

                input_flow_name = input_flow_config["name"]
                input_flow = next(
                    (
                        f
                        for f in self.data_plane_internal_app.flows
                        if f.name == input_flow_name
                    ),
                    None,
                )
                if input_flow and input_flow.component_groups:
                    self.data_plane_broker_input = input_flow.component_groups[0][0]

                output_flow_name = output_flow_config["name"]
                output_flow = next(
                    (
                        f
                        for f in self.data_plane_internal_app.flows
                        if f.name == output_flow_name
                    ),
                    None,
                )
                if output_flow and output_flow.component_groups:
                    self.data_plane_broker_output = output_flow.component_groups[0][0]

                if (
                    not self.data_plane_broker_input
                    or not self.data_plane_broker_output
                ):
                    raise RuntimeError(
                        "Failed to get references to internal data plane components."
                    )

                log.info(
                    "%s Internal data plane app with input/output flows started.",
                    log_id_prefix,
                )

            except Exception as e:
                log.exception(
                    "%s Failed to start data plane client (internal app): %s",
                    log_id_prefix,
                    e,
                )
                if self.data_plane_internal_app:
                    try:
                        self.data_plane_internal_app.cleanup()
                    except Exception as cleanup_err:
                        log.error(
                            "%s Error cleaning up data plane app after start failure: %s",
                            log_id_prefix,
                            cleanup_err,
                        )
                self.data_plane_internal_app = None
                self.data_plane_broker_input = None
                self.data_plane_broker_output = None
                raise

    async def _stop_data_plane_client(self):
        """Stops and cleans up the internal SAC App for the data plane client."""
        log_id_prefix = f"{self.log_identifier}[DataPlaneClient]"
        async with self.data_plane_client_lock:
            if self.data_plane_internal_app:
                log.info(
                    "%s Stopping data plane client (internal SAC app)...", log_id_prefix
                )
                try:
                    self.data_plane_internal_app.cleanup()
                    log.info(
                        "%s Data plane client (internal SAC app) stopped and cleaned up.",
                        log_id_prefix,
                    )
                except Exception as e:
                    log.exception(
                        "%s Error stopping/cleaning up data plane client: %s",
                        log_id_prefix,
                        e,
                    )
                finally:
                    self.data_plane_internal_app = None
                    self.data_plane_broker_input = None
                    self.data_plane_broker_output = None
            else:
                log.info(
                    "%s Data plane client (internal app) already stopped or not started.",
                    log_id_prefix,
                )

    async def _initialize_and_subscribe_data_plane(self):
        """Initializes the data plane client and adds subscriptions from event_handlers_config."""
        log_id_prefix = f"{self.log_identifier}[InitDataPlane]"
        log.info("%s Initializing and subscribing data plane...", log_id_prefix)
        try:
            await self._start_data_plane_client()

            if not self.data_plane_broker_input:
                raise RuntimeError(
                    "Data plane BrokerInput not available for adding subscriptions."
                )

            all_topics_to_subscribe = set()
            for handler_config in self.event_handlers_config:
                for sub_config in handler_config.get("subscriptions", []):
                    topic_str = sub_config.get("topic")
                    if topic_str:
                        all_topics_to_subscribe.add(topic_str)

            log.info(
                "%s Adding %d unique subscriptions to data plane BrokerInput: %s",
                log_id_prefix,
                len(all_topics_to_subscribe),
                all_topics_to_subscribe,
            )

            for topic_str in all_topics_to_subscribe:
                if not self.data_plane_broker_input.add_subscription(topic_str):
                    log.error(
                        "%s Failed to add subscription '%s' to data plane BrokerInput.",
                        log_id_prefix,
                        topic_str,
                    )
                else:
                    log.info(
                        "%s Successfully added subscription '%s' to data plane BrokerInput.",
                        log_id_prefix,
                        topic_str,
                    )

            log.info("%s Data plane subscriptions configured.", log_id_prefix)

        except Exception as e:
            log.exception(
                "%s Failed to initialize and subscribe data plane: %s", log_id_prefix, e
            )
            raise

    async def _data_plane_message_processor_loop(self):
        """
        Consumes SolaceMessages from data_plane_message_queue and processes them.
        """
        log_id_prefix = f"{self.log_identifier}[DataPlaneProcessor]"
        log.info("%s Starting data plane message processor loop...", log_id_prefix)
        loop = asyncio.get_running_loop()

        while not self.stop_signal.is_set():
            solace_msg: Optional[SolaceMessage] = None
            try:
                solace_msg = await loop.run_in_executor(
                    None, self.data_plane_message_queue.get, True, 1.0
                )

                if solace_msg is None:
                    log.info(
                        "%s Received shutdown signal for data plane processor loop.",
                        log_id_prefix,
                    )
                    break

                log.debug(
                    "%s Processing SolaceMessage from data plane queue. Topic: %s",
                    log_id_prefix,
                    solace_msg.get_topic(),
                )

                # The SolaceMessage was already ACKed by EventForwarderComponent to the internal BrokerInput.
                # _handle_incoming_solace_message is responsible for the business logic.
                # Its boolean return can be used for logging or further error handling if needed.
                await self._handle_incoming_solace_message(solace_msg)

            except queue.Empty:
                continue
            except asyncio.CancelledError:
                log.info(
                    "%s Data plane message processor loop cancelled.", log_id_prefix
                )
                break
            except Exception as e:
                log.exception(
                    "%s Unhandled error in data plane message processor loop: %s",
                    log_id_prefix,
                    e,
                )
                # If an error occurs here, the message was already ACKed by the forwarder.
                # Log and continue. Consider if specific error handling for the original message is needed.
                await asyncio.sleep(1)  # Avoid tight loop on unexpected errors
            finally:
                if solace_msg is not None and self.data_plane_message_queue is not None:
                    self.data_plane_message_queue.task_done()

        log.info("%s Data plane message processor loop finished.", log_id_prefix)

    async def _extract_initial_claims(
        self, external_event_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the primary identity claims from an incoming Solace message
        based on the matched event handler's configuration.
        """
        log_id_prefix = f"{self.log_identifier}[ExtractClaims]"
        solace_msg: SolaceMessage = external_event_data.get("solace_message")
        handler_config: Dict = external_event_data.get("handler_config")

        if not solace_msg or not handler_config:
            log.error(
                "%s Invalid external_event_data. Missing 'solace_message' or 'handler_config'.",
                log_id_prefix,
            )
            return None

        user_identity_str: Optional[str] = None
        user_identity_expression = handler_config.get("user_identity_expression")

        if user_identity_expression:
            try:
                user_identity_str = solace_msg.get_data(user_identity_expression)
            except Exception as e:
                log.warning(
                    "%s Failed to evaluate user_identity_expression '%s': %s. Authentication fails.",
                    log_id_prefix,
                    user_identity_expression,
                    e,
                )
                return None

        if not user_identity_str:
            log.debug(
                "%s No user identity extracted from expression. Returning None for claims.",
                log_id_prefix,
            )
            return None

        log.info(
            "%s Extracted initial claims with id: %s", log_id_prefix, user_identity_str
        )
        return {"id": user_identity_str, "source": "solace_message"}

    async def _process_artifacts_from_message(
        self,
        msg_for_expression: SolaceMessage,
        handler_config: Dict[str, Any],
        user_identity: Dict[str, Any],
        a2a_session_id: str,
    ) -> List[str]:
        """
        Processes the artifact_processing block from a handler config.
        Extracts data, creates artifacts, and returns their URIs.
        """
        log_id_prefix = f"{self.log_identifier}[ProcessArtifacts]"
        artifact_processing_config = handler_config.get("artifact_processing")

        if not artifact_processing_config:
            return []

        if not self.shared_artifact_service:
            log.warning(
                "%s Artifact processing is configured but no artifact_service is available. Skipping.",
                log_id_prefix,
            )
            return []

        extract_expr = artifact_processing_config.get("extract_artifacts_expression")
        artifact_def = artifact_processing_config.get("artifact_definition")

        if not extract_expr or not artifact_def:
            log.error(
                "%s Invalid artifact_processing config: missing 'extract_artifacts_expression' or 'artifact_definition'.",
                log_id_prefix,
            )
            return []

        try:
            items_to_process = msg_for_expression.get_data(extract_expr)
        except Exception as e:
            log.error(
                "%s Failed to evaluate extract_artifacts_expression '%s': %s",
                log_id_prefix,
                extract_expr,
                e,
            )
            return []

        if items_to_process is None:
            return []

        if not isinstance(items_to_process, list):
            items_to_process = [items_to_process]

        created_artifact_uris = []
        for item in items_to_process:
            try:
                temp_msg = SolaceMessage(
                    payload=item,
                    topic=msg_for_expression.get_topic(),
                    user_properties=msg_for_expression.get_user_properties(),
                )

                filename_expr = artifact_def.get("filename", "").replace(
                    "list_item:", "input.payload:"
                )
                content_expr = artifact_def.get("content", "").replace(
                    "list_item:", "input.payload:"
                )
                mime_type_expr = artifact_def.get("mime_type", "").replace(
                    "list_item:", "input.payload:"
                )
                encoding_expr = artifact_def.get("content_encoding", "").replace(
                    "list_item:", "input.payload:"
                )

                filename = temp_msg.get_data(filename_expr)
                content_value = temp_msg.get_data(content_expr)
                mime_type = temp_msg.get_data(mime_type_expr)
                encoding = temp_msg.get_data(encoding_expr) if encoding_expr else None

                if not filename or content_value is None or not mime_type:
                    log.warning(
                        "%s Skipping item due to missing filename, content, or mime_type after expression evaluation.",
                        log_id_prefix,
                    )
                    continue

                content_bytes: bytes
                if encoding == "base64":
                    if isinstance(content_value, str):
                        content_bytes = base64.b64decode(content_value)
                    else:
                        log.warning(
                            "%s 'base64' encoding specified, but content is not a string. Skipping item.",
                            log_id_prefix,
                        )
                        continue
                elif encoding == "text":
                    content_bytes = str(content_value).encode("utf-8")
                elif encoding == "binary":
                    if isinstance(content_value, bytes):
                        content_bytes = content_value
                    else:
                        log.warning(
                            "%s 'binary' encoding specified, but content is not bytes. Skipping item.",
                            log_id_prefix,
                        )
                        continue
                else:
                    if isinstance(content_value, bytes):
                        content_bytes = content_value
                    else:
                        content_bytes = str(content_value).encode("utf-8")

                save_result = await save_artifact_with_metadata(
                    artifact_service=self.shared_artifact_service,
                    app_name=self.gateway_id,
                    user_id=user_identity.get("id"),
                    session_id=a2a_session_id,
                    filename=filename,
                    content_bytes=content_bytes,
                    mime_type=mime_type,
                    metadata_dict={
                        "source": "event_mesh_gateway",
                        "original_topic": msg_for_expression.get_topic(),
                    },
                    timestamp=datetime.now(timezone.utc),
                )

                if save_result["status"] in ["success", "partial_success"]:
                    data_version = save_result.get("data_version", 0)
                    artifact_uri = f"artifact://{self.gateway_id}/{user_identity.get('id')}/{a2a_session_id}/{filename}?version={data_version}"
                    created_artifact_uris.append(artifact_uri)
                    log.info(
                        "%s Successfully created artifact: %s",
                        log_id_prefix,
                        artifact_uri,
                    )
                else:
                    log.error(
                        "%s Failed to save artifact '%s': %s",
                        log_id_prefix,
                        filename,
                        save_result.get("message"),
                    )

            except Exception as item_err:
                log.exception(
                    "%s Error processing an item for artifact creation: %s",
                    log_id_prefix,
                    item_err,
                )
                continue

        return created_artifact_uris

    async def _translate_external_input(
        self,
        external_event_data: SolaceMessage,
        user_identity: Dict[str, Any],
        handler_config: Dict,
    ) -> Tuple[Optional[str], List[A2APart], Dict[str, Any]]:
        """
        Translates an incoming SolaceMessage into A2A task parameters.
        """
        log_id_prefix = f"{self.log_identifier}[TranslateInput]"
        a2a_parts: List[A2APart] = []
        external_request_context: Dict[str, Any] = {}
        a2a_session_id = f"event-mesh-session-{uuid.uuid4().hex}"

        try:
            decoded_payload = decode_payload(
                payload=external_event_data.get_payload(),
                encoding=handler_config.get("payload_encoding", "utf-8"),
                payload_format=handler_config.get("payload_format", "json"),
            )
            msg_for_expression = SolaceMessage(
                payload=decoded_payload,
                topic=external_event_data.get_topic(),
                user_properties=external_event_data.get_user_properties(),
            )
            log.debug("%s Payload decoded successfully.", log_id_prefix)
        except Exception as e:
            log.error("%s Failed to decode payload: %s", log_id_prefix, e)
            return None, [], {"error": "Payload decoding failed"}

        created_artifact_uris = await self._process_artifacts_from_message(
            msg_for_expression, handler_config, user_identity, a2a_session_id
        )
        if created_artifact_uris:
            msg_for_expression.set_data(
                "user_data.created_artifacts:uris", created_artifact_uris
            )
            for uri in created_artifact_uris:
                try:
                    filename = uri.split("/")[-1].split("?")[0]
                    file_content = FileContent(name=filename, uri=uri)
                    a2a_parts.append(FilePart(file=file_content))
                except Exception as uri_parse_err:
                    log.warning(
                        "%s Failed to parse URI to create FilePart: %s",
                        log_id_prefix,
                        uri_parse_err,
                    )

        input_expression = handler_config.get("input_expression")
        if not input_expression:
            log.error(
                "%s 'input_expression' is missing in handler_config.", log_id_prefix
            )
            return None, [], {"error": "Missing input_expression"}
        try:
            transformed_text = msg_for_expression.get_data(input_expression)
            if transformed_text is not None:
                a2a_parts.append(TextPart(text=str(transformed_text)))
            else:
                log.warning(
                    "%s Input expression '%s' yielded None. Creating empty TextPart.",
                    log_id_prefix,
                    input_expression,
                )
                a2a_parts.append(TextPart(text=""))
            log.debug(
                "%s Input expression evaluated. Result length: %d",
                log_id_prefix,
                len(transformed_text or ""),
            )
        except Exception as e:
            log.error(
                "%s Failed to evaluate input_expression '%s': %s",
                log_id_prefix,
                input_expression,
                e,
            )
            return None, [], {"error": f"Input expression evaluation failed: {e}"}

        target_agent_name: Optional[str] = None
        target_agent_name_expression = handler_config.get(
            "target_agent_name_expression"
        )
        if target_agent_name_expression:
            try:
                target_agent_name = msg_for_expression.get_data(
                    target_agent_name_expression
                )
                log.debug(
                    "%s Target agent name from expression: %s",
                    log_id_prefix,
                    target_agent_name,
                )
            except Exception as e:
                log.warning(
                    "%s Failed to evaluate target_agent_name_expression '%s': %s. Falling back to static.",
                    log_id_prefix,
                    target_agent_name_expression,
                    e,
                )
                target_agent_name = None

        if not target_agent_name:
            target_agent_name = handler_config.get("target_agent_name")
            if target_agent_name:
                log.debug(
                    "%s Target agent name from static config: %s",
                    log_id_prefix,
                    target_agent_name,
                )

        if not target_agent_name:
            log.error("%s Could not determine target_agent_name.", log_id_prefix)
            return None, [], {"error": "Target agent name not configured or resolved"}

        external_request_context = {
            "event_handler_name": handler_config.get("name"),
            "original_solace_topic": external_event_data.get_topic(),
            "original_solace_user_properties": external_event_data.get_user_properties(),
            "user_identity": user_identity,
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": user_identity.get("id"),
            "a2a_session_id": a2a_session_id,
            "user_id_for_a2a": user_identity.get("id"),
            "target_agent_name": target_agent_name,
        }

        forward_context_config = handler_config.get("forward_context", {})
        if forward_context_config:
            forwarded_data = {}
            for key, expression in forward_context_config.items():
                try:
                    forwarded_data[key] = msg_for_expression.get_data(expression)
                except Exception as e:
                    log.warning(
                        "%s Could not evaluate forward_context expression for '%s': %s. Skipping.",
                        log_id_prefix,
                        key,
                        e,
                    )
            external_request_context["forwarded_context"] = forwarded_data
            log.debug(
                "%s Forwarded context prepared: %s", log_id_prefix, forwarded_data
            )

        log.debug(
            "%s External request context prepared: %s",
            log_id_prefix,
            external_request_context,
        )

        return target_agent_name, a2a_parts, external_request_context

    async def _send_final_response_to_external(
        self, external_request_context: Dict, task_data: Task
    ) -> None:
        """
        Sends the final A2A Task response back to the Solace Event Mesh.
        """
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        event_handler_name = external_request_context.get("event_handler_name")
        event_handler_config = self.event_handler_map.get(event_handler_name, {})

        output_handler_name = event_handler_config.get("on_success")

        if not output_handler_name:
            log.debug(
                "%s No on_success or output_handler_name in context for handler '%s'. Response for task %s will not be published.",
                log_id_prefix,
                event_handler_name,
                task_data.id,
            )
            return

        handler_config = self.output_handler_map.get(output_handler_name)
        if not handler_config:
            log.warning(
                "%s Output handler '%s' not found for task %s. Response will not be published.",
                log_id_prefix,
                output_handler_name,
                task_data.id,
            )
            return

        log.info(
            "%s Processing final response for task %s using output_handler '%s'",
            log_id_prefix,
            task_data.id,
            output_handler_name,
        )

        try:
            simplified_payload = {
                "text": None,
                "files": [],
                "data": [],
                "a2a_task_response": task_data.model_dump(exclude_none=True),
            }

            if (
                task_data.status
                and task_data.status.message
                and task_data.status.message.parts
            ):
                text_parts_content = []
                for part in task_data.status.message.parts:
                    if isinstance(part, TextPart):
                        text_parts_content.append(part.text)
                    elif isinstance(part, DataPart):
                        simplified_payload["data"].append(
                            part.model_dump(exclude_none=True)
                        )
                    elif isinstance(part, FilePart) and self.shared_artifact_service:
                        file_info = await self._process_file_part_for_output(
                            part, external_request_context, handler_config
                        )
                        simplified_payload["files"].append(file_info)

                if text_parts_content:
                    simplified_payload["text"] = "\n".join(text_parts_content)

            original_user_props = external_request_context.get(
                "original_solace_user_properties", {}
            )
            forwarded_context_data = external_request_context.get(
                "forwarded_context", {}
            )

            msg_for_expression = SolaceMessage(
                payload=simplified_payload, user_properties=original_user_props
            )
            msg_for_expression.set_data(
                "user_data.forward_context", forwarded_context_data
            )

            if output_handler_name in self.output_handler_transforms:
                transform_engine = self.output_handler_transforms[output_handler_name]
                transform_engine.transform(msg_for_expression, calling_object=self)
                log.debug(
                    "%s Applied output_transforms for handler '%s'",
                    log_id_prefix,
                    output_handler_name,
                )

            topic_expression = handler_config.get("topic_expression", "").replace(
                "task_response:", "input.payload:", 1
            )
            if not topic_expression:
                log.error(
                    "%s 'topic_expression' missing in output_handler '%s'. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return
            target_topic = msg_for_expression.get_data(topic_expression)
            if not target_topic:
                log.error(
                    "%s 'topic_expression' for handler '%s' evaluated to empty. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return

            payload_expression = handler_config.get("payload_expression", "").replace(
                "task_response:", "input.payload:", 1
            )
            if not payload_expression:
                log.error(
                    "%s 'payload_expression' missing in output_handler '%s'. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return
            raw_payload_for_solace = msg_for_expression.get_data(payload_expression)
            if raw_payload_for_solace is None:
                log.warning(
                    "%s 'payload_expression' for handler '%s' evaluated to None. Publishing empty payload.",
                    log_id_prefix,
                    output_handler_name,
                )
                raw_payload_for_solace = ""

            output_schema = handler_config.get("output_schema")
            if output_schema and isinstance(output_schema, dict) and output_schema:
                try:
                    payload_to_validate = raw_payload_for_solace
                    if isinstance(raw_payload_for_solace, str):
                        try:
                            payload_to_validate = json.loads(raw_payload_for_solace)
                        except json.JSONDecodeError:
                            pass

                    jsonschema.validate(
                        instance=payload_to_validate, schema=output_schema
                    )
                    log.debug(
                        "%s Output payload validated successfully against schema for handler '%s'.",
                        log_id_prefix,
                        output_handler_name,
                    )
                except jsonschema.ValidationError as ve:
                    log.error(
                        "%s Output payload validation failed for handler '%s': %s",
                        log_id_prefix,
                        output_handler_name,
                        ve.message,
                    )
                    if handler_config.get("on_validation_error", "log") == "drop":
                        log.warning(
                            "%s Dropping message due to schema validation failure for handler '%s'.",
                            log_id_prefix,
                            output_handler_name,
                        )
                        return

            encoded_payload = encode_payload(
                payload=raw_payload_for_solace,
                encoding=handler_config.get("payload_encoding", "utf-8"),
                payload_format=handler_config.get("payload_format", "json"),
            )
            if self.data_plane_broker_output:
                output_data = {
                    "payload": encoded_payload,
                    "topic": target_topic,
                    "user_properties": {},
                }
                output_message = SolaceMessage()
                output_message.set_previous(output_data)
                event = Event(EventType.MESSAGE, output_message)
                self.data_plane_broker_output.enqueue(event)
                log.info(
                    "%s Enqueued final response for task %s to topic '%s' via data plane output flow.",
                    log_id_prefix,
                    task_data.id,
                    target_topic,
                )
            else:
                log.error(
                    "%s Data plane broker output service not available. Cannot publish response for task %s.",
                    log_id_prefix,
                    task_data.id,
                )

        except Exception as e:
            log.exception(
                "%s Error sending final response for task %s using handler '%s': %s",
                log_id_prefix,
                task_data.id,
                output_handler_name,
                e,
            )

    async def _send_error_to_external(
        self, external_request_context: Dict, error_data: JSONRPCError
    ) -> None:
        """
        Sends an A2A Error response back to the Solace Event Mesh.
        Uses the same output handler logic as final responses.
        """
        log_id_prefix = f"{self.log_identifier}[SendErrorResponse]"
        event_handler_name = external_request_context.get("event_handler_name")
        event_handler_config = self.event_handler_map.get(event_handler_name, {})
        task_id_for_log = external_request_context.get(
            "a2a_task_id_for_event", "unknown_task"
        )

        output_handler_name = event_handler_config.get("on_error")

        if not output_handler_name:
            log.debug(
                "%s No on_error or output_handler_name in context for handler '%s'. Error for task %s will not be published.",
                log_id_prefix,
                event_handler_name,
                task_id_for_log,
            )
            return

        handler_config = self.output_handler_map.get(output_handler_name)
        if not handler_config:
            log.warning(
                "%s Output handler '%s' not found for error of task %s. Error will not be published.",
                log_id_prefix,
                output_handler_name,
                task_id_for_log,
            )
            return

        log.info(
            "%s Processing error response for task %s using output_handler '%s'",
            log_id_prefix,
            task_id_for_log,
            output_handler_name,
        )

        try:
            simplified_payload = {
                "text": None,
                "files": [],
                "data": [],
                "a2a_task_response": {
                    "error": error_data.model_dump(exclude_none=True)
                },
            }

            original_user_props = external_request_context.get(
                "original_solace_user_properties", {}
            )
            forwarded_context_data = external_request_context.get(
                "forwarded_context", {}
            )

            msg_for_expression = SolaceMessage(
                payload=simplified_payload, user_properties=original_user_props
            )
            msg_for_expression.set_data(
                "user_data.forward_context", forwarded_context_data
            )

            if output_handler_name in self.output_handler_transforms:
                transform_engine = self.output_handler_transforms[output_handler_name]
                transform_engine.transform(msg_for_expression, calling_object=self)
                log.debug(
                    "%s Applied output_transforms for error handler '%s'",
                    log_id_prefix,
                    output_handler_name,
                )

            topic_expression = handler_config.get("topic_expression", "").replace(
                "task_response:", "input.payload:", 1
            )
            if not topic_expression:
                log.error(
                    "%s 'topic_expression' missing in error output_handler '%s'. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return
            target_topic = msg_for_expression.get_data(topic_expression)
            if not target_topic:
                log.error(
                    "%s 'topic_expression' for error handler '%s' evaluated to empty. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return

            payload_expression = handler_config.get("payload_expression", "").replace(
                "task_response:", "input.payload:", 1
            )
            if not payload_expression:
                log.error(
                    "%s 'payload_expression' missing in error output_handler '%s'. Cannot publish.",
                    log_id_prefix,
                    output_handler_name,
                )
                return
            raw_payload_for_solace = msg_for_expression.get_data(payload_expression)
            if raw_payload_for_solace is None:
                log.warning(
                    "%s 'payload_expression' for error handler '%s' evaluated to None. Publishing empty payload.",
                    log_id_prefix,
                    output_handler_name,
                )
                raw_payload_for_solace = ""

            output_schema = handler_config.get("output_schema")
            if output_schema and isinstance(output_schema, dict) and output_schema:
                try:
                    payload_to_validate = raw_payload_for_solace
                    if isinstance(raw_payload_for_solace, str):
                        try:
                            payload_to_validate = json.loads(raw_payload_for_solace)
                        except json.JSONDecodeError:
                            pass
                    jsonschema.validate(
                        instance=payload_to_validate, schema=output_schema
                    )
                except jsonschema.ValidationError as ve:
                    log.error(
                        "%s Error payload validation failed for handler '%s': %s",
                        log_id_prefix,
                        output_handler_name,
                        ve.message,
                    )
                    if handler_config.get("on_validation_error", "log") == "drop":
                        log.warning(
                            "%s Dropping error message due to schema validation failure for handler '%s'.",
                            log_id_prefix,
                            output_handler_name,
                        )
                        return

            encoded_payload = encode_payload(
                payload=raw_payload_for_solace,
                encoding=handler_config.get("payload_encoding", "utf-8"),
                payload_format=handler_config.get("payload_format", "json"),
            )

            if self.data_plane_broker_output:
                output_data = {
                    "payload": encoded_payload,
                    "topic": target_topic,
                    "user_properties": {},
                }
                output_message = SolaceMessage()
                output_message.set_previous(output_data)
                event = Event(EventType.MESSAGE, output_message)
                self.data_plane_broker_output.enqueue(event)
                log.info(
                    "%s Enqueued error response for task %s to topic '%s' via data plane output flow.",
                    log_id_prefix,
                    task_id_for_log,
                    target_topic,
                )
            else:
                log.error(
                    "%s Data plane broker output service not available. Cannot publish error for task %s.",
                    log_id_prefix,
                    task_id_for_log,
                )

        except Exception as e:
            log.exception(
                "%s Error sending error response for task %s using handler '%s': %s",
                log_id_prefix,
                task_id_for_log,
                output_handler_name,
                e,
            )

    async def _send_update_to_external(
        self,
        external_request_context: Dict,
        event_data: Any,
        is_final_chunk_of_update: bool,
    ) -> None:
        log.debug(
            "%s _send_update_to_external called, but Event Mesh Gateway does not publish intermediate updates.",
            self.log_identifier,
        )
        pass

    def _start_listener(self) -> None:
        """
        GDK Hook: Schedules data plane initialization and starts the data plane message processor.
        Called by BaseGatewayComponent.run() within self.async_loop.
        """
        log_id_prefix = f"{self.log_identifier}[StartListener]"
        log.info(
            "%s Scheduling data plane initialization and starting data plane message processor...",
            log_id_prefix,
        )

        if not self.async_loop:
            log.error(
                "%s Async loop not available. Cannot start listener.",
                log_id_prefix,
            )
            self.stop_signal.set()
            return

        self.async_loop.create_task(self._initialize_and_subscribe_data_plane())
        log.info("%s Data plane subscriber initialization task created.", log_id_prefix)

        if (
            self.data_plane_processor_task is None
            or self.data_plane_processor_task.done()
        ):
            self.data_plane_processor_task = self.async_loop.create_task(
                self._data_plane_message_processor_loop()
            )
            log.info(
                "%s Data plane message processor task created and started.",
                log_id_prefix,
            )
        else:
            log.info(
                "%s Data plane message processor task already running.", log_id_prefix
            )

    def _stop_listener(self) -> None:
        """
        GDK Hook: Schedules data plane client stop and terminates the data plane message processor.
        Called by BaseGatewayComponent.cleanup().
        """
        log_id_prefix = f"{self.log_identifier}[StopListener]"
        log.info(
            "%s Stopping listener: scheduling data plane client stop and terminating processor...",
            log_id_prefix,
        )

        if self.async_loop and self.async_loop.is_running():
            if self.data_plane_internal_app:
                stop_subscriber_future = asyncio.run_coroutine_threadsafe(
                    self._stop_data_plane_client(), self.async_loop
                )
                try:
                    stop_subscriber_future.result(timeout=10)
                    log.info(
                        "%s Data plane subscriber client stop scheduled and completed.",
                        log_id_prefix,
                    )
                except TimeoutError:
                    log.error(
                        "%s Timeout waiting for data plane subscriber client to stop.",
                        log_id_prefix,
                    )
                except Exception as e:
                    log.exception(
                        "%s Error stopping data plane subscriber client: %s",
                        log_id_prefix,
                        e,
                    )

            if self.data_plane_message_queue:
                try:
                    self.data_plane_message_queue.put_nowait(None)
                except queue.Full:
                    log.warning(
                        "%s Data plane message queue full, could not send stop signal.",
                        log_id_prefix,
                    )

            if (
                self.data_plane_processor_task
                and not self.data_plane_processor_task.done()
            ):
                log.info(
                    "%s Cancelling data plane message processor task...", log_id_prefix
                )
                self.data_plane_processor_task.cancel()

            log.info(
                "%s Data plane message processor task signalled/cancelled.",
                log_id_prefix,
            )
        else:
            log.warning(
                "%s Async loop not running. Cannot perform clean stop of data plane listener components.",
                log_id_prefix,
            )
            if self.data_plane_internal_app:
                try:
                    asyncio.run(self._stop_data_plane_client())
                except Exception as e:
                    log.error(
                        "%s Error in direct call to _stop_data_plane_client (subscriber) during cleanup: %s",
                        log_id_prefix,
                        e,
                    )
            if self.data_plane_publisher_service:
                try:
                    asyncio.run(self._cleanup_data_plane_publisher())
                except Exception as e:
                    log.error(
                        "%s Error in direct call to _cleanup_data_plane_publisher during cleanup: %s",
                        log_id_prefix,
                        e,
                    )

    async def _handle_incoming_solace_message(self, solace_msg: SolaceMessage) -> bool:
        """
        Processes an incoming SolaceMessage from the data plane.
        Finds a matching event handler, authenticates, translates, and submits an A2A task.
        The SolaceMessage is already ACKed by the EventForwarderComponent in the internal flow.
        Returns True if task submission was initiated, False otherwise.
        """
        log_id_prefix = f"{self.log_identifier}[HandleIncomingMsg]"
        incoming_topic = solace_msg.get_topic()
        log.info(
            "%s Received Solace message on topic: %s", log_id_prefix, incoming_topic
        )

        matched_handler_config: Optional[Dict[str, Any]] = None
        for handler_config in self.event_handlers_config:
            for sub_config in handler_config.get("subscriptions", []):
                subscription_topic = sub_config.get("topic")
                if subscription_topic and _topic_matches_subscription(
                    incoming_topic, subscription_topic
                ):
                    matched_handler_config = handler_config
                    log.debug(
                        "%s Matched event_handler '%s' for topic '%s'",
                        log_id_prefix,
                        matched_handler_config.get("name"),
                        incoming_topic,
                    )
                    break
            if matched_handler_config:
                break

        if not matched_handler_config:
            log.warning(
                "%s No matching event_handler found for topic: %s. Discarding message.",
                log_id_prefix,
                incoming_topic,
            )
            return False
        try:
            event_data_for_auth = {
                "solace_message": solace_msg,
                "handler_config": matched_handler_config,
            }
            user_identity = await self.authenticate_and_enrich_user(event_data_for_auth)
            if user_identity is None:
                log.error(
                    "%s Authentication failed for message on topic %s. Discarding.",
                    log_id_prefix,
                    incoming_topic,
                )
                return False
        except Exception as auth_err:
            log.exception(
                "%s Error during authentication/enrichment for topic %s: %s",
                log_id_prefix,
                incoming_topic,
                auth_err,
            )
            return False

        try:
            target_agent_name, a2a_parts, external_request_context = (
                await self._translate_external_input(
                    solace_msg, user_identity, matched_handler_config
                )
            )
            if target_agent_name is None or not a2a_parts:
                log.error(
                    "%s Input translation failed or yielded no A2A parts for topic %s. Discarding.",
                    log_id_prefix,
                    incoming_topic,
                )
                return False
        except Exception as trans_err:
            log.exception(
                "%s Error during _translate_external_input for topic %s: %s",
                log_id_prefix,
                incoming_topic,
                trans_err,
            )
            return False

        try:
            task_id = await self.submit_a2a_task(
                target_agent_name=target_agent_name,
                a2a_parts=a2a_parts,
                external_request_context=external_request_context,
                user_identity=user_identity,
                is_streaming=False,
            )
            log.info(
                "%s Successfully submitted A2A task %s for Solace message on topic %s",
                log_id_prefix,
                task_id,
                incoming_topic,
            )
            return True
        except PermissionError as perm_err:
            log.error(
                "%s Permission denied during A2A task submission for topic %s: %s",
                log_id_prefix,
                incoming_topic,
                perm_err,
            )
            return False
        except Exception as submit_err:
            log.exception(
                "%s Error submitting A2A task for Solace message on topic %s: %s",
                log_id_prefix,
                incoming_topic,
                submit_err,
            )
            return False
