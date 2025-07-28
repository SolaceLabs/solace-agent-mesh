"""
Abstract base class for proxy components.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

import httpx

from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.components.component_base import ComponentBase

from ....common.a2a_protocol import get_agent_request_topic, get_discovery_topic
from ....common.agent_registry import AgentRegistry
from a2a.types import (
    A2ARequest,
    AgentCard,
    CancelTaskRequest,
    InternalError,
    InvalidRequestError,
    JSONParseError,
    JSONRPCResponse,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
from pydantic import ValidationError
from ...adk.services import initialize_artifact_service
from ..a2a.translation import (
    translate_modern_to_sam_response,
    translate_sam_to_modern_request,
)

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService

    from .proxy_task_context import ProxyTaskContext

info = {
    "class_name": "BaseProxyComponent",
    "description": (
        "Abstract base class for proxy components. Handles Solace interaction, "
        "discovery, and task lifecycle management."
    ),
    "config_parameters": [],
    "input_schema": {},
    "output_schema": {},
}


class BaseProxyComponent(ComponentBase, ABC):
    """
    Abstract base class for proxy components.

    Initializes shared services and manages the core lifecycle for proxying
    requests between the Solace event mesh and a downstream agent protocol.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(info, **kwargs)
        self.namespace = self.get_config("namespace")
        self.proxied_agents_config = self.get_config("proxied_agents", [])
        self.artifact_service_config = self.get_config(
            "artifact_service", {"type": "memory"}
        )
        self.discovery_interval_sec = self.get_config("discovery_interval_seconds", 60)

        self.agent_registry = AgentRegistry()
        self.artifact_service: Optional[BaseArtifactService] = None
        self.active_tasks: Dict[str, ProxyTaskContext] = {}
        self._httpx_client = httpx.AsyncClient()
        self.active_tasks_lock = threading.Lock()

        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._async_init_future: Optional[concurrent.futures.Future] = None
        self._discovery_timer_id = f"proxy_discovery_{self.name}"

        try:
            # Initialize synchronous services first
            self.artifact_service = initialize_artifact_service(self)
            log.info("%s Artifact service initialized.", self.log_identifier)

            # Start the dedicated asyncio event loop
            self._async_loop = asyncio.new_event_loop()
            self._async_init_future = concurrent.futures.Future()
            self._async_thread = threading.Thread(
                target=self._start_async_loop, daemon=True
            )
            self._async_thread.start()

            # Schedule async initialization and wait for it to complete
            init_coro_future = asyncio.run_coroutine_threadsafe(
                self._perform_async_init(), self._async_loop
            )
            init_coro_future.result(timeout=60)
            self._async_init_future.result(timeout=1)
            log.info("%s Async initialization completed.", self.log_identifier)

            # Perform initial blocking discovery
            log.info("%s Performing initial agent discovery...", self.log_identifier)
            initial_discovery_future = asyncio.run_coroutine_threadsafe(
                self._discover_agents(), self._async_loop
            )
            initial_discovery_future.result(timeout=60)
            log.info("%s Initial agent discovery complete.", self.log_identifier)

            # Schedule the recurring discovery timer
            if self.discovery_interval_sec > 0:
                self.add_timer(
                    delay_ms=1000,  # Initial delay
                    timer_id=self._discovery_timer_id,
                    interval_ms=self.discovery_interval_sec * 1000,
                )
                log.info(
                    "%s Scheduled agent discovery every %d seconds.",
                    self.log_identifier,
                    self.discovery_interval_sec,
                )

        except Exception as e:
            log.exception("%s Initialization failed: %s", self.log_identifier, e)
            self.cleanup()
            raise

    def invoke(self, message: SolaceMessage, data: dict) -> dict:
        """Placeholder invoke method. Primary logic resides in process_event."""
        log.warning(
            "%s 'invoke' method called, but primary logic resides in 'process_event'. This should not happen in normal operation.",
            self.log_identifier,
        )
        return None

    def process_event(self, event: Event):
        """Processes incoming events by routing them to the async loop."""
        if not self._async_loop or not self._async_loop.is_running():
            log.error(
                "%s Async loop not available. Cannot process event: %s",
                self.log_identifier,
                event.event_type,
            )
            if event.event_type == EventType.MESSAGE:
                event.data.call_negative_acknowledgements()
            return

        future = asyncio.run_coroutine_threadsafe(
            self._process_event_async(event), self._async_loop
        )
        future.add_done_callback(self._handle_scheduled_task_completion)

    async def _process_event_async(self, event: Event):
        """Asynchronous event processing logic."""
        if event.event_type == EventType.MESSAGE:
            await self._handle_a2a_request(event.data)
        elif event.event_type == EventType.TIMER:
            if event.data.get("timer_id") == self._discovery_timer_id:
                await self._discover_agents()
        else:
            log.debug(
                "%s Ignoring unhandled event type: %s",
                self.log_identifier,
                event.event_type,
            )

    async def _handle_a2a_request(self, message: SolaceMessage):
        """Handles an incoming A2A request message from Solace."""
        jsonrpc_request_id = None
        logical_task_id = None
        try:
            payload = message.get_payload()
            if not isinstance(payload, dict):
                raise ValueError("Payload is not a dictionary.")

            jsonrpc_request_id = payload.get("id")

            # Get agent name from topic
            topic = message.get_topic()
            if not topic:
                raise ValueError("Message has no topic.")
            target_agent_name = topic.split("/")[-1]

            # 4.2.2: Call inbound translator
            a2a_request = translate_sam_to_modern_request(payload)

            # Get logical task ID based on the modern request type
            if isinstance(
                a2a_request, (SendMessageRequest, SendStreamingMessageRequest)
            ):
                logical_task_id = a2a_request.params.message.task_id
            else:
                logical_task_id = a2a_request.params.id

            # 4.2.3: Pass modern request to forwarder
            if isinstance(
                a2a_request, (SendMessageRequest, SendStreamingMessageRequest)
            ):
                from .proxy_task_context import ProxyTaskContext

                a2a_context = {
                    "jsonrpc_request_id": jsonrpc_request_id,
                    "logical_task_id": logical_task_id,
                    "statusTopic": message.get_user_properties().get("a2aStatusTopic"),
                    "replyToTopic": message.get_user_properties().get("replyTo"),
                }
                task_context = ProxyTaskContext(
                    task_id=logical_task_id, a2a_context=a2a_context
                )
                with self.active_tasks_lock:
                    self.active_tasks[logical_task_id] = task_context

                log.info(
                    "%s Forwarding request for task %s to agent %s.",
                    self.log_identifier,
                    logical_task_id,
                    target_agent_name,
                )
                await self._forward_request(
                    task_context, a2a_request, target_agent_name
                )

            elif isinstance(a2a_request, CancelTaskRequest):
                with self.active_tasks_lock:
                    task_context = self.active_tasks.get(logical_task_id)
                if task_context:
                    task_context.cancellation_event.set()
                    log.info(
                        "%s Cancellation signal set for task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )
            else:
                log.warning(
                    "%s Received unhandled A2A request type: %s",
                    self.log_identifier,
                    type(a2a_request).__name__,
                )

            message.call_acknowledgements()

        # 4.2.4: Update except block
        except (ValueError, TypeError, ValidationError) as e:
            log.error(
                "%s Failed to parse, translate, or validate A2A request: %s",
                self.log_identifier,
                e,
            )
            error_data = {"taskId": logical_task_id} if logical_task_id else None
            error = InvalidRequestError(message=str(e), data=error_data)
            await self._publish_error_response(jsonrpc_request_id, error, message)
            message.call_negative_acknowledgements()
        except Exception as e:
            log.exception(
                "%s Unexpected error handling A2A request: %s",
                self.log_identifier,
                e,
            )
            error = InternalError(
                message=f"Unexpected proxy error: {e}",
                data={"taskId": logical_task_id},
            )
            await self._publish_error_response(jsonrpc_request_id, error, message)
            message.call_negative_acknowledgements()

    async def _discover_agents(self):
        """Fetches agent cards from all configured downstream agents and publishes them."""
        log.info("%s Starting agent discovery cycle...", self.log_identifier)
        for agent_config in self.proxied_agents_config:
            try:
                agent_card = await self._fetch_agent_card(agent_config)
                if not agent_card:
                    continue

                agent_alias = agent_config["name"]

                # Create a copy of the card that will represent the agent on the mesh.
                # Overwrite its name with the configured alias.
                card_for_proxy = agent_card.model_copy(deep=True)
                card_for_proxy.name = agent_alias

                # Register the agent using the alias, so it can be found by internal requests.
                self.agent_registry.add_or_update_agent(card_for_proxy)
                log.info(
                    "%s Registered agent card for alias '%s' (actual name: '%s').",
                    self.log_identifier,
                    agent_alias,
                    agent_card.name,
                )

                # The card to be published should also use the alias and have its URL rewritten.
                card_to_publish = card_for_proxy.model_copy(deep=True)
                card_to_publish.url = (
                    f"solace:{get_agent_request_topic(self.namespace, agent_alias)}"
                )

                discovery_topic = get_discovery_topic(self.namespace)
                self._publish_a2a_message(
                    card_to_publish.model_dump(exclude_none=True), discovery_topic
                )
                log.info(
                    "%s Published card for agent '%s' to discovery topic.",
                    self.log_identifier,
                    agent_alias,
                )
            except Exception as e:
                log.error(
                    "%s Failed to discover or publish card for agent '%s': %s",
                    self.log_identifier,
                    agent_config.get("name", "unknown"),
                    e,
                )

    async def _publish_status_update(
        self, event: TaskStatusUpdateEvent, a2a_context: Dict
    ):
        """Publishes a TaskStatusUpdateEvent to the appropriate Solace topic."""
        target_topic = a2a_context.get("statusTopic")
        if not target_topic:
            log.warning(
                "%s No statusTopic in context for task %s. Cannot publish status update.",
                self.log_identifier,
                event.task_id,
            )
            return

        # 4.3.2: Call outbound translator
        legacy_event_dict = translate_modern_to_sam_response(event)

        # 4.3.3: Use translated dict as result
        response = JSONRPCResponse(
            id=a2a_context.get("jsonrpc_request_id"), result=legacy_event_dict
        )
        self._publish_a2a_message(response.model_dump(exclude_none=True), target_topic)

    async def _publish_final_response(self, task: Task, a2a_context: Dict):
        """Publishes the final Task object to the appropriate Solace topic."""
        target_topic = a2a_context.get("replyToTopic")
        if not target_topic:
            log.warning(
                "%s No replyToTopic in context for task %s. Cannot publish final response.",
                self.log_identifier,
                task.id,
            )
            return

        # 4.4.2: Call outbound translator
        legacy_task_dict = translate_modern_to_sam_response(task)

        # 4.4.3: Use translated dict as result
        response = JSONRPCResponse(
            id=a2a_context.get("jsonrpc_request_id"), result=legacy_task_dict
        )
        self._publish_a2a_message(response.model_dump(exclude_none=True), target_topic)

    async def _publish_artifact_update(
        self, event: TaskArtifactUpdateEvent, a2a_context: Dict
    ):
        """Publishes a TaskArtifactUpdateEvent to the appropriate Solace topic."""
        target_topic = a2a_context.get("statusTopic")
        if not target_topic:
            log.warning(
                "%s No statusTopic in context for task %s. Cannot publish artifact update.",
                self.log_identifier,
                event.task_id,
            )
            return

        legacy_event_dict = translate_modern_to_sam_response(event)

        response = JSONRPCResponse(
            id=a2a_context.get("jsonrpc_request_id"), result=legacy_event_dict
        )
        self._publish_a2a_message(response.model_dump(exclude_none=True), target_topic)

    async def _publish_error_response(
        self,
        request_id: str,
        error: InternalError | InvalidRequestError,
        message: SolaceMessage,
    ):
        """Publishes a JSON-RPC error response."""
        target_topic = message.get_user_properties().get("replyTo")
        if not target_topic:
            log.warning(
                "%s No replyToTopic in message. Cannot publish error response.",
                self.log_identifier,
            )
            return
        response = JSONRPCResponse(id=request_id, error=error)
        self._publish_a2a_message(response.model_dump(exclude_none=True), target_topic)

    def _publish_a2a_message(
        self, payload: Dict, topic: str, user_properties: Optional[Dict] = None
    ):
        """Helper to publish A2A messages via the SAC App."""
        app = self.get_app()
        if app:
            app.send_message(
                payload=payload, topic=topic, user_properties=user_properties
            )
        else:
            log.error(
                "%s Cannot publish message: Not running within a SAC App context.",
                self.log_identifier,
            )

    def _start_async_loop(self):
        """Target method for the dedicated async thread."""
        log.info("%s Dedicated async thread started.", self.log_identifier)
        try:
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()
        except Exception as e:
            log.exception(
                "%s Exception in dedicated async thread loop: %s",
                self.log_identifier,
                e,
            )
            if self._async_init_future and not self._async_init_future.done():
                self._async_init_future.set_exception(e)
        finally:
            log.info("%s Dedicated async thread loop finishing.", self.log_identifier)
            if self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._async_loop.stop)

    async def _perform_async_init(self):
        """Coroutine to perform async initialization."""
        try:
            log.info("%s Performing async initialization...", self.log_identifier)
            # Placeholder for any future async init steps
            if self._async_init_future and not self._async_init_future.done():
                self._async_loop.call_soon_threadsafe(
                    self._async_init_future.set_result, True
                )
        except Exception as e:
            if self._async_init_future and not self._async_init_future.done():
                self._async_loop.call_soon_threadsafe(
                    self._async_init_future.set_exception, e
                )

    def _handle_scheduled_task_completion(self, future: concurrent.futures.Future):
        """Callback to log exceptions from tasks scheduled on the async loop."""
        if future.done() and future.exception():
            log.error(
                "%s Coroutine scheduled on async loop failed: %s",
                self.log_identifier,
                future.exception(),
                exc_info=future.exception(),
            )

    def cleanup(self):
        """Cleans up resources on component shutdown."""
        log.info("%s Cleaning up proxy component.", self.log_identifier)
        self.cancel_timer(self._discovery_timer_id)

        with self.active_tasks_lock:
            for task_context in self.active_tasks.values():
                task_context.cancellation_event.set()

        if self._async_loop and self._async_loop.is_running():
            # Schedule the client cleanup and wait for it
            cleanup_future = asyncio.run_coroutine_threadsafe(
                self._httpx_client.aclose(), self._async_loop
            )
            try:
                cleanup_future.result(timeout=5)
            except Exception as e:
                log.error("%s Error closing httpx client: %s", self.log_identifier, e)

            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread and self._async_thread.is_alive():
            self._async_thread.join(timeout=5)
            if self._async_thread.is_alive():
                log.warning(
                    "%s Async thread did not exit cleanly.", self.log_identifier
                )

        super().cleanup()
        log.info("%s Component cleanup finished.", self.log_identifier)

    @abstractmethod
    async def _fetch_agent_card(self, agent_config: dict) -> Optional[AgentCard]:
        """
        Fetches the AgentCard from a single downstream agent.
        To be implemented by concrete proxy classes.
        """
        raise NotImplementedError

    @abstractmethod
    async def _forward_request(
        self, task_context: "ProxyTaskContext", request: A2ARequest, agent_name: str
    ):
        """
        Forwards a request to the downstream agent using its specific protocol.
        To be implemented by concrete proxy classes.
        """
        raise NotImplementedError
