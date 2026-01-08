"""
Custom Solace AI Connector Component to host the FastAPI backend for the Web UI.
"""

import asyncio
import json
import logging
import queue
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, UploadFile
from fastapi import Request as FastAPIRequest
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.components.inputs_outputs.broker_input import BrokerInput
from solace_ai_connector.flow.app import App as SACApp

from ...common.agent_registry import AgentRegistry
from ...core_a2a.service import CoreA2AService
from ...gateway.base.component import BaseGatewayComponent
from ...gateway.http_sse.session_manager import SessionManager
from ...gateway.http_sse.sse_manager import SSEManager
from . import dependencies
from .components import VisualizationForwarderComponent
from .components.task_logger_forwarder import TaskLoggerForwarderComponent
from .services.task_logger_service import TaskLoggerService
from .sse_event_buffer import SSEEventBuffer

log = logging.getLogger(__name__)

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


from a2a.types import (
    A2ARequest,
    AgentCard,
    JSONRPCError,
    JSONRPCResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)

from ...common import a2a
from ...common.a2a.types import ContentPart
from ...common.middleware.config_resolver import ConfigResolver
from ...common.utils.embeds import (
    EARLY_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_in_string,
)

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
        component_config = kwargs.get("component_config", {})
        app_config = component_config.get("app_config", {})
        resolve_uris = app_config.get("resolve_artifact_uris_in_gateway", True)

        # HTTP SSE gateway configuration:
        # - supports_inline_artifact_resolution=True: Artifacts are converted to FileParts
        #   during embed resolution and rendered inline in the web UI
        # - filter_tool_data_parts=False: Web UI displays all parts including tool execution details
        super().__init__(
            resolve_artifact_uris_in_gateway=resolve_uris,
            supports_inline_artifact_resolution=True,
            filter_tool_data_parts=False,
            **kwargs
        )
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
            self.ssl_keyfile = self.get_config("ssl_keyfile", "")
            self.ssl_certfile = self.get_config("ssl_certfile", "")
            self.ssl_keyfile_password = self.get_config("ssl_keyfile_password", "")
            self.model_config = self.get_config("model", None)

            log.info(
                "%s WebUI-specific configuration retrieved (Host: %s, Port: %d).",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
            )
        except Exception as e:
            log.error("%s Failed to retrieve configuration: %s", self.log_identifier, e)
            raise ValueError(f"Configuration retrieval error: {e}") from e

        self.sse_max_queue_size = self.get_config("sse_max_queue_size", 200)
        sse_buffer_max_age_seconds = self.get_config("sse_buffer_max_age_seconds", 600)

        self.sse_event_buffer = SSEEventBuffer(
            max_queue_size=self.sse_max_queue_size,
            max_age_seconds=sse_buffer_max_age_seconds,
        )
        # SSE manager will be initialized after database setup
        self.sse_manager = None

        self._sse_cleanup_timer_id = f"sse_cleanup_{self.gateway_id}"
        cleanup_interval_sec = self.get_config(
            "sse_buffer_cleanup_interval_seconds", 300
        )
        self.add_timer(
            delay_ms=cleanup_interval_sec * 1000,
            timer_id=self._sse_cleanup_timer_id,
            interval_ms=cleanup_interval_sec * 1000,
        )

        # Set up health check timer for agent registry
        from ...common.constants import HEALTH_CHECK_INTERVAL_SECONDS

        self.health_check_timer_id = f"agent_health_check_{self.gateway_id}"
        health_check_interval_seconds = self.get_config(
            "agent_health_check_interval_seconds", HEALTH_CHECK_INTERVAL_SECONDS
        )
        if health_check_interval_seconds > 0:
            log.info(
                "%s Scheduling agent health check every %d seconds.",
                self.log_identifier,
                health_check_interval_seconds,
            )
            self.add_timer(
                delay_ms=health_check_interval_seconds * 1000,
                timer_id=self.health_check_timer_id,
                interval_ms=health_check_interval_seconds * 1000,
            )
        else:
            log.warning(
                "%s Agent health check interval not configured or invalid, health checks will not run periodically.",
                self.log_identifier,
            )

        session_config = self._resolve_session_config()
        if session_config.get("type") == "sql":
            # SQL type explicitly configured - database_url is required
            database_url = session_config.get("database_url")
            if not database_url:
                raise ValueError(
                    f"{self.log_identifier} Session service type is 'sql' but no database_url provided. "
                    "Please provide a database_url in the session_service configuration or use type 'memory'."
                )
            self.database_url = database_url
        else:
            # Memory storage or no explicit configuration - no persistence service needed
            self.database_url = None

        # Validate that features requiring runtime database persistence are not enabled without database
        if self.database_url is None:
            task_logging_config = self.get_config("task_logging", {})
            if task_logging_config.get("enabled", False):
                raise ValueError(
                    f"{self.log_identifier} Task logging requires SQL session storage. "
                    "Either set session_service.type='sql' with a valid database_url, "
                    "or disable task_logging.enabled."
                )

            feedback_config = self.get_config("feedback_publishing", {})
            if feedback_config.get("enabled", False):
                log.warning(
                    "%s Feedback publishing is enabled but database persistence is not configured. "
                    "Feedback will only be published to the broker, not stored locally.",
                    self.log_identifier,
                )

        platform_config = self.get_config("platform_service", {})
        self.platform_database_url = platform_config.get("database_url")
        component_config = self.get_config("component_config", {})
        app_config = component_config.get("app_config", {})

        self.session_manager = SessionManager(
            secret_key=self.session_secret_key,
            app_config=app_config,
        )

        self.fastapi_app: FastAPI | None = None
        self.uvicorn_server: uvicorn.Server | None = None
        self.fastapi_thread: threading.Thread | None = None
        self.fastapi_event_loop: asyncio.AbstractEventLoop | None = None

        self._visualization_internal_app: SACApp | None = None
        self._visualization_broker_input: BrokerInput | None = None
        self._visualization_message_queue: queue.Queue = queue.Queue(maxsize=200)
        self._task_logger_queue: queue.Queue = queue.Queue(maxsize=200)
        self._active_visualization_streams: dict[str, dict[str, Any]] = {}
        self._visualization_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._visualization_locks_lock = threading.Lock()
        self._global_visualization_subscriptions: dict[str, int] = {}
        self._visualization_processor_task: asyncio.Task | None = None

        self._task_logger_internal_app: SACApp | None = None
        self._task_logger_broker_input: BrokerInput | None = None
        self._task_logger_processor_task: asyncio.Task | None = None
        self.task_logger_service: TaskLoggerService | None = None
        
        # Background task monitor
        self.background_task_monitor = None
        self._background_task_monitor_timer_id = None

        # Initialize SAM Events service for system events
        from ...common.sam_events import SamEventService

        self.sam_events = SamEventService(
            namespace=self.namespace,
            component_name=f"{self.name}_gateway",
            publish_func=self.publish_a2a,
        )

        # Initialize data retention service and timer
        self.data_retention_service = None
        self._data_retention_timer_id = None
        data_retention_config = self.get_config("data_retention", {})
        if data_retention_config.get("enabled", True):
            log.info(
                "%s Data retention is enabled. Initializing service and timer...",
                self.log_identifier,
            )

            # Import and initialize the DataRetentionService
            from .services.data_retention_service import DataRetentionService

            session_factory = None
            if self.database_url:
                # SessionLocal will be initialized later in setup_dependencies
                # We'll pass a lambda that returns SessionLocal when called
                session_factory = lambda: (
                    dependencies.SessionLocal() if dependencies.SessionLocal else None
                )

            self.data_retention_service = DataRetentionService(
                session_factory=session_factory, config=data_retention_config
            )

            # Create and start the cleanup timer
            cleanup_interval_hours = data_retention_config.get(
                "cleanup_interval_hours", 24
            )
            cleanup_interval_ms = cleanup_interval_hours * 60 * 60 * 1000
            self._data_retention_timer_id = f"data_retention_cleanup_{self.gateway_id}"

            self.add_timer(
                delay_ms=cleanup_interval_ms,
                timer_id=self._data_retention_timer_id,
                interval_ms=cleanup_interval_ms,
            )
            log.info(
                "%s Data retention timer created with ID '%s' and interval %d hours.",
                self.log_identifier,
                self._data_retention_timer_id,
                cleanup_interval_hours,
            )
        else:
            log.info(
                "%s Data retention is disabled via configuration.", self.log_identifier
            )

        log.info("%s Web UI Backend Component initialized.", self.log_identifier)

    def process_event(self, event: Event):
        if event.event_type == EventType.TIMER:
            timer_id = event.data.get("timer_id")

            if timer_id == self._sse_cleanup_timer_id:
                log.debug("%s SSE buffer cleanup timer triggered.", self.log_identifier)
                self.sse_event_buffer.cleanup_stale_buffers()
                return
            elif event.data.get("timer_id") == self.health_check_timer_id:
                log.debug("%s Agent health check timer triggered.", self.log_identifier)
                self._check_agent_health()
                return

            if timer_id == self._data_retention_timer_id:
                log.debug(
                    "%s Data retention cleanup timer triggered.", self.log_identifier
                )
                if self.data_retention_service:
                    try:
                        self.data_retention_service.cleanup_old_data()
                    except Exception as e:
                        log.error(
                            "%s Error during data retention cleanup: %s",
                            self.log_identifier,
                            e,
                            exc_info=True,
                        )
                else:
                    log.warning(
                        "%s Data retention timer fired but service is not initialized.",
                        self.log_identifier,
                    )
                return
            
            if timer_id == self._background_task_monitor_timer_id:
                log.debug("%s Background task monitor timer triggered.", self.log_identifier)
                if self.background_task_monitor:
                    loop = self.get_async_loop()
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.background_task_monitor.check_timeouts(),
                            loop
                        )
                    else:
                        log.warning(
                            "%s Async loop not available for background task monitor.",
                            self.log_identifier
                        )
                else:
                    log.warning(
                        "%s Background task monitor timer fired but service is not initialized.",
                        self.log_identifier,
                    )
                return

        super().process_event(event)

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
                "broker_queue_name": f"{self.namespace.strip('/')}/q/gdk/viz/{self.gateway_id}",
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
                    "temporary_queue": main_broker_config.get("temporary_queue", True),
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
                log.debug(
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

    def _ensure_task_logger_flow_is_running(self) -> None:
        """
        Ensures the internal SAC flow for A2A task logging is created and running.
        """
        log_id_prefix = f"{self.log_identifier}[EnsureTaskLogFlow]"
        if self._task_logger_internal_app is not None:
            log.debug("%s Task logger flow already running.", log_id_prefix)
            return

        log.info("%s Initializing internal A2A task logger flow...", log_id_prefix)
        try:
            main_app = self.get_app()
            if not main_app or not main_app.connector:
                raise RuntimeError(
                    "Main app or connector not available for internal flow creation."
                )

            main_broker_config = main_app.app_info.get("broker", {})
            if not main_broker_config:
                raise ValueError("Main app broker configuration is missing.")

            # The task logger needs to see ALL messages.
            subscriptions = [{"topic": f"{self.namespace.rstrip('/')}/a2a/>"}]

            broker_input_cfg = {
                "component_module": "broker_input",
                "component_name": f"{self.gateway_id}_task_log_broker_input",
                "broker_queue_name": f"{self.namespace.strip('/')}/q/gdk/task_log/{self.gateway_id}",
                "create_queue_on_start": True,
                "component_config": {
                    "broker_url": main_broker_config.get("broker_url"),
                    "broker_username": main_broker_config.get("broker_username"),
                    "broker_password": main_broker_config.get("broker_password"),
                    "broker_vpn": main_broker_config.get("broker_vpn"),
                    "trust_store_path": main_broker_config.get("trust_store_path"),
                    "dev_mode": main_broker_config.get("dev_mode"),
                    "broker_subscriptions": subscriptions,
                    "reconnection_strategy": main_broker_config.get(
                        "reconnection_strategy"
                    ),
                    "retry_interval": main_broker_config.get("retry_interval"),
                    "retry_count": main_broker_config.get("retry_count"),
                    "temporary_queue": main_broker_config.get("temporary_queue", True),
                },
            }

            forwarder_cfg = {
                "component_class": TaskLoggerForwarderComponent,
                "component_name": f"{self.gateway_id}_task_log_forwarder",
                "component_config": {"target_queue_ref": self._task_logger_queue},
            }

            flow_config = {
                "name": f"{self.gateway_id}_task_log_flow",
                "components": [broker_input_cfg, forwarder_cfg],
            }

            internal_app_broker_config = main_broker_config.copy()
            internal_app_broker_config["input_enabled"] = True
            internal_app_broker_config["output_enabled"] = False

            app_config_for_internal_flow = {
                "name": f"{self.gateway_id}_task_log_internal_app",
                "flows": [flow_config],
                "broker": internal_app_broker_config,
                "app_config": {},
            }

            self._task_logger_internal_app = main_app.connector.create_internal_app(
                app_name=app_config_for_internal_flow["name"],
                flows=app_config_for_internal_flow["flows"],
            )

            if (
                not self._task_logger_internal_app
                or not self._task_logger_internal_app.flows
            ):
                raise RuntimeError("Internal task logger app/flow creation failed.")

            self._task_logger_internal_app.run()
            log.info("%s Internal task logger app started.", log_id_prefix)

            flow_instance = self._task_logger_internal_app.flows[0]
            if flow_instance.component_groups and flow_instance.component_groups[0]:
                self._task_logger_broker_input = flow_instance.component_groups[0][0]
                if not isinstance(self._task_logger_broker_input, BrokerInput):
                    raise RuntimeError(
                        "Task logger flow setup error: BrokerInput not found."
                    )
                log.info(
                    "%s Obtained reference to internal task logger BrokerInput component.",
                    log_id_prefix,
                )
            else:
                raise RuntimeError(
                    "Task logger flow setup error: BrokerInput instance not accessible."
                )

        except Exception as e:
            log.exception(
                "%s Failed to ensure task logger flow is running: %s", log_id_prefix, e
            )
            if self._task_logger_internal_app:
                try:
                    self._task_logger_internal_app.cleanup()
                except Exception as cleanup_err:
                    log.error(
                        "%s Error during cleanup after task logger flow init failure: %s",
                        log_id_prefix,
                        cleanup_err,
                    )
            self._task_logger_internal_app = None
            self._task_logger_broker_input = None
            raise

    def _resolve_session_config(self) -> dict:
        """
        Resolve session service configuration with backward compatibility.

        Priority order:
        1. Component-specific session_service config (new approach)
        2. Shared default_session_service config (deprecated, with warning)
        3. Hardcoded default (SQLite for Web UI)
        """
        # Check component-specific session_service config first
        component_session_config = self.get_config("session_service")
        if component_session_config:
            log.debug("Using component-specific session_service configuration")
            return component_session_config

        # Backward compatibility: check shared config
        shared_session_config = self.get_config("default_session_service")
        if shared_session_config:
            log.warning(
                "Using session_service from shared config is deprecated. "
                "Move to component-specific configuration in app_config.session_service"
            )
            return shared_session_config

        # Default configuration for Web UI (backward compatibility)
        default_config = {"type": "memory", "default_behavior": "PERSISTENT"}
        log.info(
            "Using default memory session configuration for Web UI (backward compatibility)"
        )
        return default_config

    async def _visualization_message_processor_loop(self) -> None:
        """
        Asynchronously consumes messages from the _visualization_message_queue,
        filters them, and forwards them to relevant SSE connections.
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
                        "%s Visualization message queue is over 90%% full. Current size: %d/%d",
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
                                    a2a.topic_matches_subscription(topic, pattern)
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
                                "debug_type": event_details["debug_type"],
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
                                # Check if this is a background task
                                is_background = False
                                if task_id_for_context and self.database_url:
                                    try:
                                        from .repository.task_repository import TaskRepository
                                        db = dependencies.SessionLocal()
                                        try:
                                            repo = TaskRepository()
                                            task = repo.find_by_id(db, task_id_for_context)
                                            is_background = task and task.background_execution_enabled
                                        finally:
                                            db.close()
                                    except Exception:
                                        pass
                                
                                if is_background:
                                    log.debug(
                                        "%s SSE queue full for stream %s. Dropping visualization message for background task %s.",
                                        log_id_prefix,
                                        stream_id,
                                        task_id_for_context,
                                    )
                                else:
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

    async def _task_logger_loop(self) -> None:
        """
        Asynchronously consumes messages from the _task_logger_queue and
        passes them to the TaskLoggerService for persistence.
        """
        log_id_prefix = f"{self.log_identifier}[TaskLoggerLoop]"
        log.info("%s Starting task logger loop...", log_id_prefix)
        loop = asyncio.get_running_loop()

        while not self.stop_signal.is_set():
            msg_data = None
            try:
                msg_data = await loop.run_in_executor(
                    None,
                    self._task_logger_queue.get,
                    True,
                    1.0,
                )

                if msg_data is None:
                    log.info(
                        "%s Received shutdown signal for task logger loop.",
                        log_id_prefix,
                    )
                    break

                if self.task_logger_service:
                    self.task_logger_service.log_event(msg_data)
                else:
                    log.warning(
                        "%s Task logger service not available. Cannot log event.",
                        log_id_prefix,
                    )

                self._task_logger_queue.task_done()

            except queue.Empty:
                continue
            except asyncio.CancelledError:
                log.info("%s Task logger loop cancelled.", log_id_prefix)
                break
            except Exception as e:
                log.exception(
                    "%s Error in task logger loop: %s",
                    log_id_prefix,
                    e,
                )
                if msg_data and self._task_logger_queue:
                    self._task_logger_queue.task_done()
                await asyncio.sleep(1)

        log.info("%s Task logger loop finished.", log_id_prefix)

    async def _add_visualization_subscription(
        self, topic_str: str, stream_id: str
    ) -> bool:
        """
        Adds a Solace topic subscription to the internal BrokerInput for visualization.
        Manages global subscription reference counts.
        """
        log_id_prefix = f"{self.log_identifier}[AddVizSub:{stream_id}]"
        log.debug(
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
                        self._visualization_broker_input.add_subscription
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
                ) or not callable(self._visualization_broker_input.remove_subscription):
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
    ) -> dict[str, Any] | None:
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
            user_info = {}
            if hasattr(request.state, "user") and request.state.user:
                user_info = request.state.user
                username = user_info.get("username")
                if username:
                    log.debug(
                        "%s Extracted user '%s' from request.state.",
                        log_id_prefix,
                        username,
                    )
                    return {
                        "id": username,
                        "name": username,
                        "email": username,
                        "user_info": user_info,
                    }

            log.debug(
                "%s No authenticated user in request.state, falling back to SessionManager.",
                log_id_prefix,
            )
            user_id = self.session_manager.get_a2a_client_id(request)
            log.debug(
                "%s Extracted user_id '%s' via SessionManager.", log_id_prefix, user_id
            )
            return {"id": user_id, "name": user_id, "user_info": user_info}

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
            from ...gateway.http_sse.main import app as fastapi_app_instance
            from ...gateway.http_sse.main import setup_dependencies

            self.fastapi_app = fastapi_app_instance

            setup_dependencies(self, self.database_url, self.platform_database_url)

            # Instantiate services that depend on the database session factory.
            # This must be done *after* setup_dependencies has run.
            session_factory = dependencies.SessionLocal if self.database_url else None
            
            # Initialize SSE manager with session factory for background task detection
            self.sse_manager = SSEManager(
                max_queue_size=self.sse_max_queue_size,
                event_buffer=self.sse_event_buffer,
                session_factory=session_factory
            )
            log.debug(
                "%s SSE manager initialized with database session factory.",
                self.log_identifier,
            )
            task_logging_config = self.get_config("task_logging", {})
            self.task_logger_service = TaskLoggerService(
                session_factory=session_factory, config=task_logging_config
            )
            log.debug(
                "%s Services dependent on database session factory have been initialized.",
                self.log_identifier,
            )
            
            # Initialize background task monitor if task logging is enabled
            if self.database_url and task_logging_config.get("enabled", False):
                from .services.background_task_monitor import BackgroundTaskMonitor
                from .services.task_service import TaskService
                
                # Create task service for cancellation operations
                task_service = TaskService(
                    core_a2a_service=self.core_a2a_service,
                    publish_func=self.publish_a2a,
                    namespace=self.namespace,
                    gateway_id=self.gateway_id,
                    sse_manager=self.sse_manager,
                    task_context_map=self.task_context_manager._contexts,
                    task_context_lock=self.task_context_manager._lock,
                    app_name=self.name,
                )
                
                # Get timeout configuration
                background_config = self.get_config("background_tasks", {})
                default_timeout_ms = background_config.get("default_timeout_ms", 3600000)  # 1 hour
                
                self.background_task_monitor = BackgroundTaskMonitor(
                    session_factory=session_factory,
                    task_service=task_service,
                    default_timeout_ms=default_timeout_ms,
                )
                
                # Create timer for periodic timeout checks
                monitor_interval_ms = background_config.get("monitor_interval_ms", 300000)  # 5 minutes
                self._background_task_monitor_timer_id = f"background_task_monitor_{self.gateway_id}"
                
                self.add_timer(
                    delay_ms=monitor_interval_ms,
                    timer_id=self._background_task_monitor_timer_id,
                    interval_ms=monitor_interval_ms,
                )
                
                log.info(
                    "%s Background task monitor initialized with %dms check interval and %dms default timeout",
                    self.log_identifier,
                    monitor_interval_ms,
                    default_timeout_ms
                )
            else:
                log.info(
                    "%s Background task monitor not initialized (task logging disabled or no database)",
                    self.log_identifier
                )

            port = (
                self.fastapi_https_port
                if self.ssl_keyfile and self.ssl_certfile
                else self.fastapi_port
            )

            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.fastapi_host,
                port=port,
                log_level="warning",
                lifespan="on",
                ssl_keyfile=self.ssl_keyfile,
                ssl_certfile=self.ssl_certfile,
                ssl_keyfile_password=self.ssl_keyfile_password,
                log_config=None
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
                    log.debug(
                        "%s [_start_listener] Captured FastAPI event loop via startup event: %s",
                        self.log_identifier,
                        self.fastapi_event_loop,
                    )

                    if self.fastapi_event_loop:
                        log.debug(
                            "%s Ensuring visualization flow is running...",
                            self.log_identifier,
                        )
                        self._ensure_visualization_flow_is_running()

                        if (
                            self._visualization_processor_task is None
                            or self._visualization_processor_task.done()
                        ):
                            log.debug(
                                "%s Starting visualization message processor task.",
                                self.log_identifier,
                            )
                            self._visualization_processor_task = (
                                self.fastapi_event_loop.create_task(
                                    self._visualization_message_processor_loop()
                                )
                            )
                        else:
                            log.debug(
                                "%s Visualization message processor task already running.",
                                self.log_identifier,
                            )

                        task_logging_config = self.get_config("task_logging", {})
                        if task_logging_config.get("enabled", False):
                            log.info(
                                "%s Task logging is enabled. Ensuring flow is running...",
                                self.log_identifier,
                            )
                            self._ensure_task_logger_flow_is_running()

                            if (
                                self._task_logger_processor_task is None
                                or self._task_logger_processor_task.done()
                            ):
                                log.info(
                                    "%s Starting task logger processor task.",
                                    self.log_identifier,
                                )
                                self._task_logger_processor_task = (
                                    self.fastapi_event_loop.create_task(
                                        self._task_logger_loop()
                                    )
                                )
                            else:
                                log.info(
                                    "%s Task logger processor task already running.",
                                    self.log_identifier,
                                )
                        else:
                            log.info(
                                "%s Task logging is disabled.", self.log_identifier
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

                try:
                    from solace_agent_mesh_enterprise.init_enterprise import (
                        start_enterprise_background_tasks,
                    )

                    log.info(
                        "%s Starting enterprise background tasks...",
                        self.log_identifier,
                    )
                    await start_enterprise_background_tasks(self)
                    log.info(
                        "%s Enterprise background tasks started successfully",
                        self.log_identifier,
                    )
                except ImportError:
                    log.debug(
                        "%s Enterprise package not available - skipping background tasks",
                        self.log_identifier,
                    )
                except RuntimeError as enterprise_err:
                    log.warning(
                        "%s Enterprise background tasks disabled: %s - Community features will continue normally",
                        self.log_identifier,
                        enterprise_err,
                    )
                except Exception as enterprise_err:
                    log.error(
                        "%s Failed to start enterprise background tasks: %s - Community features will continue normally",
                        self.log_identifier,
                        enterprise_err,
                        exc_info=True,
                    )

            @self.fastapi_app.on_event("shutdown")
            async def shutdown_event():
                log.info(
                    "%s [_start_listener] FastAPI shutdown event triggered.",
                    self.log_identifier,
                )

                try:
                    from solace_agent_mesh_enterprise.init_enterprise import (
                        stop_enterprise_background_tasks,
                    )

                    log.info(
                        "%s Stopping enterprise background tasks...",
                        self.log_identifier,
                    )
                    await stop_enterprise_background_tasks()
                    log.info(
                        "%s Enterprise background tasks stopped", self.log_identifier
                    )
                except ImportError:
                    log.debug(
                        "%s Enterprise package not available - no background tasks to stop",
                        self.log_identifier,
                    )
                except Exception as enterprise_err:
                    log.error(
                        "%s Failed to stop enterprise background tasks: %s",
                        self.log_identifier,
                        enterprise_err,
                        exc_info=True,
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
            log.error(
                "%s [_start_listener] Failed to start FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
            raise

    def publish_a2a(
        self, topic: str, payload: dict, user_properties: dict | None = None
    ):
        """
        Publishes an A2A message using the SAC App's send_message method.
        This method can be called from FastAPI handlers (via dependency injection).
        It's thread-safe as it uses the SAC App instance.
        """
        log.debug(f"[publish_a2a] Starting to publish message to topic: {topic}")
        log.debug(
            f"[publish_a2a] Payload type: {type(payload)}, size: {len(str(payload))} chars"
        )
        log.debug(f"[publish_a2a] User properties: {user_properties}")

        try:
            super().publish_a2a_message(payload, topic, user_properties)
            log.debug(
                f"[publish_a2a] Successfully called super().publish_a2a_message for topic: {topic}"
            )
        except Exception as e:
            log.error(f"[publish_a2a] Exception in publish_a2a: {e}", exc_info=True)
            raise

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

        # Cancel timers
        self.cancel_timer(self._sse_cleanup_timer_id)
        if self._data_retention_timer_id:
            self.cancel_timer(self._data_retention_timer_id)
            log.info("%s Cancelled data retention cleanup timer.", self.log_identifier)
        
        if self._background_task_monitor_timer_id:
            self.cancel_timer(self._background_task_monitor_timer_id)
            log.info("%s Cancelled background task monitor timer.", self.log_identifier)

        # Clean up data retention service
        if self.data_retention_service:
            self.data_retention_service = None
            log.info("%s Data retention service cleaned up.", self.log_identifier)
        
        # Clean up background task monitor
        if self.background_task_monitor:
            self.background_task_monitor = None
            log.info("%s Background task monitor cleaned up.", self.log_identifier)

        self.cancel_timer(self.health_check_timer_id)
        log.info("%s Cleaning up visualization resources...", self.log_identifier)
        if self._visualization_message_queue:
            self._visualization_message_queue.put(None)
        if self._task_logger_queue:
            self._task_logger_queue.put(None)

        if (
            self._visualization_processor_task
            and not self._visualization_processor_task.done()
        ):
            log.info(
                "%s Cancelling visualization processor task...", self.log_identifier
            )
            self._visualization_processor_task.cancel()

        if (
            self._task_logger_processor_task
            and not self._task_logger_processor_task.done()
        ):
            log.info("%s Cancelling task logger processor task...", self.log_identifier)
            self._task_logger_processor_task.cancel()

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

        if self._task_logger_internal_app:
            log.info("%s Cleaning up internal task logger app...", self.log_identifier)
            try:
                self._task_logger_internal_app.cleanup()
            except Exception as e:
                log.error(
                    "%s Error cleaning up internal task logger app: %s",
                    self.log_identifier,
                    e,
                )

        self._active_visualization_streams.clear()
        self._global_visualization_subscriptions.clear()
        self._cleanup_visualization_locks()
        log.info("%s Visualization resources cleaned up.", self.log_identifier)

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

    def _infer_visualization_event_details(
        self, topic: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Infers details for the visualization SSE payload from the Solace topic and A2A message.
        This version is updated to parse the official A2A SDK message formats.
        """
        details = {
            "direction": "unknown",
            "source_entity": "unknown",
            "target_entity": "unknown",
            "debug_type": "unknown",
            "message_id": payload.get("id"),
            "task_id": None,
            "payload_summary": {
                "method": payload.get("method", "N/A"),
                "params_preview": None,
            },
        }

        # --- Phase 1: Parse the payload to extract core info ---
        try:
            # Handle SAM Events (system events)
            event_type = payload.get("event_type")
            if event_type:
                details["direction"] = "system_event"
                details["debug_type"] = "sam_event"
                details["payload_summary"]["method"] = event_type
                details["source_entity"] = payload.get("source_component", "unknown")
                details["target_entity"] = "system"
                return details

            # Try to parse as a JSON-RPC response first
            if "result" in payload or "error" in payload:
                rpc_response = JSONRPCResponse.model_validate(payload)
                result = a2a.get_response_result(rpc_response)
                error = a2a.get_response_error(rpc_response)
                details["message_id"] = a2a.get_response_id(rpc_response)

                if result:
                    kind = getattr(result, "kind", None)
                    details["direction"] = kind or "response"
                    details["task_id"] = getattr(result, "task_id", None) or getattr(
                        result, "id", None
                    )

                    if isinstance(result, TaskStatusUpdateEvent):
                        details["source_entity"] = (
                            result.metadata.get("agent_name")
                            if result.metadata
                            else None
                        )
                        message = a2a.get_message_from_status_update(result)
                        if message:
                            if not details["source_entity"]:
                                details["source_entity"] = (
                                    message.metadata.get("agent_name")
                                    if message.metadata
                                    else None
                                )
                            data_parts = a2a.get_data_parts_from_message(message)
                            if data_parts:
                                details["debug_type"] = data_parts[0].data.get(
                                    "type", "unknown"
                                )
                            elif a2a.get_text_from_message(message):
                                details["debug_type"] = "streaming_text"
                    elif isinstance(result, Task):
                        details["source_entity"] = (
                            result.metadata.get("agent_name")
                            if result.metadata
                            else None
                        )
                    elif isinstance(result, TaskArtifactUpdateEvent):
                        artifact = a2a.get_artifact_from_artifact_update(result)
                        if artifact:
                            details["source_entity"] = (
                                artifact.metadata.get("agent_name")
                                if artifact.metadata
                                else None
                            )
                elif error:
                    details["direction"] = "error_response"
                    details["task_id"] = (
                        error.data.get("taskId")
                        if isinstance(error.data, dict)
                        else None
                    )
                    details["debug_type"] = "error"

            # Try to parse as a JSON-RPC request
            elif "method" in payload:
                rpc_request = A2ARequest.model_validate(payload)
                method = a2a.get_request_method(rpc_request)
                details["direction"] = "request"
                details["payload_summary"]["method"] = method
                details["message_id"] = a2a.get_request_id(rpc_request)

                if method in ["message/send", "message/stream"]:
                    details["debug_type"] = method
                    message = a2a.get_message_from_send_request(rpc_request)
                    details["task_id"] = a2a.get_request_id(rpc_request)
                    if message:
                        details["target_entity"] = (
                            message.metadata.get("agent_name")
                            if message.metadata
                            else None
                        )
                elif method == "tasks/cancel":
                    details["task_id"] = a2a.get_task_id_from_cancel_request(
                        rpc_request
                    )

            # Handle Discovery messages (which are not JSON-RPC)
            elif "/a2a/v1/discovery/" in topic:
                agent_card = AgentCard.model_validate(payload)
                details["direction"] = "discovery"
                details["source_entity"] = agent_card.name
                details["target_entity"] = "broadcast"
                details["message_id"] = None  # Discovery has no ID

        except Exception as e:
            log.warning(
                "[%s] Failed to parse A2A payload for visualization details: %s",
                self.log_identifier,
                e,
            )

        # --- Phase 2: Refine details using topic information as a fallback ---
        if details["direction"] == "unknown":
            if "request" in topic:
                details["direction"] = "request"
            elif "response" in topic:
                details["direction"] = "response"
            elif "status" in topic:
                details["direction"] = "status_update"
                # TEMP - add debug_type based on the type in the data
                details["debug_type"] = "unknown"

        # --- Phase 3: Create a payload summary ---
        try:
            summary_source = (
                payload.get("result")
                or payload.get("params")
                or payload.get("error")
                or payload
            )
            summary_str = json.dumps(summary_source)
            details["payload_summary"]["params_preview"] = (
                (summary_str[:100] + "...") if len(summary_str) > 100 else summary_str
            )
        except Exception:
            details["payload_summary"][
                "params_preview"
            ] = "[Could not serialize payload]"

        return details

    def _extract_involved_agents_for_viz(
        self, topic: str, payload_dict: dict[str, Any]
    ) -> set[str]:
        """
        Extracts agent names involved in a message from its topic and payload.
        """
        agents: set[str] = set()
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

    def get_agent_registry(self) -> AgentRegistry:
        return self.agent_registry

    def _check_agent_health(self):
        """
        Checks the health of peer agents and de-registers unresponsive ones.
        This is called periodically by the health check timer.
        Uses TTL-based expiration to determine if an agent is unresponsive.
        """

        log.debug("%s Performing agent health check...", self.log_identifier)

        # Get TTL from configuration or use default from constants
        from ...common.constants import (
            HEALTH_CHECK_INTERVAL_SECONDS,
            HEALTH_CHECK_TTL_SECONDS,
        )

        ttl_seconds = self.get_config(
            "agent_health_check_ttl_seconds", HEALTH_CHECK_TTL_SECONDS
        )
        health_check_interval = self.get_config(
            "agent_health_check_interval_seconds", HEALTH_CHECK_INTERVAL_SECONDS
        )

        log.debug(
            "%s Health check configuration: interval=%d seconds, TTL=%d seconds",
            self.log_identifier,
            health_check_interval,
            ttl_seconds,
        )

        # Validate configuration values
        if (
            ttl_seconds <= 0
            or health_check_interval <= 0
            or ttl_seconds < health_check_interval
        ):
            log.error(
                "%s agent_health_check_ttl_seconds (%d) and agent_health_check_interval_seconds (%d) must be positive and TTL must be greater than interval.",
                self.log_identifier,
                ttl_seconds,
                health_check_interval,
            )
            raise ValueError(
                f"Invalid health check configuration. agent_health_check_ttl_seconds ({ttl_seconds}) and agent_health_check_interval_seconds ({health_check_interval}) must be positive and TTL must be greater than interval."
            )

        # Get all agent names from the registry
        agent_names = self.agent_registry.get_agent_names()
        total_agents = len(agent_names)
        agents_to_deregister = []

        log.debug(
            "%s Checking health of %d peer agents", self.log_identifier, total_agents
        )

        for agent_name in agent_names:
            # Check if the agent's TTL has expired
            is_expired, time_since_last_seen = self.agent_registry.check_ttl_expired(
                agent_name, ttl_seconds
            )

            if is_expired:
                log.warning(
                    "%s Agent '%s' TTL has expired. De-registering. Time since last seen: %d seconds (TTL: %d seconds)",
                    self.log_identifier,
                    agent_name,
                    time_since_last_seen,
                    ttl_seconds,
                )
                agents_to_deregister.append(agent_name)

        # De-register unresponsive agents
        for agent_name in agents_to_deregister:
            self._deregister_agent(agent_name)

        log.debug(
            "%s Agent health check completed. Total agents: %d, De-registered: %d",
            self.log_identifier,
            total_agents,
            len(agents_to_deregister),
        )

    def _deregister_agent(self, agent_name: str):
        """
        De-registers an agent from the registry and publishes a de-registration event.
        """
        # Remove from registry
        self.agent_registry.remove_agent(agent_name)

    def get_sse_manager(self) -> SSEManager:
        return self.sse_manager

    def get_session_manager(self) -> SessionManager:
        return self.session_manager

    def get_task_logger_service(self) -> TaskLoggerService | None:
        """Returns the shared TaskLoggerService instance."""
        return self.task_logger_service

    def get_namespace(self) -> str:
        return self.namespace

    def get_gateway_id(self) -> str:
        """Returns the unique identifier for this gateway instance."""
        return self.gateway_id

    def get_cors_origins(self) -> list[str]:
        return self.cors_allowed_origins

    def get_shared_artifact_service(self) -> BaseArtifactService | None:
        return self.shared_artifact_service

    def get_embed_config(self) -> dict[str, Any]:
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
        self, external_event_data: dict[str, Any]
    ) -> tuple[str, list[ContentPart], dict[str, Any]]:
        """
        Translates raw HTTP request data (from FastAPI form) into A2A task parameters.

        Args:
            external_event_data: A dictionary containing data from the HTTP request,
                                 expected to have keys like 'agent_name', 'message',
                                 'files' (List[UploadFile]), 'client_id', 'a2a_session_id'.

        Returns:
            A tuple containing:
            - target_agent_name (str): The name of the A2A agent to target.
            - a2a_parts (List[ContentPart]): A list of unwrapped A2A Part objects.
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
        files: list[UploadFile] | None = external_event_data.get("files")
        client_id: str = external_event_data.get("client_id")
        a2a_session_id: str = external_event_data.get("a2a_session_id")
        if not target_agent_name:
            raise ValueError("Target agent name is missing in external_event_data.")
        if not client_id or not a2a_session_id:
            raise ValueError(
                "Client ID or A2A Session ID is missing in external_event_data."
            )

        a2a_parts: list[ContentPart] = []

        if files:
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

                    # The BaseGatewayComponent will handle normalization based on policy.
                    # Here, we just create the FilePart with inline bytes.
                    file_part = a2a.create_file_part_from_bytes(
                        content_bytes=content_bytes,
                        name=upload_file.filename,
                        mime_type=upload_file.content_type,
                    )
                    a2a_parts.append(file_part)
                    log.info(
                        "%s Created inline FilePart for uploaded file: %s (%d bytes)",
                        log_id_prefix,
                        upload_file.filename,
                        len(content_bytes),
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

        if user_message:
            a2a_parts.append(a2a.create_text_part(text=user_message))

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
        external_request_context: dict[str, Any],
        event_data: TaskStatusUpdateEvent | TaskArtifactUpdateEvent,
        is_final_chunk_of_update: bool,
    ) -> None:
        """
        Sends an intermediate update (TaskStatusUpdateEvent or TaskArtifactUpdateEvent)
        to the external platform (Web UI via SSE) and stores agent messages in the database.
        """
        log_id_prefix = f"{self.log_identifier}[SendUpdate]"
        sse_task_id = external_request_context.get("a2a_task_id_for_event")
        a2a_task_id = event_data.task_id

        log.debug(
            "%s _send_update_to_external called with event_type: %s",
            log_id_prefix,
            type(event_data).__name__,
        )

        if not sse_task_id:
            log.error(
                "%s Cannot send update: 'a2a_task_id_for_event' missing from external_request_context.",
                log_id_prefix,
            )
            return

        try:
            from solace_agent_mesh_enterprise.auth.input_required import (
                handle_input_required_request,
            )

            event_data = handle_input_required_request(event_data, sse_task_id, self)
        except ImportError:
            pass

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

        sse_payload_model = a2a.create_success_response(
            result=event_data, request_id=a2a_task_id
        )
        sse_payload = sse_payload_model.model_dump(by_alias=True, exclude_none=True)

        try:
            await self.sse_manager.send_event(
                task_id=sse_task_id, event_data=sse_payload, event_type=sse_event_type
            )
            log.debug(
                "%s Successfully sent %s via SSE for A2A Task ID %s.",
                log_id_prefix,
                sse_event_type,
                a2a_task_id,
            )

            # Note: Agent message storage is handled in _send_final_response_to_external
            # to avoid duplicate storage of intermediate status updates

        except Exception as e:
            log.exception(
                "%s Failed to send %s via SSE for A2A Task ID %s: %s",
                log_id_prefix,
                sse_event_type,
                a2a_task_id,
                e,
            )

    async def _send_final_response_to_external(
        self, external_request_context: dict[str, Any], task_data: Task
    ) -> None:
        """
        Sends the final A2A Task result to the external platform (Web UI via SSE).
        """
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        sse_task_id = external_request_context.get("a2a_task_id_for_event")
        a2a_task_id = task_data.id

        log.debug("%s _send_final_response_to_external called", log_id_prefix)

        if not sse_task_id:
            log.error(
                "%s Cannot send final response: 'a2a_task_id_for_event' missing from external_request_context.",
                log_id_prefix,
            )
            return

        log.info(
            "%s Sending final response for A2A Task ID %s to SSE Task ID %s.",
            log_id_prefix,
            a2a_task_id,
            sse_task_id,
        )

        sse_payload_model = a2a.create_success_response(
            result=task_data, request_id=a2a_task_id
        )
        sse_payload = sse_payload_model.model_dump(by_alias=True, exclude_none=True)

        try:
            await self.sse_manager.send_event(
                task_id=sse_task_id, event_data=sse_payload, event_type="final_response"
            )
            log.debug(
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
        self, external_request_context: dict[str, Any], error_data: JSONRPCError
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

        sse_payload_model = a2a.create_error_response(
            error=error_data,
            request_id=external_request_context.get("original_rpc_id", sse_task_id),
        )
        sse_payload = sse_payload_model.model_dump(by_alias=True, exclude_none=True)

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
