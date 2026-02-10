"""
Sandbox Worker Component.

This component handles sandboxed execution of Python tools via bubblewrap (bwrap).
It extends SamComponentBase to use the standard SAM infrastructure for
Solace communication.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Set

from solace_ai_connector.common.message import Message as SolaceMessage

from ..agent.adk.services import initialize_artifact_service
from ..common.sac.sam_component_base import SamComponentBase
from ..common.a2a import protocol as a2a
from .manifest import ToolManifest
from .sandbox_runner import SandboxRunner
from .protocol import (
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxStatusUpdate,
    SandboxStatusUpdateParams,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

log = logging.getLogger(__name__)

info = {
    "class_name": "SandboxWorkerComponent",
    "description": (
        "Executes sandboxed Python tools via bubblewrap (bwrap). "
        "Configuration is defined in the app-level 'app_config' block "
        "and validated by SandboxWorkerApp."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "description": "Tool invocation request messages.",
    },
    "output_schema": {
        "type": "object",
        "description": "Tool invocation response messages.",
    },
}


class SandboxWorkerComponent(SamComponentBase):
    """
    Component that executes sandboxed Python tools via bubblewrap (bwrap).

    Uses the same SAM infrastructure as agents for Solace communication.
    Receives tool invocation requests, executes them in a sandboxed environment,
    and publishes results back to the requesting agent.

    Subscriptions are managed dynamically based on the tool manifest:
    - On startup, subscribes to one topic per tool in the manifest
    - Periodically checks manifest for changes and adjusts subscriptions
    - Handles stale subscriptions (tools removed from manifest)
    """

    def __init__(self, **kwargs: Any):
        super().__init__(info, **kwargs)

        # Get worker-specific configuration
        self.worker_id: str = self.get_config("worker_id", "sandbox-worker-001")

        log.info(
            "%s Initializing SandboxWorkerComponent (worker_id=%s, namespace=%s)",
            self.log_identifier,
            self.worker_id,
            self.namespace,
        )

        # Initialize artifact service (same as agents)
        try:
            self.artifact_service = initialize_artifact_service(self)
            log.info("%s Artifact service initialized", self.log_identifier)
        except Exception as e:
            log.error(
                "%s Failed to initialize artifact service: %s",
                self.log_identifier,
                e,
            )
            raise

        # Load tool manifest
        manifest_path = self.get_config("manifest_path", "/tools/manifest.yaml")
        self.manifest = ToolManifest(manifest_path)
        self.manifest.ensure_packages_installed()

        # Track which tool topics we're currently subscribed to
        self._subscribed_tools: Set[str] = set()

        # Sandbox configuration - merge app-level tools_python_dir into runner config
        sandbox_cfg = self.get_config("sandbox", {})
        if hasattr(sandbox_cfg, "model_dump"):
            sandbox_cfg = sandbox_cfg.model_dump()
        sandbox_cfg["tools_python_dir"] = self.get_config(
            "tools_python_dir", "/tools/python"
        )
        self.default_timeout_seconds: int = self.get_config("default_timeout_seconds", 300)

        # Initialize sandbox runner
        self.sandbox_runner = SandboxRunner(sandbox_cfg)

        # Track active executions for cleanup
        self._active_executions: Dict[str, Any] = {}

        # Background thread to watch manifest for changes
        self._manifest_poll_interval: float = 2.0  # seconds
        self._manifest_poll_stop = threading.Event()
        self._manifest_poll_thread = threading.Thread(
            target=self._manifest_poll_loop,
            name="manifest-watcher",
            daemon=True,
        )
        self._manifest_poll_thread.start()

        log.info("%s SandboxWorkerComponent initialized", self.log_identifier)

    def _get_component_id(self) -> str:
        """Returns the worker ID as the component identifier."""
        return self.worker_id

    def _get_component_type(self) -> str:
        """Returns 'sandbox_worker' as the component type."""
        return "sandbox_worker"

    def _manifest_poll_loop(self) -> None:
        """Background thread that watches for manifest changes."""
        while not self._manifest_poll_stop.wait(self._manifest_poll_interval):
            try:
                if self.manifest.has_changed():
                    log.info(
                        "%s Manifest change detected, syncing subscriptions",
                        self.log_identifier,
                    )
                    self._sync_subscriptions()
            except Exception as e:
                log.warning(
                    "%s Error in manifest poll loop: %s",
                    self.log_identifier,
                    e,
                )

    def _pre_async_cleanup(self) -> None:
        """Pre-cleanup actions before stopping the async loop."""
        self._manifest_poll_stop.set()

    def invoke(self, message: SolaceMessage, data: dict) -> Optional[dict]:
        """
        Placeholder invoke method - primary logic is in _handle_message_async.

        This is required by the SAC framework but we handle messages via
        the async handler instead.
        """
        return None

    def _extract_tool_name_from_topic(self, topic: str) -> Optional[str]:
        """
        Extract the tool name from an invoke topic.

        Topic format: {namespace}/a2a/v1/sam_remote_tool/invoke/{tool_name}
        """
        prefix = a2a.get_a2a_base_topic(self.namespace) + "/sam_remote_tool/invoke/"
        if topic.startswith(prefix):
            return topic[len(prefix):]
        return None

    def _sync_subscriptions(self) -> None:
        """
        Synchronize subscriptions with the current manifest.

        Adds subscriptions for new tools and removes subscriptions for
        tools no longer in the manifest.
        """
        current_tools = self.manifest.get_tool_names()

        # Tools to add (in manifest but not subscribed)
        tools_to_add = current_tools - self._subscribed_tools
        # Tools to remove (subscribed but no longer in manifest)
        tools_to_remove = self._subscribed_tools - current_tools

        for tool_name in tools_to_add:
            topic = a2a.get_sam_remote_tool_invoke_topic(self.namespace, tool_name)
            try:
                self.subscribe(topic)
                self._subscribed_tools.add(tool_name)
                log.info(
                    "%s Subscribed to tool topic: %s",
                    self.log_identifier,
                    topic,
                )
            except Exception as e:
                log.error(
                    "%s Failed to subscribe to tool topic %s: %s",
                    self.log_identifier,
                    topic,
                    e,
                )

        for tool_name in tools_to_remove:
            topic = a2a.get_sam_remote_tool_invoke_topic(self.namespace, tool_name)
            try:
                self.unsubscribe(topic)
                self._subscribed_tools.discard(tool_name)
                log.info(
                    "%s Unsubscribed from tool topic: %s",
                    self.log_identifier,
                    topic,
                )
            except Exception as e:
                log.error(
                    "%s Failed to unsubscribe from tool topic %s: %s",
                    self.log_identifier,
                    topic,
                    e,
                )

    async def _handle_message_async(self, message: SolaceMessage, topic: str) -> None:
        """
        Handle incoming messages asynchronously.

        Routes messages to appropriate handlers based on topic:
        - Tool invocation requests (per-tool topics)
        - Discovery messages (for agent cards)
        """
        log.debug(
            "%s Received message on topic: %s",
            self.log_identifier,
            topic,
        )

        discovery_topic = a2a.get_discovery_subscription_topic(self.namespace)

        try:
            # Check if this is a tool invocation request
            tool_name = self._extract_tool_name_from_topic(topic)
            if tool_name is not None:
                await self._handle_tool_invocation(message, tool_name)
            elif a2a.topic_matches_subscription(topic, discovery_topic):
                await self._handle_discovery_message(message, topic)
            else:
                log.warning(
                    "%s Received message on unexpected topic: %s",
                    self.log_identifier,
                    topic,
                )

            # ACK the message
            message.call_acknowledgements()

        except Exception as e:
            log.error(
                "%s Error handling message on topic %s: %s",
                self.log_identifier,
                topic,
                e,
                exc_info=True,
            )
            # NACK the message on error
            try:
                message.call_negative_acknowledgements()
            except Exception as nack_e:
                log.error(
                    "%s Failed to NACK message: %s",
                    self.log_identifier,
                    nack_e,
                )

    async def _handle_tool_invocation(self, message: SolaceMessage, tool_name: str) -> None:
        """
        Handle a tool invocation request.

        Resolves the tool from the manifest, executes it in the bwrap sandbox,
        and publishes the result back to the requesting agent.

        If the tool is not found in the manifest (stale subscription),
        unsubscribes from the topic and returns TOOL_NOT_AVAILABLE error.
        """
        start_time = time.time()
        request_id = "unknown"

        try:
            # Parse the request
            payload = message.get_payload()
            request = SandboxToolInvocationRequest.model_validate(payload)
            request_id = request.id
            params = request.params

            log.info(
                "%s Received tool invocation request: id=%s, tool=%s",
                self.log_identifier,
                request_id,
                params.tool_name,
            )

            # Get routing info from user properties
            user_props = message.get_user_properties() or {}
            reply_to = user_props.get("replyTo")
            status_topic = user_props.get("statusTo")

            if not reply_to:
                log.error(
                    "%s No replyTo in user properties for request %s",
                    self.log_identifier,
                    request_id,
                )
                return

            # Resolve tool from manifest
            manifest_entry = self.manifest.get_tool(tool_name)

            if manifest_entry is None:
                # Stale subscription - tool no longer in manifest
                log.warning(
                    "%s Tool '%s' not found in manifest (stale subscription). "
                    "Unsubscribing and returning TOOL_NOT_AVAILABLE.",
                    self.log_identifier,
                    tool_name,
                )

                # Unsubscribe from this tool's topic
                invoke_topic = a2a.get_sam_remote_tool_invoke_topic(
                    self.namespace, tool_name
                )
                try:
                    self.unsubscribe(invoke_topic)
                    self._subscribed_tools.discard(tool_name)
                except Exception as unsub_e:
                    log.error(
                        "%s Failed to unsubscribe from stale topic %s: %s",
                        self.log_identifier,
                        invoke_topic,
                        unsub_e,
                    )

                # Send error response
                response = SandboxToolInvocationResponse.failure(
                    request_id=request_id,
                    code=SandboxErrorCodes.TOOL_NOT_AVAILABLE,
                    message=f"Tool '{tool_name}' is not available on this worker",
                )
                self.publish_a2a_message(
                    payload=response.model_dump(exclude_none=True),
                    topic=reply_to,
                )
                return

            # Create status callback that publishes to Solace
            def on_status(text: str) -> None:
                if status_topic:
                    status_update = SandboxStatusUpdate(
                        params=SandboxStatusUpdateParams(
                            task_id=params.task_id,
                            status_text=text,
                        ),
                    )
                    self.publish_a2a_message(
                        payload=status_update.model_dump(),
                        topic=status_topic,
                    )

            # Execute the tool via sandbox runner
            response = await self.sandbox_runner.execute_tool(
                request=request,
                manifest_entry=manifest_entry,
                artifact_service=self.artifact_service,
                status_callback=on_status,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            log.info(
                "%s Tool execution completed: id=%s, time=%dms",
                self.log_identifier,
                request_id,
                execution_time_ms,
            )

            self.publish_a2a_message(
                payload=response.model_dump(exclude_none=True),
                topic=reply_to,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            log.error(
                "%s Tool invocation failed: id=%s, error=%s",
                self.log_identifier,
                request_id,
                e,
                exc_info=True,
            )

            # Try to get reply_to for error response
            try:
                user_props = message.get_user_properties() or {}
                reply_to = user_props.get("replyTo")

                if reply_to:
                    response = SandboxToolInvocationResponse.failure(
                        request_id=request_id,
                        code=SandboxErrorCodes.EXECUTION_ERROR,
                        message=str(e),
                    )
                    self.publish_a2a_message(
                        payload=response.model_dump(exclude_none=True),
                        topic=reply_to,
                    )
            except Exception as resp_e:
                log.error(
                    "%s Failed to send error response: %s",
                    self.log_identifier,
                    resp_e,
                )

    async def _handle_discovery_message(
        self, message: SolaceMessage, topic: str
    ) -> None:
        """
        Handle discovery messages (agent cards, gateway cards).

        The sandbox worker may need to track available agents for routing.
        For now, this is a placeholder.
        """
        log.debug(
            "%s Received discovery message on topic: %s",
            self.log_identifier,
            topic,
        )

    def stop_component(self):
        """Clean up resources when component is stopped."""
        log.info("%s Stopping SandboxWorkerComponent...", self.log_identifier)

        # Cancel any active executions
        for exec_id in list(self._active_executions.keys()):
            log.warning(
                "%s Cancelling active execution: %s",
                self.log_identifier,
                exec_id,
            )

        self._active_executions.clear()

        log.info("%s SandboxWorkerComponent stopped", self.log_identifier)
