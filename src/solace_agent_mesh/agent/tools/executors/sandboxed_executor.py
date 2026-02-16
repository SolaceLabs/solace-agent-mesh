"""
SAM Remote Tool Executor.

This executor delegates tool execution to a remote worker (e.g., sandbox worker)
via Solace broker using topic-based routing. The agent only needs to know the
tool name - routing and module resolution happen on the worker side.
"""

import asyncio
import concurrent.futures
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext
from google.genai import types as genai_types

from .base import ToolExecutor, ToolExecutionResult, register_executor
from ....common.a2a import (
    get_sam_remote_tool_init_topic,
    get_sam_remote_tool_invoke_topic,
    get_sam_remote_tool_response_topic,
    get_sam_remote_tool_status_topic,
)
from ....common.a2a.types import ArtifactInfo
from ..artifact_types import Artifact
from ...utils.artifact_helpers import METADATA_SUFFIX
from ...utils.context_helpers import get_original_session_id
from ....sandbox.protocol import (
    ArtifactReference,
    SandboxErrorCodes,
    SandboxInitParams,
    SandboxInvokeParams,
    SandboxInvokeResult,
    SandboxToolInitRequest,
    SandboxToolInitResponse,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


@register_executor("sam_remote")
class SamRemoteExecutor(ToolExecutor):
    """
    Executor that runs tools on a remote worker via Solace broker.

    This executor sends tool invocation requests to a worker using
    topic-based routing (one topic per tool name). Workers subscribe
    to topics for tools they support based on their manifest.

    On TOOL_NOT_AVAILABLE errors, the executor retries once after a
    short delay to handle tool migration between workers.

    Configuration:
        tool_name: Name of the tool (used for topic routing)
        timeout_seconds: Maximum execution time (default: 300)
        sandbox_profile: Execution profile hint (default: standard)
    """

    def __init__(
        self,
        tool_name: str,
        timeout_seconds: int = 300,
        sandbox_profile: str = "standard",
    ):
        self._tool_name = tool_name
        self._timeout_seconds = timeout_seconds
        self._sandbox_profile = sandbox_profile

        # Will be set during initialize()
        self._component: Optional["SamAgentComponent"] = None
        self._namespace: Optional[str] = None
        self._agent_name: Optional[str] = None

        # Track pending requests (thread-safe concurrent futures)
        self._pending_responses: Dict[str, concurrent.futures.Future] = {}
        # Track a2a_context per correlation_id for status forwarding
        self._pending_a2a_contexts: Dict[str, Dict[str, Any]] = {}

    @property
    def executor_type(self) -> str:
        return "sam_remote"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """
        Initialize the executor with the host component for publishing.
        """
        log_id = f"[SamRemoteExecutor:{self._tool_name}]"
        log.info("%s Initializing...", log_id)

        self._component = component
        self._namespace = component.namespace
        self._agent_name = component.agent_name

        log.info(
            "%s Initialized (timeout=%ds)",
            log_id,
            self._timeout_seconds,
        )

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """
        Execute the tool on a remote worker.

        Sends an invocation request via Solace and waits for the response.
        Retries once on TOOL_NOT_AVAILABLE (handles tool migration).
        """
        result = await self._execute_once(args, tool_context, tool_config)

        # Retry once on TOOL_NOT_AVAILABLE
        if (
            not result.success
            and result.error_code == SandboxErrorCodes.TOOL_NOT_AVAILABLE
        ):
            log.info(
                "[SamRemoteExecutor:%s] Got TOOL_NOT_AVAILABLE, retrying in 1s...",
                self._tool_name,
            )
            await asyncio.sleep(1.0)
            result = await self._execute_once(args, tool_context, tool_config)

        return result

    async def _execute_once(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a single attempt at running the tool."""
        log_id = f"[SamRemoteExecutor:{self._tool_name}]"

        if not self._component:
            return ToolExecutionResult.fail(
                error="Executor not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Extract context information
            invocation_context = getattr(tool_context, "_invocation_context", None)
            if invocation_context:
                app_name = getattr(invocation_context, "app_name", self._agent_name)
                user_id = getattr(invocation_context, "user_id", "unknown")
                session_id = get_original_session_id(invocation_context)
            else:
                app_name = self._agent_name
                user_id = "unknown"
                session_id = "unknown"

            # Extract artifacts from args (DynamicTool pre-loads Artifact
            # objects). Send lightweight references so the worker loads
            # content from the shared artifact service — artifact data
            # should never transit through the broker.
            artifact_references = {}
            clean_args = {}
            for key, value in args.items():
                if isinstance(value, Artifact):
                    artifact_references[key] = ArtifactReference(
                        filename=value.filename,
                        version=value.version,
                    )
                    # Pass filename string to the tool args
                    clean_args[key] = value.filename
                elif isinstance(value, list) and value and isinstance(value[0], Artifact):
                    # List[Artifact] - reference each artifact
                    for idx, art in enumerate(value):
                        ref_key = f"{key}[{idx}]"
                        artifact_references[ref_key] = ArtifactReference(
                            filename=art.filename,
                            version=art.version,
                        )
                    clean_args[key] = [art.filename for art in value]
                else:
                    clean_args[key] = value

            # Build the invocation request
            params = SandboxInvokeParams(
                task_id=correlation_id,
                tool_name=self._tool_name,
                args=clean_args,
                tool_config=tool_config,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                artifact_references=artifact_references,
                timeout_seconds=self._timeout_seconds,
                sandbox_profile=self._sandbox_profile,
            )

            request = SandboxToolInvocationRequest(
                id=correlation_id,
                params=params,
            )

            # Build topics - route by tool name
            request_topic = get_sam_remote_tool_invoke_topic(
                self._namespace, self._tool_name
            )
            reply_to = get_sam_remote_tool_response_topic(
                self._namespace, self._agent_name, correlation_id
            )
            status_topic = get_sam_remote_tool_status_topic(
                self._namespace, self._agent_name, correlation_id
            )

            # User properties for routing (following A2A patterns)
            user_properties = {
                "replyTo": reply_to,
                "statusTo": status_topic,
                "clientId": self._agent_name,
                "userId": user_id,
            }

            log.info(
                "%s Sending request: id=%s, topic=%s",
                log_id,
                correlation_id,
                request_topic,
            )

            # Create a thread-safe future for the response
            response_future = concurrent.futures.Future()
            self._pending_responses[correlation_id] = response_future

            # Store a2a_context so handle_status can forward updates upstream
            a2a_context = tool_context.state.get("a2a_context")
            if a2a_context:
                self._pending_a2a_contexts[correlation_id] = a2a_context

            try:
                # Publish the request
                self._component.publish_a2a_message(
                    payload=request.model_dump(exclude_none=True),
                    topic=request_topic,
                    user_properties=user_properties,
                )

                # Wait for response with timeout
                try:
                    asyncio_future = asyncio.wrap_future(response_future)
                    response_payload = await asyncio.wait_for(
                        asyncio_future,
                        timeout=self._timeout_seconds + 10,
                    )

                    response = SandboxToolInvocationResponse.model_validate(
                        response_payload
                    )

                    if response.error:
                        return ToolExecutionResult.fail(
                            error=response.error.message,
                            error_code=response.error.code,
                        )

                    if response.result:
                        if response.result.timed_out:
                            return ToolExecutionResult.fail(
                                error=f"Tool execution timed out after {self._timeout_seconds}s",
                                error_code=SandboxErrorCodes.TIMEOUT,
                            )

                        # If the tool created output artifacts, register them
                        # in the framework (metadata + artifact_delta) without
                        # re-saving data — the container already saved to the
                        # shared artifact store.
                        if response.result.created_artifacts:
                            log.info(
                                "%s Response contains %d created artifact(s), "
                                "registering in framework...",
                                log_id,
                                len(response.result.created_artifacts),
                            )
                            await self._register_sandbox_artifacts(
                                response.result,
                                tool_context=tool_context,
                                app_name=app_name,
                                user_id=user_id,
                                session_id=session_id,
                            )

                        return ToolExecutionResult.ok(
                            data=response.result.tool_result,
                            metadata={
                                "execution_time_ms": response.result.execution_time_ms,
                            },
                        )

                    return ToolExecutionResult.fail(
                        error="Empty response from remote worker",
                        error_code=SandboxErrorCodes.INTERNAL_ERROR,
                    )

                except asyncio.TimeoutError:
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    log.error(
                        "%s Request timed out: id=%s, elapsed=%dms",
                        log_id,
                        correlation_id,
                        execution_time_ms,
                    )
                    return ToolExecutionResult.fail(
                        error=f"No response from remote worker within {self._timeout_seconds}s",
                        error_code=SandboxErrorCodes.TIMEOUT,
                        metadata={"execution_time_ms": execution_time_ms},
                    )

            finally:
                # Clean up pending request
                self._pending_responses.pop(correlation_id, None)
                self._pending_a2a_contexts.pop(correlation_id, None)

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            log.exception("%s Execution failed: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Remote tool execution failed: {str(e)}",
                error_code=SandboxErrorCodes.EXECUTION_ERROR,
                metadata={"execution_time_ms": execution_time_ms},
            )

    async def _register_sandbox_artifacts(
        self,
        result: SandboxInvokeResult,
        tool_context: ToolContext,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """
        Register sandbox-created artifacts in the framework without re-saving data.

        The container already saved the artifact data to the shared artifact store.
        This method:
        1. Saves only the metadata companion file (.metadata.json)
        2. Populates artifact_delta so after_tool callbacks work
        3. Publishes artifact saved notifications for the UI
        """
        log_id = f"[SamRemoteExecutor:{self._tool_name}]"
        artifact_service = getattr(self._component, "artifact_service", None)

        if not artifact_service:
            log.warning(
                "%s No artifact service on component — cannot register artifacts",
                log_id,
            )
            return

        for artifact_meta in result.created_artifacts:
            try:
                # Save the metadata companion file (the container only saves
                # the raw data artifact, not the .metadata.json that the
                # framework's after_tool callbacks expect).
                metadata_dict = {
                    "filename": artifact_meta.filename,
                    "mime_type": artifact_meta.mime_type,
                    "size_bytes": artifact_meta.size_bytes,
                    "timestamp_utc": datetime.now(timezone.utc).timestamp(),
                    "source": "sandbox_tool",
                }
                metadata_bytes = json.dumps(metadata_dict, indent=2).encode("utf-8")
                metadata_filename = f"{artifact_meta.filename}{METADATA_SUFFIX}"

                await artifact_service.save_artifact(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=metadata_filename,
                    artifact=genai_types.Part.from_bytes(
                        data=metadata_bytes, mime_type="application/json"
                    ),
                )

                # Register in artifact_delta so after_tool callbacks
                # (metadata injection, artifact tracking) work correctly.
                if (
                    hasattr(tool_context, "actions")
                    and hasattr(tool_context.actions, "artifact_delta")
                ):
                    tool_context.actions.artifact_delta[
                        artifact_meta.filename
                    ] = artifact_meta.version

                # Publish artifact saved notification for the UI
                try:
                    a2a_context = tool_context.state.get("a2a_context")
                    if a2a_context and self._component:
                        artifact_info = ArtifactInfo(
                            filename=artifact_meta.filename,
                            version=artifact_meta.version,
                            mime_type=artifact_meta.mime_type,
                            size=artifact_meta.size_bytes,
                        )
                        function_call_id = (
                            tool_context.state.get("function_call_id")
                            or getattr(tool_context, "function_call_id", None)
                        )
                        await self._component.notify_artifact_saved(
                            artifact_info=artifact_info,
                            a2a_context=a2a_context,
                            function_call_id=function_call_id,
                        )
                except Exception as notify_err:
                    log.warning(
                        "%s Failed to publish artifact notification for %s: %s",
                        log_id,
                        artifact_meta.filename,
                        notify_err,
                    )

                log.info(
                    "%s Registered sandbox artifact: %s (v%d, %d bytes)",
                    log_id,
                    artifact_meta.filename,
                    artifact_meta.version,
                    artifact_meta.size_bytes,
                )

            except Exception as e:
                log.error(
                    "%s Failed to register sandbox artifact %s: %s",
                    log_id,
                    artifact_meta.filename,
                    e,
                    exc_info=True,
                )

    def handle_response(self, correlation_id: str, payload: Dict[str, Any]) -> None:
        """
        Handle a response from the remote worker.

        Called by the agent component when it receives a message on the
        sam_remote_tool response topic.
        """
        future = self._pending_responses.get(correlation_id)
        if future and not future.done():
            log.info(
                "[SamRemoteExecutor] Resolving future for correlation_id=%s",
                correlation_id,
            )
            future.set_result(payload)
        else:
            log.warning(
                "[SamRemoteExecutor] Received response for unknown or completed "
                "request: correlation_id=%s",
                correlation_id,
            )

    def handle_status(self, correlation_id: str, status_text: str) -> None:
        """
        Handle a status update from the remote worker.

        Forwards the status as an AgentProgressUpdateData signal to the
        gateway/UI via the a2a_context stored when the request was sent.
        """
        log.debug(
            "[SamRemoteExecutor] Status update for %s: %s",
            correlation_id,
            status_text,
        )

        a2a_context = self._pending_a2a_contexts.get(correlation_id)
        if not a2a_context or not self._component:
            return

        from ....common.data_parts import AgentProgressUpdateData

        signal = AgentProgressUpdateData(status_text=status_text)
        self._component.publish_data_signal_from_thread(
            a2a_context=a2a_context,
            signal_data=signal,
        )

    async def request_init(
        self,
        tool_config: Dict[str, Any],
        timeout_seconds: float = 15.0,
    ) -> Optional[SandboxToolInitResponse]:
        """
        Request enriched tool metadata from the remote worker via init protocol.

        Sends an init request and waits for the worker to run the tool's init()
        inside bwrap and return enriched description/schema. Returns None on
        timeout (worker may not be running).

        Args:
            tool_config: Tool configuration to pass to init()
            timeout_seconds: How long to wait for the response

        Returns:
            SandboxToolInitResponse on success/error, or None on timeout
        """
        log_id = f"[SamRemoteExecutor:{self._tool_name}]"

        if not self._component:
            log.warning("%s Cannot request init: executor not initialized", log_id)
            return None

        correlation_id = str(uuid.uuid4())

        try:
            # Build init request
            request = SandboxToolInitRequest(
                id=correlation_id,
                params=SandboxInitParams(
                    tool_name=self._tool_name,
                    tool_config=tool_config,
                ),
            )

            # Build topics — reuse existing response topic for reply routing
            request_topic = get_sam_remote_tool_init_topic(
                self._namespace, self._tool_name
            )
            reply_to = get_sam_remote_tool_response_topic(
                self._namespace, self._agent_name, correlation_id
            )

            user_properties = {
                "replyTo": reply_to,
                "clientId": self._agent_name,
            }

            log.info(
                "%s Sending init request: id=%s, topic=%s",
                log_id,
                correlation_id,
                request_topic,
            )

            # Create future and publish
            response_future = concurrent.futures.Future()
            self._pending_responses[correlation_id] = response_future

            try:
                self._component.publish_a2a_message(
                    payload=request.model_dump(exclude_none=True),
                    topic=request_topic,
                    user_properties=user_properties,
                )

                # Wait for response
                try:
                    asyncio_future = asyncio.wrap_future(response_future)
                    response_payload = await asyncio.wait_for(
                        asyncio_future,
                        timeout=timeout_seconds,
                    )

                    response = SandboxToolInitResponse.model_validate(
                        response_payload
                    )

                    if response.error:
                        log.warning(
                            "%s Init returned error: %s - %s",
                            log_id,
                            response.error.code,
                            response.error.message,
                        )
                    else:
                        log.info(
                            "%s Init succeeded for tool %s",
                            log_id,
                            self._tool_name,
                        )

                    return response

                except asyncio.TimeoutError:
                    log.warning(
                        "%s Init request timed out after %.1fs — worker may "
                        "not be running. Tool will use static description.",
                        log_id,
                        timeout_seconds,
                    )
                    return None

            finally:
                self._pending_responses.pop(correlation_id, None)

        except Exception as e:
            log.warning(
                "%s Init request failed: %s. Tool will use static description.",
                log_id,
                e,
            )
            return None

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Clean up executor resources."""
        log_id = f"[SamRemoteExecutor:{self._tool_name}]"

        # Cancel any pending requests
        for correlation_id, future in self._pending_responses.items():
            if not future.done():
                future.cancel()
                log.debug("%s Cancelled pending request: %s", log_id, correlation_id)

        self._pending_responses.clear()
        self._pending_a2a_contexts.clear()
        self._component = None
        log.info("%s Cleaned up", log_id)
