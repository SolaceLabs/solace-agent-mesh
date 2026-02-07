"""
Sandbox Worker Component.

This component handles sandboxed execution of Python tools via nsjail.
It extends SamComponentBase to use the standard SAM infrastructure for
Solace communication.
"""

import logging
import time
from typing import Any, Dict, Optional

from solace_ai_connector.common.message import Message as SolaceMessage

from ..agent.adk.services import initialize_artifact_service
from ..common.sac.sam_component_base import SamComponentBase
from ..common.a2a import protocol as a2a
from .nsjail_runner import NsjailRunner
from .protocol import (
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxStatusUpdate,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

log = logging.getLogger(__name__)


class SandboxWorkerComponent(SamComponentBase):
    """
    Component that executes sandboxed Python tools via nsjail.

    Uses the same SAM infrastructure as agents for Solace communication.
    Receives tool invocation requests, executes them in a sandboxed environment,
    and publishes results back to the requesting agent.
    """

    def __init__(self, info: dict[str, Any], **kwargs: Any):
        """
        Initialize the sandbox worker component.

        Args:
            info: Component info dictionary from SAC framework
            **kwargs: Additional keyword arguments
        """
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

        # nsjail configuration
        self.nsjail_config: Dict[str, Any] = self.get_config("nsjail", {})
        self.default_timeout_seconds: int = self.get_config("default_timeout_seconds", 300)

        # Initialize nsjail runner
        self.nsjail_runner = NsjailRunner(self.nsjail_config)

        # Track active executions for cleanup
        self._active_executions: Dict[str, Any] = {}

        log.info("%s SandboxWorkerComponent initialized", self.log_identifier)

    def invoke(self, message: SolaceMessage, data: dict) -> Optional[dict]:
        """
        Placeholder invoke method - primary logic is in _handle_message_async.

        This is required by the SAC framework but we handle messages via
        the async handler instead.
        """
        return None

    async def _handle_message_async(self, message: SolaceMessage, topic: str) -> None:
        """
        Handle incoming messages asynchronously.

        Routes messages to appropriate handlers based on topic:
        - Tool invocation requests
        - Discovery messages (for agent cards)

        Args:
            message: The incoming Solace message
            topic: The topic the message was received on
        """
        log.debug(
            "%s Received message on topic: %s",
            self.log_identifier,
            topic,
        )

        # Check if this is a tool invocation request
        request_topic = a2a.get_sandbox_request_topic(self.namespace, self.worker_id)
        discovery_topic = a2a.get_discovery_subscription_topic(self.namespace)

        try:
            if topic == request_topic:
                await self._handle_tool_invocation(message)
            elif a2a.topic_matches_subscription(topic, discovery_topic):
                # Handle discovery messages (agent cards, gateway cards)
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

    async def _handle_tool_invocation(self, message: SolaceMessage) -> None:
        """
        Handle a tool invocation request.

        Parses the request, executes the tool in nsjail sandbox,
        and publishes the result back to the requesting agent.

        Args:
            message: The incoming Solace message containing the invocation request
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
                "%s Received tool invocation request: id=%s, tool=%s, module=%s.%s",
                self.log_identifier,
                request_id,
                params.tool_name,
                params.module,
                params.function,
            )

            # Get routing info from user properties
            user_props = message.get_user_properties() or {}
            reply_to = user_props.get("replyTo")
            status_topic = user_props.get("a2aStatusTopic")

            if not reply_to:
                log.error(
                    "%s No replyTo in user properties for request %s",
                    self.log_identifier,
                    request_id,
                )
                return

            # Create status callback that publishes to Solace
            def on_status(text: str) -> None:
                if status_topic:
                    status_update = SandboxStatusUpdate(
                        task_id=params.task_id,
                        status_text=text,
                    )
                    self.publish_a2a_message(
                        payload=status_update.model_dump(),
                        topic=status_topic,
                    )

            # Execute the tool via nsjail runner
            response = await self.nsjail_runner.execute_tool(
                request=request,
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

        Args:
            message: The incoming discovery message
            topic: The topic the message was received on
        """
        log.debug(
            "%s Received discovery message on topic: %s",
            self.log_identifier,
            topic,
        )
        # TODO: Implement discovery message handling if needed

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
            # TODO: Implement execution cancellation

        self._active_executions.clear()

        log.info("%s SandboxWorkerComponent stopped", self.log_identifier)
