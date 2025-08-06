"""
Custom Solace AI Connector Component to host the FastAPI backend for the Web UI.
"""

import asyncio
import queue
import uuid
import json
import re
import threading
from typing import Any, Dict, Optional, List, Tuple, Union, Set
from datetime import datetime, timezone
from fastapi import UploadFile, Request as FastAPIRequest

import uvicorn
from fastapi import FastAPI

from solace_ai_connector.common.log import log
from solace_ai_connector.flow.app import App as SACApp
from solace_ai_connector.components.inputs_outputs.broker_input import (
    BrokerInput,
)

from ...gateway.http_sse.sse_manager import SSEManager

from .components import VisualizationForwarderComponent
from ...gateway.http_sse.session_manager import SessionManager
from ...gateway.base.component import BaseGatewayComponent
from ...common.agent_registry import AgentRegistry
from ...core_a2a.service import CoreA2AService
from google.adk.artifacts import BaseArtifactService

from ...common.types import (
    AgentCard,
    Part as A2APart,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    JSONRPCResponse,
    TextPart,
    FilePart,
    FileContent,
)
from ...common.a2a_protocol import (
    _topic_matches_subscription,
)

from ...agent.utils.artifact_helpers import save_artifact_with_metadata
from ...common.middleware.config_resolver import ConfigResolver


info = {
    "class_name": "WebUIBackendComponent",
    "description": (
        "Hosts the FastAPI backend server for the A2A Web UI, manages messaging via SAC, "
        "and implements GDK abstract methods for Web UI interaction. "
        "Configuration is derived from WebUIBackendApp's app_config."
    ),
    "config_parameters": [
        # Configuration parameters are defined and validated by WebUIBackendApp.app_schema.
    ],
    "input_schema": {
        "type": "object",
        "description": "Not typically used; component reacts to events.",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used; component publishes results via FastAPI/SSE.",
        "properties": {},
    },
}


class WebUIBackendComponent(BaseGatewayComponent):
    """
    Hosts the FastAPI backend, manages messaging via SAC, and bridges threads.
    """

    def __init__(self, **kwargs):
        """
        Initializes the WebUIBackendComponent, inheriting from BaseGatewayComponent.
        """
        super().__init__(**kwargs)
        log.info("%s Initializing Web UI Backend Component...", self.log_identifier)

        try:
            self.namespace = self.get_config("namespace")
            self.gateway_id = self.get_config("gateway_id")
            if not self.gateway_id:
                raise ValueError(
                    "Internal Error: Gateway ID missing after app initialization."
                )
            self.fastapi_host = self.get_config("fastapi_host", "127.0.0.1")
            self.fastapi_port = self.get_config("fastapi_port", 8000)
            self.fastapi_https_port = self.get_config("fastapi_https_port", 8443)
            self.session_secret_key = self.get_config("session_secret_key")
            self.cors_allowed_origins = self.get_config("cors_allowed_origins", ["*"])
            self.resolve_artifact_uris_in_gateway = self.get_config(
                "resolve_artifact_uris_in_gateway", True
            )
            self.ssl_keyfile = self.get_config("ssl_keyfile", "")
            self.ssl_certfile = self.get_config("ssl_certfile", "")
            self.ssl_keyfile_password = self.get_config("ssl_keyfile_password", "")

            log.info(
                "%s WebUI-specific configuration retrieved (Host: %s, Port: %d).",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
            )
        except Exception as e:
            log.error("%s Failed to retrieve configuration: %s", self.log_identifier, e)
            raise ValueError(f"Configuration retrieval error: {e}") from e

        sse_max_queue_size = self.get_config("sse_max_queue_size", 200)

        self.sse_manager = SSEManager(max_queue_size=sse_max_queue_size)

        component_config = self.get_config("component_config", {})
        app_config = component_config.get("app_config", {})

        self.session_manager = SessionManager(
            secret_key=self.session_secret_key,
            app_config=app_config,
        )

        self.fastapi_app: Optional[FastAPI] = None
        self.uvicorn_server: Optional[uvicorn.Server] = None
        self.fastapi_thread: Optional[threading.Thread] = None
        self.fastapi_event_loop: Optional[asyncio.AbstractEventLoop] = None

        self._visualization_internal_app: Optional[SACApp] = None
        self._visualization_broker_input: Optional[BrokerInput] = None
        self._visualization_message_queue: queue.Queue = queue.Queue(maxsize=200)
        self._active_visualization_streams: Dict[str, Dict[str, Any]] = {}
        self._visualization_locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._visualization_locks_lock = threading.Lock()
        self._global_visualization_subscriptions: Dict[str, int] = {}
        self._visualization_processor_task: Optional[asyncio.Task] = None

        log.info("%s Web UI Backend Component initialized.", self.log_identifier)

    def _get_visualization_lock(self) -> asyncio.Lock:
        """Get or create a visualization lock for the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(
                "Visualization lock methods must be called from within an async context"
            )

        with self._visualization_locks_lock:
            if current_loop not in self._visualization_locks:
                self._visualization_locks[current_loop] = asyncio.Lock()
                log.debug(
                    "%s Created new visualization lock for event loop %s",
                    self.log_identifier,
                    id(current_loop),
                )
            return self._visualization_locks[current_loop]

    def _ensure_visualization_flow_is_running(self) -> None:
        """
        Ensures the internal SAC flow for A2A message visualization is created and running.
        This method is designed to be called once during component startup.
        """
        log_id_prefix = f"{self.log_identifier}[EnsureVizFlow]"
        if self._visualization_internal_app is not None:
            log.debug("%s Visualization flow already running.", log_id_prefix)
            return

        log.info("%s Initializing internal A2A visualization flow...", log_id_prefix)
        try:
            main_app = self.get_app()
            if not main_app or not main_app.connector:
                log.error(
                    "%s Cannot get main app or connector instance. Visualization flow NOT started.",
                    log_id_prefix,
                )
                raise RuntimeError(
                    "Main app or connector not available for internal flow creation."
                )

            main_broker_config = main_app.app_info.get("broker", {})
            if not main_broker_config:
                log.error(
                    "%s Main app broker configuration not found. Visualization flow NOT started.",
                    log_id_prefix,
                )
                raise ValueError("Main app broker configuration is missing.")

            broker_input_cfg = {
                "component_module": "broker_input",
                "component_name": f"{self.gateway_id}_viz_broker_input",
                "broker_queue_name": f"{self.namespace.strip('/')}/q/gdk/viz/{self.gateway_id}/{uuid.uuid4().hex}",
                "create_queue_on_start": True,
                "component_config": {
                    "broker_url": main_broker_config.get("broker_url"),
                    "broker_username": main_broker_config.get("broker_username"),
                    "broker_password": main_broker_config.get("broker_password"),
                    "broker_vpn": main_broker_config.get("broker_vpn"),
                    "trust_store_path": main_broker_config.get("trust_store_path"),
                    "dev_mode": main_broker_config.get("dev_mode"),
                    "broker_subscriptions": [],
                    "reconnection_strategy": main_broker_config.get(
                        "reconnection_strategy"
                    ),
                    "retry_interval": main_broker_config.get("retry_interval"),
                    "retry_count": main_broker_config.get("retry_count"),
                    "temporary_queue": True,
                },
            }

            forwarder_cfg = {
                "component_class": VisualizationForwarderComponent,
                "component_name": f"{self.gateway_id}_viz_forwarder",
                "component_config": {
                    "target_queue_ref": self._visualization_message_queue
                },
            }

            flow_config = {
                "name": f"{self.gateway_id}_viz_flow",
                "components": [broker_input_cfg, forwarder_cfg],
            }

            internal_app_broker_config = main_broker_config.copy()
            internal_app_broker_config["input_enabled"] = True
            internal_app_broker_config["output_enabled"] = False

            app_config_for_internal_flow = {
                "name": f"{self.gateway_id}_viz_internal_app",
                "flows": [flow_config],
                "broker": internal_app_broker_config,
                "app_config": {},
            }

            self._visualization_internal_app = main_app.connector.create_internal_app(
                app_name=app_config_for_internal_flow["name"],
                flows=app_config_for_internal_flow["flows"],
            )

            if (
                not self._visualization_internal_app
                or not self._visualization_internal_app.flows
            ):
                log.error(
                    "%s Failed to create internal visualization app/flow.",
                    log_id_prefix,
                )
                self._visualization_internal_app = None
                raise RuntimeError("Internal visualization app/flow creation failed.")

            self._visualization_internal_app.run()
            log.info("%s Internal visualization app started.", log_id_prefix)

            flow_instance = self._visualization_internal_app.flows[0]
            if flow_instance.component_groups and flow_instance.component_groups[0]:
                self._visualization_broker_input = flow_instance.component_groups[0][0]
                if not isinstance(self._visualization_broker_input, BrokerInput):
                    log.error(
                        "%s First component in viz flow is not BrokerInput. Type: %s",
                        log_id_prefix,
                        type(self._visualization_broker_input).__name__,
                    )
                    self._visualization_broker_input = None
                    raise RuntimeError(
                        "Visualization flow setup error: BrokerInput not found."
                    )
                log.info(
                    "%s Obtained reference to internal BrokerInput component.",
                    log_id_prefix,
                )
            else:
                log.error(
                    "%s Could not get BrokerInput instance from internal flow.",
                    log_id_prefix,
                )
                raise RuntimeError(
                    "Visualization flow setup error: BrokerInput instance not accessible."
                )

        except Exception as e:
            log.exception(
                "%s Failed to ensure visualization flow is running: %s",
                log_id_prefix,
                e,
            )
            if self._visualization_internal_app:
                try:
                    self._visualization_internal_app.cleanup()
                except Exception as cleanup_err:
                    log.error(
                        "%s Error during cleanup after viz flow init failure: %s",
                        log_id_prefix,
                        cleanup_err,
                    )
            self._visualization_internal_app = None
            self._visualization_broker_input = None
            raise

    async def _visualization_message_processor_loop(self) -> None:
        """
        Asynchronously consumes messages from the _visualization_message_queue,
        filters them, and forwards them to relevant SSE connections.
        Placeholder for Phase 2: Just logs messages.
        """
        log_id_prefix = f"{self.log_identifier}[VizMsgProcessor]"
        log.info("%s Starting visualization message processor loop...", log_id_prefix)
        loop = asyncio.get_running_loop()

        while not self.stop_signal.is_set():
            msg_data = None
            try:
                msg_data = await loop.run_in_executor(
                    None,
                    self._visualization_message_queue.get,
                    True,
                    1.0,
                )

                if msg_data is None:
                    log.info(
                        "%s Received shutdown signal for viz processor loop.",
                        log_id_prefix,
                    )
                    break

                current_size = self._visualization_message_queue.qsize()
                max_size = self._visualization_message_queue.maxsize
                if max_size > 0 and (current_size / max_size) > 0.90:
                    log.warning(
                        "%s Visualization queue is over 90%% full. Current size: %d/%d",
                        log_id_prefix,
                        current_size,
                        max_size,
                    )

                topic = msg_data.get("topic")
                payload_dict = msg_data.get("payload")

                log.debug("%s [VIZ_DATA_RAW] Topic: %s", log_id_prefix, topic)

                if "/a2a/v1/discovery/" in topic:
                    self._visualization_message_queue.task_done()
                    continue

                event_details_for_owner = self._infer_visualization_event_details(
                    topic, payload_dict
                )
                task_id_for_context = event_details_for_owner.get("task_id")
                message_owner_id = None
                if task_id_for_context:
                    root_task_id = task_id_for_context.split(":", 1)[0]
                    context = self.task_context_manager.get_context(root_task_id)
                    if context and "user_identity" in context:
                        message_owner_id = context["user_identity"].get("id")
                        log.debug(
                            "%s Found owner '%s' for task %s via local context (root: %s).",
                            log_id_prefix,
                            message_owner_id,
                            task_id_for_context,
                            root_task_id,
                        )

                    if not message_owner_id:
                        user_properties = msg_data.get("user_properties") or {}

                        if not user_properties:
                            log.warning(
                                "%s No user_properties found for task %s (root: %s). Cannot determine owner via message properties.",
                                log_id_prefix,
                                task_id_for_context,
                                root_task_id,
                            )
                        user_config = user_properties.get(
                            "a2aUserConfig"
                        ) or user_properties.get("a2a_user_config")

                        if (
                            isinstance(user_config, dict)
                            and "user_profile" in user_config
                            and isinstance(user_config.get("user_profile"), dict)
                        ):
                            message_owner_id = user_config["user_profile"].get("id")
                            if message_owner_id:
                                log.debug(
                                    "%s Found owner '%s' for task %s via message properties.",
                                    log_id_prefix,
                                    message_owner_id,
                                    task_id_for_context,
                                )
                async with self._get_visualization_lock():
                    for (
                        stream_id,
                        stream_config,
                    ) in self._active_visualization_streams.items():
                        sse_queue_for_stream = stream_config.get("sse_queue")
                        if not sse_queue_for_stream:
                            log.warning(
                                "%s SSE queue not found for stream %s. Skipping.",
                                log_id_prefix,
                                stream_id,
                            )
                            continue

                        is_permitted = False
                        stream_owner_id = stream_config.get("user_id")
                        abstract_targets = stream_config.get("abstract_targets", [])

                        for abstract_target in abstract_targets:
                            if abstract_target.status != "subscribed":
                                continue

                            if abstract_target.type == "my_a2a_messages":
                                if (
                                    stream_owner_id
                                    and message_owner_id
                                    and stream_owner_id == message_owner_id
                                ):
                                    is_permitted = True
                                    break
                            else:
                                subscribed_topics_for_stream = stream_config.get(
                                    "solace_topics", set()
                                )
                                if any(
                                    _topic_matches_subscription(topic, pattern)
                                    for pattern in subscribed_topics_for_stream
                                ):
                                    is_permitted = True
                                    break

                        if is_permitted:
                            event_details = self._infer_visualization_event_details(
                                topic, payload_dict
                            )

                            sse_event_payload = {
                                "event_type": "a2a_message",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "solace_topic": topic,
                                "direction": event_details["direction"],
                                "source_entity": event_details["source_entity"],
                                "target_entity": event_details["target_entity"],
                                "message_id": event_details["message_id"],
                                "task_id": event_details["task_id"],
                                "payload_summary": event_details["payload_summary"],
                                "full_payload": payload_dict,
                            }

                            try:
                                log.debug(
                                    "%s Attempting to put message on SSE queue for stream %s. Queue size: %d",
                                    log_id_prefix,
                                    stream_id,
                                    sse_queue_for_stream.qsize(),
                                )
                                sse_queue_for_stream.put_nowait(
                                    {
                                        "event": "a2a_message",
                                        "data": json.dumps(sse_event_payload),
                                    }
                                )
                                log.debug(
                                    "%s [VIZ_DATA_SENT] Stream %s: Topic: %s, Direction: %s",
                                    log_id_prefix,
                                    stream_id,
                                    topic,
                                    event_details["direction"],
                                )
                            except asyncio.QueueFull:
                                log.warning(
                                    "%s SSE queue full for stream %s. Visualization message dropped.",
                                    log_id_prefix,
                                    stream_id,
                                )
                            except Exception as send_err:
                                log.error(
                                    "%s Error sending formatted message to SSE queue for stream %s: %s",
                                    log_id_prefix,
                                    stream_id,
                                    send_err,
                                )
                        else:
                            pass

                self._visualization_message_queue.task_done()

            except queue.Empty:
                continue
            except asyncio.CancelledError:
                log.info(
                    "%s Visualization message processor loop cancelled.", log_id_prefix
                )
                break
            except Exception as e:
                log.exception(
                    "%s Error in visualization message processor loop: %s",
                    log_id_prefix,
                    e,
                )
                if msg_data and self._visualization_message_queue:
                    self._visualization_message_queue.task_done()
                await asyncio.sleep(1)

        log.info("%s Visualization message processor loop finished.", log_id_prefix)

    async def _add_visualization_subscription(
        self, topic_str: str, stream_id: str
    ) -> bool:
        """
        Adds a Solace topic subscription to the internal BrokerInput for visualization.
        Manages global subscription reference counts.
        """
        log_id_prefix = f"{self.log_identifier}[AddVizSub:{stream_id}]"
        log.info(
            "%s Attempting to add subscription to topic: %s", log_id_prefix, topic_str
        )

        if not self._visualization_broker_input:
            log.error(
                "%s Visualization BrokerInput is not initialized. Cannot add subscription.",
                log_id_prefix,
            )
            return False
        if (
            not hasattr(self._visualization_broker_input, "messaging_service")
            or not self._visualization_broker_input.messaging_service
        ):
            log.error(
                "%s Visualization BrokerInput's messaging_service not available or not initialized. Cannot add subscription.",
                log_id_prefix,
            )
            return False

        log.debug(
            "%s Acquiring visualization stream lock for topic '%s'...",
            log_id_prefix,
            topic_str,
        )
        async with self._get_visualization_lock():
            log.debug(
                "%s Acquired visualization stream lock for topic '%s'.",
                log_id_prefix,
                topic_str,
            )
            self._global_visualization_subscriptions[topic_str] = (
                self._global_visualization_subscriptions.get(topic_str, 0) + 1
            )
            log.debug(
                "%s Global subscription count for topic '%s' is now %d.",
                log_id_prefix,
                topic_str,
                self._global_visualization_subscriptions[topic_str],
            )

            if self._global_visualization_subscriptions[topic_str] == 1:
                log.info(
                    "%s First global subscription for topic '%s'. Attempting to subscribe on broker.",
                    log_id_prefix,
                    topic_str,
                )
                try:
                    if not hasattr(
                        self._visualization_broker_input, "add_subscription"
                    ) or not callable(
                        getattr(self._visualization_broker_input, "add_subscription")
                    ):
                        log.error(
                            "%s Visualization BrokerInput does not support dynamic 'add_subscription'. "
                            "Please upgrade the 'solace-ai-connector' module. Cannot add subscription '%s'.",
                            log_id_prefix,
                            topic_str,
                        )
                        self._global_visualization_subscriptions[topic_str] -= 1
                        if self._global_visualization_subscriptions[topic_str] == 0:
                            del self._global_visualization_subscriptions[topic_str]
                        return False

                    loop = asyncio.get_event_loop()
                    add_result = await loop.run_in_executor(
                        None,
                        self._visualization_broker_input.add_subscription,
                        topic_str,
                    )
                    if not add_result:
                        log.error(
                            "%s Failed to add subscription '%s' via BrokerInput.",
                            log_id_prefix,
                            topic_str,
                        )
                        self._global_visualization_subscriptions[topic_str] -= 1
                        if self._global_visualization_subscriptions[topic_str] == 0:
                            del self._global_visualization_subscriptions[topic_str]
                        return False
                    log.info(
                        "%s Successfully added subscription '%s' via BrokerInput.",
                        log_id_prefix,
                        topic_str,
                    )
                except Exception as e:
                    log.exception(
                        "%s Exception calling BrokerInput.add_subscription for topic '%s': %s",
                        log_id_prefix,
                        topic_str,
                        e,
                    )
                    self._global_visualization_subscriptions[topic_str] -= 1
                    if self._global_visualization_subscriptions[topic_str] == 0:
                        del self._global_visualization_subscriptions[topic_str]
                    return False
            else:
                log.debug(
                    "%s Topic '%s' already globally subscribed. Skipping broker subscribe.",
                    log_id_prefix,
                    topic_str,
                )

            if stream_id in self._active_visualization_streams:
                self._active_visualization_streams[stream_id]["solace_topics"].add(
                    topic_str
                )
                log.debug(
                    "%s Topic '%s' added to active subscriptions for stream %s.",
                    log_id_prefix,
                    topic_str,
                    stream_id,
                )
            else:
                log.warning(
                    "%s Stream ID %s not found in active streams. Cannot add topic.",
                    log_id_prefix,
                    stream_id,
                )
                return False
        log.debug(
            "%s Releasing visualization stream lock after successful processing for topic '%s'.",
            log_id_prefix,
            topic_str,
        )
        return True

    async def _remove_visualization_subscription_nolock(
        self, topic_str: str, stream_id: str
    ) -> bool:
        """
        Internal helper to remove a Solace topic subscription.
        Assumes _visualization_stream_lock is already held by the caller.
        Manages global subscription reference counts.
        """
        log_id_prefix = f"{self.log_identifier}[RemoveVizSubNL:{stream_id}]"
        log.info(
            "%s Removing subscription (no-lock) from topic: %s",
            log_id_prefix,
            topic_str,
        )

        if not self._visualization_broker_input or not hasattr(
            self._visualization_broker_input, "messaging_service"
        ):
            log.error(
                "%s Visualization BrokerInput or its messaging_service not available.",
                log_id_prefix,
            )
            return False

        if topic_str not in self._global_visualization_subscriptions:
            log.warning(
                "%s Topic '%s' not found in global subscriptions. Cannot remove.",
                log_id_prefix,
                topic_str,
            )
            return False

        self._global_visualization_subscriptions[topic_str] -= 1

        if self._global_visualization_subscriptions[topic_str] == 0:
            del self._global_visualization_subscriptions[topic_str]
            try:
                if not hasattr(
                    self._visualization_broker_input, "remove_subscription"
                ) or not callable(
                    getattr(self._visualization_broker_input, "remove_subscription")
                ):
                    log.error(
                        "%s Visualization BrokerInput does not support dynamic 'remove_subscription'. "
                        "Please upgrade the 'solace-ai-connector' module. Cannot remove subscription '%s'.",
                        log_id_prefix,
                        topic_str,
                    )
                    return False

                loop = asyncio.get_event_loop()
                remove_result = await loop.run_in_executor(
                    None,
                    self._visualization_broker_input.remove_subscription,
                    topic_str,
                )
                if not remove_result:
                    log.error(
                        "%s Failed to remove subscription '%s' via BrokerInput. Global count might be inaccurate.",
                        log_id_prefix,
                        topic_str,
                    )
                else:
                    log.info(
                        "%s Successfully removed subscription '%s' via BrokerInput.",
                        log_id_prefix,
                        topic_str,
                    )
            except Exception as e:
                log.exception(
                    "%s Exception calling BrokerInput.remove_subscription for topic '%s': %s",
                    log_id_prefix,
                    topic_str,
                    e,
                )

        if stream_id in self._active_visualization_streams:
            if (
                topic_str
                in self._active_visualization_streams[stream_id]["solace_topics"]
            ):
                self._active_visualization_streams[stream_id]["solace_topics"].remove(
                    topic_str
                )
                log.debug(
                    "%s Topic '%s' removed from active subscriptions for stream %s.",
                    log_id_prefix,
                    topic_str,
                    stream_id,
                )
            else:
                log.warning(
                    "%s Topic '%s' not found in subscriptions for stream %s.",
                    log_id_prefix,
                    topic_str,
                    stream_id,
                )
        else:
            log.warning(
                "%s Stream ID %s not found in active streams. Cannot remove topic.",
                log_id_prefix,
                stream_id,
            )
        return True

    async def _remove_visualization_subscription(
        self, topic_str: str, stream_id: str
    ) -> bool:
        """
        Public method to remove a Solace topic subscription.
        Acquires the lock before calling the internal no-lock version.
        """
        log_id_prefix = f"{self.log_identifier}[RemoveVizSubPub:{stream_id}]"
        log.debug(
            "%s Acquiring lock to remove subscription for topic: %s",
            log_id_prefix,
            topic_str,
        )
        async with self._get_visualization_lock():
            log.debug("%s Lock acquired for topic: %s", log_id_prefix, topic_str)
            result = await self._remove_visualization_subscription_nolock(
                topic_str, stream_id
            )
            log.debug("%s Releasing lock for topic: %s", log_id_prefix, topic_str)
            return result

    async def _extract_initial_claims(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts initial identity claims from the incoming external event.
        For the WebUI, this means inspecting the FastAPIRequest.
        It prioritizes the authenticated user from `request.state.user`.
        """
        log_id_prefix = f"{self.log_identifier}[ExtractClaims]"

        if not isinstance(external_event_data, FastAPIRequest):
            log.warning(
                "%s Expected external_event_data to be a FastAPIRequest, but got %s.",
                log_id_prefix,
                type(external_event_data).__name__,
            )
            return None

        request = external_event_data
        try:
            if hasattr(request.state, "user") and request.state.user:
                user_info = request.state.user
                username = user_info.get("username")
                if username:
                    log.debug(
                        "%s Extracted user '%s' from request.state.",
                        log_id_prefix,
                        username,
                    )
                    return {"id": username, "name": username, "email": username}

            log.debug(
                "%s No authenticated user in request.state, falling back to SessionManager.",
                log_id_prefix,
            )
            user_id = self.session_manager.get_a2a_client_id(request)
            log.debug(
                "%s Extracted user_id '%s' via SessionManager.", log_id_prefix, user_id
            )
            return {"id": user_id, "name": user_id}

        except Exception as e:
            log.error("%s Failed to extract user_id from request: %s", log_id_prefix, e)
            return None

    def _start_fastapi_server(self):
        """Starts the Uvicorn server in a separate thread."""
        log.info(
            "%s [_start_listener] Attempting to start FastAPI/Uvicorn server...",
            self.log_identifier,
        )
        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.warning(
                "%s FastAPI server thread already started.", self.log_identifier
            )
            return

        try:
            from ...gateway.http_sse.main import (
                app as fastapi_app_instance,
            )
            from ...gateway.http_sse.main import (
                setup_dependencies,
            )

            self.fastapi_app = fastapi_app_instance

            setup_dependencies(self)

            port = self.fastapi_https_port if self.ssl_keyfile and self.ssl_certfile else self.fastapi_port

            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.fastapi_host,
                port=port,
                log_level="info",
                lifespan="on",
                ssl_keyfile=self.ssl_keyfile,
                ssl_certfile=self.ssl_certfile,
                ssl_keyfile_password=self.ssl_keyfile_password,
            )
            self.uvicorn_server = uvicorn.Server(config)

            @self.fastapi_app.on_event("startup")
            async def capture_event_loop():
                log.info(
                    "%s [_start_listener] FastAPI startup event triggered.",
                    self.log_identifier,
                )
                try:
                    self.fastapi_event_loop = asyncio.get_running_loop()
                    log.info(
                        "%s [_start_listener] Captured FastAPI event loop via startup event: %s",
                        self.log_identifier,
                        self.fastapi_event_loop,
                    )

                    if self.fastapi_event_loop:
                        log.info(
                            "%s Ensuring visualization flow is running...",
                            self.log_identifier,
                        )
                        self._ensure_visualization_flow_is_running()

                        if (
                            self._visualization_processor_task is None
                            or self._visualization_processor_task.done()
                        ):
                            log.info(
                                "%s Starting visualization message processor task.",
                                self.log_identifier,
                            )
                            self._visualization_processor_task = (
                                self.fastapi_event_loop.create_task(
                                    self._visualization_message_processor_loop()
                                )
                            )
                        else:
                            log.info(
                                "%s Visualization message processor task already running.",
                                self.log_identifier,
                            )
                    else:
                        log.error(
                            "%s FastAPI event loop not captured. Cannot start visualization processor.",
                            self.log_identifier,
                        )

                except Exception as startup_err:
                    log.exception(
                        "%s [_start_listener] Error during FastAPI startup event (capture_event_loop or viz setup): %s",
                        self.log_identifier,
                        startup_err,
                    )
                    self.stop_signal.set()

            @self.fastapi_app.on_event("shutdown")
            async def shutdown_event():
                log.info(
                    "%s [_start_listener] FastAPI shutdown event triggered.",
                    self.log_identifier,
                )

            self.fastapi_thread = threading.Thread(
                target=self.uvicorn_server.run, daemon=True, name="FastAPI_Thread"
            )
            self.fastapi_thread.start()
            protocol = "https" if self.ssl_keyfile and self.ssl_certfile else "http"
            log.info(
                "%s [_start_listener] FastAPI/Uvicorn server starting in background thread on %s://%s:%d",
                self.log_identifier,
                protocol,
                self.fastapi_host,
                port,
            )

        except Exception as e:
            log.exception(
                "%s [_start_listener] Failed to start FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
            raise

    def publish_a2a(
        self, topic: str, payload: Dict, user_properties: Optional[Dict] = None
    ):
        """
        Publishes an A2A message using the SAC App's send_message method.
        This method can be called from FastAPI handlers (via dependency injection).
        It's thread-safe as it uses the SAC App instance.
        """
        super().publish_a2a_message(topic, payload, user_properties)

    def _cleanup_visualization_locks(self):
        """Remove locks for closed event loops to prevent memory leaks."""
        with self._visualization_locks_lock:
            closed_loops = [
                loop for loop in self._visualization_locks if loop.is_closed()
            ]
            for loop in closed_loops:
                del self._visualization_locks[loop]
                log.debug(
                    "%s Cleaned up visualization lock for closed event loop %s",
                    self.log_identifier,
                    id(loop),
                )

    def cleanup(self):
        """Gracefully shuts down the component and the FastAPI server."""
        log.info("%s Cleaning up Web UI Backend Component...", self.log_identifier)
        log.info("%s Cleaning up visualization resources...", self.log_identifier)
        if self._visualization_message_queue:
            self._visualization_message_queue.put(None)

        if (
            self._visualization_processor_task
            and not self._visualization_processor_task.done()
        ):
            log.info(
                "%s Cancelling visualization processor task...", self.log_identifier
            )
            self._visualization_processor_task.cancel()

        if self._visualization_internal_app:
            log.info(
                "%s Cleaning up internal visualization app...", self.log_identifier
            )
            try:
                self._visualization_internal_app.cleanup()
            except Exception as e:
                log.error(
                    "%s Error cleaning up internal visualization app: %s",
                    self.log_identifier,
                    e,
                )

        self._active_visualization_streams.clear()
        self._global_visualization_subscriptions.clear()
        self._cleanup_visualization_locks()
        log.info("%s Visualization resources cleaned up.", self.log_identifier)

    def _infer_visualization_event_details(
        self, topic: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Infers details for the visualization SSE payload from the Solace topic and A2A message.
        """
        details = {
            "direction": "unknown",
            "source_entity": "unknown",
            "target_entity": "unknown",
            "message_id": payload.get("id"),
            "task_id": None,
            "payload_summary": {
                "method": payload.get("method", "N/A"),
                "params_preview": None,
            },
        }

        topic_parts = topic.split("/")

        try:
            a2a_base_index = topic_parts.index("a2a")
            domain_index = a2a_base_index + 2
            action_type_index = a2a_base_index + 3
            entity_name_index = a2a_base_index + 4
            task_id_from_topic_index = a2a_base_index + 5

            domain = (
                topic_parts[domain_index] if len(topic_parts) > domain_index else None
            )
            action_type = (
                topic_parts[action_type_index]
                if len(topic_parts) > action_type_index
                else None
            )
            entity_name = (
                topic_parts[entity_name_index]
                if len(topic_parts) > entity_name_index
                else None
            )

            if domain == "agent":
                if action_type == "request":
                    details["direction"] = "request"
                    details["target_entity"] = entity_name
                    user_props = (
                        payload.get("params", {})
                        .get("metadata", {})
                        .get("solaceUserProperties", {})
                    )
                    details["source_entity"] = (
                        user_props.get("clientId")
                        or user_props.get("delegating_agent_name")
                        or self.gateway_id
                    )
                elif action_type == "response":
                    details["direction"] = "response"
                    details["source_entity"] = entity_name
                    details["target_entity"] = (
                        payload.get("result", {}).get("metadata", {}).get("clientId")
                    )
                elif action_type == "status":
                    details["direction"] = "status_update"
                    details["source_entity"] = entity_name
                    details["target_entity"] = (
                        payload.get("result", {}).get("metadata", {}).get("clientId")
                    )
            elif domain == "gateway":
                if action_type == "response":
                    details["direction"] = "response"
                    details["source_entity"] = (
                        payload.get("result", {})
                        .get("status", {})
                        .get("message", {})
                        .get("metadata", {})
                        .get("agent_name", "unknown_agent")
                    )
                    details["target_entity"] = entity_name
                elif action_type == "status":
                    details["direction"] = "status_update"
                    details["source_entity"] = (
                        payload.get("result", {})
                        .get("status", {})
                        .get("message", {})
                        .get("metadata", {})
                        .get("agent_name", "unknown_agent")
                    )
                    details["target_entity"] = entity_name
            elif domain == "discovery" and action_type == "agentcards":
                details["direction"] = "discovery"
                details["source_entity"] = payload.get("name", "unknown_agent")
                details["target_entity"] = "broadcast"

            if payload.get("method") in [
                "tasks/send",
                "tasks/sendSubscribe",
                "tasks/cancel",
            ]:
                details["task_id"] = payload.get("params", {}).get("id")
            elif "result" in payload and isinstance(payload["result"], dict):
                details["task_id"] = payload["result"].get("id")
            elif len(topic_parts) > task_id_from_topic_index and (
                action_type == "status" or action_type == "response"
            ):
                details["task_id"] = topic_parts[task_id_from_topic_index]

        except (ValueError, IndexError):
            log.debug(
                "%s Could not parse A2A structure from topic: %s",
                self.log_identifier,
                topic,
            )
            if "request" in topic:
                details["direction"] = "request"
            elif "response" in topic:
                details["direction"] = "response"
            elif "status" in topic:
                details["direction"] = "status_update"
            elif "discovery" in topic:
                details["direction"] = "discovery"

        if "params" in payload:
            params_str = json.dumps(payload["params"])
            details["payload_summary"]["params_preview"] = (
                (params_str[:100] + "...") if len(params_str) > 100 else params_str
            )
        elif "result" in payload:
            result_str = json.dumps(payload["result"])
            details["payload_summary"]["params_preview"] = (
                (result_str[:100] + "...") if len(result_str) > 100 else result_str
            )
        elif "error" in payload:
            details["payload_summary"]["method"] = "JSONRPCError"
            error_str = json.dumps(payload["error"])
            details["payload_summary"]["params_preview"] = (
                (error_str[:100] + "...") if len(error_str) > 100 else error_str
            )

        return details

    def _extract_involved_agents_for_viz(
        self, topic: str, payload_dict: Dict[str, Any]
    ) -> Set[str]:
        """
        Extracts agent names involved in a message from its topic and payload.
        """
        agents: Set[str] = set()
        log_id_prefix = f"{self.log_identifier}[ExtractAgentsViz]"

        topic_agent_match = re.match(
            rf"^{re.escape(self.namespace)}/a2a/v1/agent/(?:request|response|status)/([^/]+)",
            topic,
        )
        if topic_agent_match:
            agents.add(topic_agent_match.group(1))
            log.debug(
                "%s Found agent '%s' in topic.",
                log_id_prefix,
                topic_agent_match.group(1),
            )

        if isinstance(payload_dict, dict):
            if (
                "name" in payload_dict
                and "capabilities" in payload_dict
                and "skills" in payload_dict
            ):
                try:
                    card = AgentCard(**payload_dict)
                    if card.name:
                        agents.add(card.name)
                        log.debug(
                            "%s Found agent '%s' in AgentCard payload.",
                            log_id_prefix,
                            card.name,
                        )
                except Exception:
                    pass
            result = payload_dict.get("result")
            if isinstance(result, dict):
                status_info = result.get("status")
                if isinstance(status_info, dict):
                    message_info = status_info.get("message")
                    if isinstance(message_info, dict):
                        metadata = message_info.get("metadata")
                        if isinstance(metadata, dict) and "agent_name" in metadata:
                            if metadata["agent_name"]:
                                agents.add(metadata["agent_name"])
                                log.debug(
                                    "%s Found agent '%s' in status.message.metadata.",
                                    log_id_prefix,
                                    metadata["agent_name"],
                                )

                artifact_info = result.get("artifact")
                if isinstance(artifact_info, dict):
                    metadata = artifact_info.get("metadata")
                    if isinstance(metadata, dict) and "agent_name" in metadata:
                        if metadata["agent_name"]:
                            agents.add(metadata["agent_name"])
                            log.debug(
                                "%s Found agent '%s' in artifact.metadata.",
                                log_id_prefix,
                                metadata["agent_name"],
                            )

            params = payload_dict.get("params")
            if isinstance(params, dict):
                message_info = params.get("message")
                if isinstance(message_info, dict):
                    metadata = message_info.get("metadata")
                    if isinstance(metadata, dict) and "agent_name" in metadata:
                        if metadata["agent_name"]:
                            agents.add(metadata["agent_name"])
                            log.debug(
                                "%s Found agent '%s' in params.message.metadata.",
                                log_id_prefix,
                                metadata["agent_name"],
                            )

        if not agents:
            log.debug(
                "%s No specific agents identified from topic '%s' or payload.",
                log_id_prefix,
                topic,
            )
        return agents

        super().cleanup()

        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.info(
                "%s Waiting for FastAPI server thread to exit...", self.log_identifier
            )
            self.fastapi_thread.join(timeout=10)
            if self.fastapi_thread.is_alive():
                log.warning(
                    "%s FastAPI server thread did not exit gracefully.",
                    self.log_identifier,
                )

        if self.sse_manager:
            log.info(
                "%s Closing active SSE connections (best effort)...",
                self.log_identifier,
            )
            try:
                asyncio.run(self.sse_manager.close_all())
            except Exception as sse_close_err:
                log.error(
                    "%s Error closing SSE connections during cleanup: %s",
                    self.log_identifier,
                    sse_close_err,
                )

        log.info("%s Web UI Backend Component cleanup finished.", self.log_identifier)

    def get_agent_registry(self) -> AgentRegistry:
        return self.agent_registry

    def get_sse_manager(self) -> SSEManager:
        return self.sse_manager

    def get_session_manager(self) -> SessionManager:
        return self.session_manager

    def get_namespace(self) -> str:
        return self.namespace

    def get_gateway_id(self) -> str:
        """Returns the unique identifier for this gateway instance."""
        return self.gateway_id

    def get_cors_origins(self) -> List[str]:
        return self.cors_allowed_origins

    def get_shared_artifact_service(self) -> Optional[BaseArtifactService]:
        return self.shared_artifact_service

    def get_embed_config(self) -> Dict[str, Any]:
        """Returns embed-related configuration needed by dependencies."""
        return {
            "enable_embed_resolution": self.enable_embed_resolution,
            "gateway_max_artifact_resolve_size_bytes": self.gateway_max_artifact_resolve_size_bytes,
            "gateway_recursive_embed_depth": self.gateway_recursive_embed_depth,
        }

    def get_core_a2a_service(self) -> CoreA2AService:
        """Returns the CoreA2AService instance."""
        return self.core_a2a_service

    def get_config_resolver(self) -> ConfigResolver:
        """Returns the instance of the ConfigResolver."""
        return self._config_resolver

    def _start_listener(self) -> None:
        """
        GDK Hook: Starts the FastAPI/Uvicorn server.
        This method is called by BaseGatewayComponent.run().
        """
        self._start_fastapi_server()

    def _stop_listener(self) -> None:
        """
        GDK Hook: Signals the Uvicorn server to shut down.
        This method is called by BaseGatewayComponent.cleanup().
        """
        log.info(
            "%s _stop_listener called. Signaling Uvicorn server to exit.",
            self.log_identifier,
        )
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True
        pass

    async def _translate_external_input(
        self, external_event_data: Dict[str, Any]
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
        """
        Translates raw HTTP request data (from FastAPI form) into A2A task parameters.

        Args:
            external_event_data: A dictionary containing data from the HTTP request,
                                 expected to have keys like 'agent_name', 'message',
                                 'files' (List[UploadFile]), 'client_id', 'a2a_session_id'.

        Returns:
            A tuple containing:
            - target_agent_name (str): The name of the A2A agent to target.
            - a2a_parts (List[A2APart]): A list of A2A Part objects for the message.
            - external_request_context (Dict[str, Any]): Context for TaskContextManager.
        """
        log_id_prefix = f"{self.log_identifier}[TranslateInput]"
        log.debug(
            "%s Received external event data: %s",
            log_id_prefix,
            {k: type(v) for k, v in external_event_data.items()},
        )

        target_agent_name: str = external_event_data.get("agent_name")
        user_message: str = external_event_data.get("message", "")
        files: Optional[List[UploadFile]] = external_event_data.get("files")
        client_id: str = external_event_data.get("client_id")
        a2a_session_id: str = external_event_data.get("a2a_session_id")

        if not target_agent_name:
            raise ValueError("Target agent name is missing in external_event_data.")
        if not client_id or not a2a_session_id:
            raise ValueError(
                "Client ID or A2A Session ID is missing in external_event_data."
            )

        a2a_parts: List[A2APart] = []

        if files and self.shared_artifact_service:
            file_metadata_summary_parts = []
            for upload_file in files:
                try:
                    content_bytes = await upload_file.read()
                    if not content_bytes:
                        log.warning(
                            "%s Skipping empty uploaded file: %s",
                            log_id_prefix,
                            upload_file.filename,
                        )
                        continue
                    save_result = await save_artifact_with_metadata(
                        artifact_service=self.shared_artifact_service,
                        app_name=self.gateway_id,
                        user_id=client_id,
                        session_id=a2a_session_id,
                        filename=upload_file.filename,
                        content_bytes=content_bytes,
                        mime_type=upload_file.content_type
                        or "application/octet-stream",
                        metadata_dict={
                            "source": "webui_gateway_upload",
                            "original_filename": upload_file.filename,
                            "upload_timestamp_utc": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "gateway_id": self.gateway_id,
                            "web_client_id": client_id,
                            "a2a_session_id": a2a_session_id,
                        },
                        timestamp=datetime.now(timezone.utc),
                    )

                    if save_result["status"] in ["success", "partial_success"]:
                        data_version = save_result.get("data_version", 0)
                        artifact_uri = f"artifact://{self.gateway_id}/{client_id}/{a2a_session_id}/{upload_file.filename}?version={data_version}"
                        file_content = FileContent(
                            name=upload_file.filename,
                            mimeType=upload_file.content_type,
                            uri=artifact_uri,
                        )
                        a2a_parts.append(FilePart(file=file_content))
                        file_metadata_summary_parts.append(
                            f"- {upload_file.filename} ({upload_file.content_type}, {len(content_bytes)} bytes, URI: {artifact_uri})"
                        )
                        log.info(
                            "%s Processed and created URI for uploaded file: %s",
                            log_id_prefix,
                            artifact_uri,
                        )
                    else:
                        log.error(
                            "%s Failed to save artifact %s: %s",
                            log_id_prefix,
                            upload_file.filename,
                            save_result.get("message"),
                        )

                except Exception as e:
                    log.exception(
                        "%s Error processing uploaded file %s: %s",
                        log_id_prefix,
                        upload_file.filename,
                        e,
                    )
                finally:
                    await upload_file.close()

            if file_metadata_summary_parts:
                user_message = (
                    "The user uploaded the following file(s):\n"
                    + "\n".join(file_metadata_summary_parts)
                    + f"\n\nUser message: {user_message}"
                )

        if user_message:
            a2a_parts.append(TextPart(text=user_message))

        external_request_context = {
            "app_name_for_artifacts": self.gateway_id,
            "user_id_for_artifacts": client_id,
            "a2a_session_id": a2a_session_id,
            "user_id_for_a2a": client_id,
            "target_agent_name": target_agent_name,
        }
        log.debug(
            "%s Translated input. Target: %s, Parts: %d, Context: %s",
            log_id_prefix,
            target_agent_name,
            len(a2a_parts),
            external_request_context,
        )
        return target_agent_name, a2a_parts, external_request_context

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        """
        Sends an intermediate update (TaskStatusUpdateEvent or TaskArtifactUpdateEvent)
        to the external platform (Web UI via SSE).
        """
        log_id_prefix = f"{self.log_identifier}[SendUpdate]"
        sse_task_id = external_request_context.get("a2a_task_id_for_event")
        a2a_task_id = event_data.id

        if not sse_task_id:
            log.error(
                "%s Cannot send update: 'a2a_task_id_for_event' missing from external_request_context.",
                log_id_prefix,
            )
            return

        log.debug(
            "%s Sending update for A2A Task ID %s to SSE Task ID %s. Final chunk: %s",
            log_id_prefix,
            a2a_task_id,
            sse_task_id,
            is_final_chunk_of_update,
        )

        sse_event_type = "status_update"
        if isinstance(event_data, TaskArtifactUpdateEvent):
            sse_event_type = "artifact_update"

        sse_payload = JSONRPCResponse(id=a2a_task_id, result=event_data).model_dump(
            exclude_none=True
        )

        try:
            await self.sse_manager.send_event(
                task_id=sse_task_id, event_data=sse_payload, event_type=sse_event_type
            )
            log.info(
                "%s Successfully sent %s via SSE for A2A Task ID %s.",
                log_id_prefix,
                sse_event_type,
                a2a_task_id,
            )
        except Exception as e:
            log.exception(
                "%s Failed to send %s via SSE for A2A Task ID %s: %s",
                log_id_prefix,
                sse_event_type,
                a2a_task_id,
                e,
            )

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        """
        Sends the final A2A Task result to the external platform (Web UI via SSE).
        """
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        sse_task_id = external_request_context.get("a2a_task_id_for_event")
        a2a_task_id = task_data.id

        if not sse_task_id:
            log.error(
                "%s Cannot send final response: 'a2a_task_id_for_event' missing from external_request_context.",
                log_id_prefix,
            )
            return

        log.debug(
            "%s Sending final response for A2A Task ID %s to SSE Task ID %s.",
            log_id_prefix,
            a2a_task_id,
            sse_task_id,
        )

        sse_payload = JSONRPCResponse(id=a2a_task_id, result=task_data).model_dump(
            exclude_none=True
        )

        try:
            await self.sse_manager.send_event(
                task_id=sse_task_id, event_data=sse_payload, event_type="final_response"
            )
            log.info(
                "%s Successfully sent final_response via SSE for A2A Task ID %s.",
                log_id_prefix,
                a2a_task_id,
            )
        except Exception as e:
            log.exception(
                "%s Failed to send final_response via SSE for A2A Task ID %s: %s",
                log_id_prefix,
                a2a_task_id,
                e,
            )
        finally:
            await self.sse_manager.close_all_for_task(sse_task_id)
            log.info(
                "%s Closed SSE connections for SSE Task ID %s.",
                log_id_prefix,
                sse_task_id,
            )

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        """
        Sends an error notification to the external platform (Web UI via SSE).
        """
        log_id_prefix = f"{self.log_identifier}[SendError]"
        sse_task_id = external_request_context.get("a2a_task_id_for_event")

        if not sse_task_id:
            log.error(
                "%s Cannot send error: 'a2a_task_id_for_event' missing from external_request_context.",
                log_id_prefix,
            )
            return

        log.debug(
            "%s Sending error to SSE Task ID %s. Error: %s",
            log_id_prefix,
            sse_task_id,
            error_data,
        )

        sse_payload = JSONRPCResponse(
            id=external_request_context.get("original_rpc_id", sse_task_id),
            error=error_data,
        ).model_dump(exclude_none=True)

        try:
            await self.sse_manager.send_event(
                task_id=sse_task_id, event_data=sse_payload, event_type="final_response"
            )
            log.info(
                "%s Successfully sent A2A error as 'final_response' via SSE for SSE Task ID %s.",
                log_id_prefix,
                sse_task_id,
            )
        except Exception as e:
            log.exception(
                "%s Failed to send error via SSE for SSE Task ID %s: %s",
                log_id_prefix,
                sse_task_id,
                e,
            )
        finally:
            await self.sse_manager.close_all_for_task(sse_task_id)
            log.info(
                "%s Closed SSE connections for SSE Task ID %s after error.",
                log_id_prefix,
                sse_task_id,
            )
