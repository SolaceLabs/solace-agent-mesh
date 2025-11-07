"""
Abstract base class for proxy components.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

import httpx

from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.components.component_base import ComponentBase

from ....common.agent_registry import AgentRegistry
from pydantic import TypeAdapter, ValidationError

from ....common import a2a
from ....common.a2a.message import get_file_parts_from_message, update_message_parts
from ....common.a2a.protocol import (
    create_error_response,
    create_success_response,
    get_message_from_send_request,
    get_request_id,
    get_task_id_from_cancel_request,
)
from a2a.types import (
    A2ARequest,
    AgentCard,
    AgentCapabilities,
    AgentExtension,
    CancelTaskRequest,
    FilePart,
    InternalError,
    InvalidRequestError,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
from ...adk.services import initialize_artifact_service

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
        self.task_state_ttl_minutes = self.get_config("task_state_ttl_minutes", 60)
        self.task_cleanup_interval_minutes = self.get_config(
            "task_cleanup_interval_minutes", 10
        )

        self.agent_registry = AgentRegistry()
        self.artifact_service: Optional[BaseArtifactService] = None
        # Store (timestamp, ProxyTaskContext) tuples for TTL-based cleanup
        self.active_tasks: Dict[str, Tuple[float, ProxyTaskContext]] = {}
        self.active_tasks_lock = threading.Lock()

        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._async_init_future: Optional[concurrent.futures.Future] = None
        self._discovery_timer_id = f"proxy_discovery_{self.name}"
        self._task_cleanup_timer_id = f"proxy_task_cleanup_{self.name}"

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

            # Perform initial synchronous discovery to populate the registry
            self._initial_discovery_sync()

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
        # Pass the event to the completion handler so it can NACK on failure
        future.add_done_callback(
            lambda f: self._handle_scheduled_task_completion(f, event)
        )

    async def _process_event_async(self, event: Event):
        """Asynchronous event processing logic."""
        if event.event_type == EventType.MESSAGE:
            message_handled = False
            try:
                await self._handle_a2a_request(event.data)
                message_handled = True
            finally:
                # Mark that we attempted to handle the message
                # (success/failure ack/nack is done inside _handle_a2a_request)
                if not hasattr(event, "_proxy_message_handled"):
                    event._proxy_message_handled = message_handled
        elif event.event_type == EventType.TIMER:
            timer_id = event.data.get("timer_id")
            if timer_id == self._discovery_timer_id:
                await self._discover_and_publish_agents()
            elif timer_id == self._task_cleanup_timer_id:
                await self._cleanup_stale_tasks()
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

            # Directly validate the payload against the modern A2A spec
            adapter = TypeAdapter(A2ARequest)
            a2a_request = adapter.validate_python(payload)

            jsonrpc_request_id = get_request_id(a2a_request)

            # Get agent name from topic
            topic = message.get_topic()
            if not topic:
                raise ValueError("Message has no topic.")
            target_agent_name = topic.split("/")[-1]

            if isinstance(
                a2a_request.root, (SendMessageRequest, SendStreamingMessageRequest)
            ):
                from .proxy_task_context import ProxyTaskContext

                logical_task_id = jsonrpc_request_id

                # Resolve inbound artifacts before forwarding
                resolved_message = await self._resolve_inbound_artifacts(a2a_request)
                a2a_request.root.params.message = resolved_message

                a2a_context = {
                    "jsonrpc_request_id": jsonrpc_request_id,
                    "logical_task_id": logical_task_id,
                    "session_id": a2a.get_context_id(resolved_message),
                    "user_id": message.get_user_properties().get(
                        "userId", "default_user"
                    ),
                    "status_topic": message.get_user_properties().get("a2aStatusTopic"),
                    "reply_to_topic": message.get_user_properties().get("replyTo"),
                    "is_streaming": isinstance(a2a_request.root, SendStreamingMessageRequest),
                    "user_properties": message.get_user_properties(),
                }
                task_context = ProxyTaskContext(
                    task_id=logical_task_id, a2a_context=a2a_context
                )
                with self.active_tasks_lock:
                    self.active_tasks[logical_task_id] = (time.time(), task_context)

                log.info(
                    "%s Forwarding request for task %s to agent %s.",
                    self.log_identifier,
                    logical_task_id,
                    target_agent_name,
                )
                await self._forward_request(
                    task_context, a2a_request.root, target_agent_name
                )

            elif isinstance(a2a_request.root, CancelTaskRequest):
                logical_task_id = get_task_id_from_cancel_request(a2a_request)

                # Get the agent name from the topic (same as for send_message)
                target_agent_name = topic.split("/")[-1]

                with self.active_tasks_lock:
                    task_entry = self.active_tasks.get(logical_task_id)
                    task_context = task_entry[1] if task_entry else None
                
                if task_context:
                    log.info(
                        "%s Forwarding cancellation request for task %s to agent %s.",
                        self.log_identifier,
                        logical_task_id,
                        target_agent_name,
                    )
                    # Forward the cancel request to the downstream agent
                    await self._forward_request(
                        task_context, a2a_request.root, target_agent_name
                    )
                else:
                    # Task not found in active tasks
                    log.warning(
                        "%s Received cancel request for unknown task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )
                    from a2a.types import TaskNotFoundError
                    error = TaskNotFoundError(data={"taskId": logical_task_id})
                    await self._publish_error_response(jsonrpc_request_id, error, message)
            else:
                log.warning(
                    "%s Received unhandled A2A request type: %s",
                    self.log_identifier,
                    type(a2a_request.root).__name__,
                )

            message.call_acknowledgements()

        except (ValueError, TypeError, ValidationError) as e:
            log.error(
                "%s Failed to parse or validate A2A request: %s",
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

    async def _resolve_inbound_artifacts(self, request: A2ARequest) -> a2a.Message:
        """
        Resolves artifact URIs in an incoming message into byte content.
        This is necessary before forwarding to a downstream agent that may not
        share the same artifact store.
        """
        original_message = get_message_from_send_request(request)
        if not original_message:
            return None

        file_parts = get_file_parts_from_message(original_message)
        if not file_parts:
            return original_message  # No files to resolve

        log_id = f"{self.log_identifier}[ResolveInbound:{get_request_id(request)}]"
        log.info("%s Found %d file parts to resolve.", log_id, len(file_parts))

        resolved_parts = []
        all_parts = a2a.get_parts_from_message(original_message)

        for part in all_parts:
            if isinstance(part, FilePart):
                resolved_part = await a2a.resolve_file_part_uri(
                    part, self.artifact_service, log_id
                )
                resolved_parts.append(resolved_part)
            else:
                resolved_parts.append(part)

        return update_message_parts(original_message, resolved_parts)

    def _update_agent_card_for_proxy(self, agent_card: AgentCard, agent_alias: str) -> AgentCard:
        """
        Updates an agent card for proxying by:
        1. Setting the name to the proxy alias
        2. Adding/updating the display-name extension to preserve the original name

        Args:
            agent_card: The original agent card fetched from the remote agent
            agent_alias: The alias/name to use for this agent in SAM

        Returns:
            A modified copy of the agent card with updated name and display-name extension
        """
        # Create a deep copy to avoid modifying the original
        card_copy = agent_card.model_copy(deep=True)

        # Store the original name as the display name (if not already set)
        # This preserves the agent's identity while allowing it to be proxied under an alias
        original_display_name = agent_card.name

        # Check if there's already a display-name extension to preserve
        display_name_uri = "https://solace.com/a2a/extensions/display-name"
        if card_copy.capabilities and card_copy.capabilities.extensions:
            for ext in card_copy.capabilities.extensions:
                if ext.uri == display_name_uri and ext.params and ext.params.get("display_name"):
                    # Use the existing display name from the extension
                    original_display_name = ext.params["display_name"]
                    break

        # Update the card's name to the proxy alias
        card_copy.name = agent_alias

        # Ensure capabilities and extensions exist
        if not card_copy.capabilities:
            card_copy.capabilities = AgentCapabilities(extensions=[])
        if not card_copy.capabilities.extensions:
            card_copy.capabilities.extensions = []

        # Find or create the display-name extension
        display_name_ext = None
        for ext in card_copy.capabilities.extensions:
            if ext.uri == display_name_uri:
                display_name_ext = ext
                break

        if display_name_ext:
            # Update existing extension
            if not display_name_ext.params:
                display_name_ext.params = {}
            display_name_ext.params["display_name"] = original_display_name
        else:
            # Create new extension
            new_ext = AgentExtension(
                uri=display_name_uri,
                params={"display_name": original_display_name}
            )
            card_copy.capabilities.extensions.append(new_ext)

        log.debug(
            "%s Updated agent card: name='%s', display_name='%s'",
            self.log_identifier,
            agent_alias,
            original_display_name
        )

        return card_copy

    def _initial_discovery_sync(self):
        """
        Synchronously fetches agent cards to populate the registry at startup.
        This method does NOT publish the cards to the mesh.
        """
        log.info(
            "%s Performing initial synchronous agent discovery...", self.log_identifier
        )
        with httpx.Client() as client:
            for agent_config in self.proxied_agents_config:
                agent_alias = agent_config["name"]
                agent_url = agent_config.get("url")
                if not agent_url:
                    log.error(
                        "%s Skipping agent '%s' in initial discovery: no URL configured.",
                        self.log_identifier,
                        agent_alias,
                    )
                    continue
                try:
                    # Use a synchronous client for this initial blocking call
                    response = client.get(f"{agent_url}/.well-known/agent-card.json")
                    response.raise_for_status()
                    agent_card = AgentCard.model_validate(response.json())

                    # Update the card for proxying (preserves display name)
                    card_for_proxy = self._update_agent_card_for_proxy(agent_card, agent_alias)
                    self.agent_registry.add_or_update_agent(card_for_proxy)
                    log.info(
                        "%s Initial discovery successful for alias '%s' (actual name: '%s').",
                        self.log_identifier,
                        agent_alias,
                        agent_card.name,
                    )
                except Exception as e:
                    log.error(
                        "%s Failed initial discovery for agent '%s' at URL '%s': %s",
                        self.log_identifier,
                        agent_alias,
                        agent_url,
                        e,
                    )
        log.info("%s Initial synchronous discovery complete.", self.log_identifier)

    async def _discover_and_publish_agents(self):
        """
        Asynchronously fetches agent cards, updates the registry, and publishes them.
        This is intended for the recurring timer.
        """
        log.info("%s Starting recurring agent discovery cycle...", self.log_identifier)
        for agent_config in self.proxied_agents_config:
            try:
                modern_card = await self._fetch_agent_card(agent_config)
                if not modern_card:
                    continue

                agent_alias = agent_config["name"]
                # Update the card for proxying (preserves display name)
                card_for_registry = self._update_agent_card_for_proxy(modern_card, agent_alias)
                self.agent_registry.add_or_update_agent(card_for_registry)

                # Create a separate copy for publishing
                card_to_publish = card_for_registry.model_copy(deep=True)
                card_to_publish.url = (
                    f"solace:{a2a.get_agent_request_topic(self.namespace, agent_alias)}"
                )
                discovery_topic = a2a.get_discovery_topic(self.namespace)
                self._publish_a2a_message(
                    card_to_publish.model_dump(exclude_none=True), discovery_topic
                )
                log.info(
                    "%s Refreshed and published card for agent '%s'.",
                    self.log_identifier,
                    agent_alias,
                )
            except Exception as e:
                log.error(
                    "%s Failed to discover or publish card for agent '%s' in recurring cycle: %s",
                    self.log_identifier,
                    agent_config.get("name", "unknown"),
                    e,
                )

    async def _publish_status_update(
        self, event: TaskStatusUpdateEvent, a2a_context: Dict
    ):
        """Publishes a TaskStatusUpdateEvent to the appropriate Solace topic."""
        target_topic = a2a_context.get("status_topic")
        if not target_topic:
            log.warning(
                "%s No statusTopic in context for task %s. Cannot publish status update.",
                self.log_identifier,
                event.task_id,
            )
            return

        response = create_success_response(
            result=event, request_id=a2a_context.get("jsonrpc_request_id")
        )
        self._publish_a2a_message(
            response.model_dump(exclude_none=True),
            target_topic,
            user_properties=a2a_context.get("user_properties")
        )

    async def _publish_task_response(self, task: Task, a2a_context: Dict):
        """Publishes a Task object to the reply topic."""
        target_topic = a2a_context.get("reply_to_topic")
        if not target_topic:
            log.warning(
                "%s No replyToTopic in context for task %s. Cannot publish final response.",
                self.log_identifier,
                task.id,
            )
            return

        response = create_success_response(
            result=task, request_id=a2a_context.get("jsonrpc_request_id")
        )
        self._publish_a2a_message(
            response.model_dump(exclude_none=True),
            target_topic,
            user_properties=a2a_context.get("user_properties")
        )

    async def _publish_artifact_update(
        self, event: TaskArtifactUpdateEvent, a2a_context: Dict
    ):
        """Publishes a TaskArtifactUpdateEvent to the appropriate Solace topic."""
        target_topic = a2a_context.get("status_topic")
        if not target_topic:
            log.warning(
                "%s No statusTopic in context for task %s. Cannot publish artifact update.",
                self.log_identifier,
                event.task_id,
            )
            return

        response = create_success_response(
            result=event, request_id=a2a_context.get("jsonrpc_request_id")
        )
        self._publish_a2a_message(
            response.model_dump(exclude_none=True),
            target_topic,
            user_properties=a2a_context.get("user_properties")
        )

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

        response = create_error_response(error=error, request_id=request_id)
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

    def _handle_scheduled_task_completion(
        self, future: concurrent.futures.Future, event: Event
    ):
        """Callback to log exceptions from tasks scheduled on the async loop and NACK messages on failure."""
        if future.done() and future.exception():
            log.error(
                "%s Coroutine scheduled on async loop failed: %s",
                self.log_identifier,
                future.exception(),
                exc_info=future.exception(),
            )
            # NACK the message if this was a MESSAGE event that failed before being handled
            # The _proxy_message_handled flag is set in _process_event_async to track
            # whether _handle_a2a_request was entered (where ack/nack is normally done)
            if event.event_type == EventType.MESSAGE:
                message_handled = getattr(event, "_proxy_message_handled", False)
                if not message_handled:
                    try:
                        event.data.call_negative_acknowledgements()
                        log.warning(
                            "%s NACKed message due to async processing failure before entering request handler.",
                            self.log_identifier,
                        )
                    except Exception as nack_e:
                        log.error(
                            "%s Failed to NACK message after async processing failure: %s",
                            self.log_identifier,
                            nack_e,
                        )

    async def _cleanup_stale_tasks(self):
        """
        Removes task state older than configured TTL.
        This prevents memory leaks from tasks that complete without sending terminal events
        (e.g., due to agent crashes or network failures).
        """
        ttl_seconds = self.task_state_ttl_minutes * 60
        cutoff_time = time.time() - ttl_seconds

        with self.active_tasks_lock:
            stale_task_ids = [
                task_id
                for task_id, (timestamp, _) in self.active_tasks.items()
                if timestamp < cutoff_time
            ]
            for task_id in stale_task_ids:
                del self.active_tasks[task_id]
                log.warning(
                    "%s Cleaned up stale task %s (exceeded TTL of %d minutes)",
                    self.log_identifier,
                    task_id,
                    self.task_state_ttl_minutes,
                )

        if stale_task_ids:
            log.info(
                "%s Stale task cleanup removed %d tasks",
                self.log_identifier,
                len(stale_task_ids),
            )

    def _cleanup_task_state(self, task_id: str) -> None:
        """
        Cleans up state for a completed task.
        Called when a terminal event is detected (Task with terminal state,
        or TaskStatusUpdateEvent with final=true).

        Args:
            task_id: The ID of the task to clean up
        """
        with self.active_tasks_lock:
            entry = self.active_tasks.pop(task_id, None)
            if entry:
                log.info(
                    "%s Removed task %s from active_tasks (terminal event detected)",
                    self.log_identifier,
                    task_id,
                )
            else:
                log.debug(
                    "%s Task %s not found in active_tasks during cleanup (already removed)",
                    self.log_identifier,
                    task_id,
                )

    def _publish_discovered_cards(self):
        """Publishes all agent cards currently in the registry."""
        log.info(
            "%s Publishing initially discovered agent cards...", self.log_identifier
        )
        for agent_alias in self.agent_registry.get_agent_names():
            original_card = self.agent_registry.get_agent(agent_alias)
            if not original_card:
                continue

            # Create a copy for publishing to avoid modifying the card in the registry
            card_to_publish = original_card.model_copy(deep=True)
            card_to_publish.url = (
                f"solace:{a2a.get_agent_request_topic(self.namespace, agent_alias)}"
            )
            discovery_topic = a2a.get_discovery_topic(self.namespace)
            self._publish_a2a_message(
                card_to_publish.model_dump(exclude_none=True), discovery_topic
            )
            log.info(
                "%s Published initially discovered card for agent '%s'.",
                self.log_identifier,
                agent_alias,
            )

    def run(self):
        """
        Called by the framework to start the component's background tasks.
        This is the component's main entry point for active operations.
        """
        log.info(
            "%s Component is ready. Starting active operations.", self.log_identifier
        )

        # Publish the cards that were discovered synchronously during init
        self._publish_discovered_cards()

        # Schedule the recurring discovery timer
        if self.discovery_interval_sec > 0:
            self.add_timer(
                delay_ms=self.discovery_interval_sec * 1000,
                timer_id=self._discovery_timer_id,
                interval_ms=self.discovery_interval_sec * 1000,
            )
            log.info(
                "%s Scheduled recurring agent discovery every %d seconds.",
                self.log_identifier,
                self.discovery_interval_sec,
            )

        # Schedule the recurring task cleanup timer
        if self.task_cleanup_interval_minutes > 0:
            cleanup_interval_ms = self.task_cleanup_interval_minutes * 60 * 1000
            self.add_timer(
                delay_ms=cleanup_interval_ms,
                timer_id=self._task_cleanup_timer_id,
                interval_ms=cleanup_interval_ms,
            )
            log.info(
                "%s Scheduled recurring stale task cleanup every %d minutes (TTL: %d minutes).",
                self.log_identifier,
                self.task_cleanup_interval_minutes,
                self.task_state_ttl_minutes,
            )

        super().run()

    def clear_client_cache(self):
        """
        Clears all cached clients. Useful for testing when authentication
        configuration changes between tests.
        """
        # This method is intentionally empty in the base class.
        # Concrete implementations should override it if they cache clients.
        pass

    def cleanup(self):
        """Cleans up resources on component shutdown."""
        log.info("%s Cleaning up proxy component.", self.log_identifier)
        self.cancel_timer(self._discovery_timer_id)
        self.cancel_timer(self._task_cleanup_timer_id)

        # Clear active tasks (no need to signal cancellation - downstream agents own their tasks)
        with self.active_tasks_lock:
            self.active_tasks.clear()

        if self._async_loop and self._async_loop.is_running():
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
