"""
Sandboxed Python Executor.

This executor delegates tool execution to a sandbox worker running in a
container. It communicates via Solace broker using the A2A protocol patterns.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING, Union

from google.adk.tools import ToolContext

from .base import ToolExecutor, ToolExecutionResult, register_executor
from ..tool_result import ToolResult
from ....common.a2a import (
    get_sandbox_request_topic,
    get_sandbox_response_topic,
    get_sandbox_status_topic,
)
from ....sandbox.protocol import (
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


@register_executor("sandboxed_python")
class SandboxedPythonExecutor(ToolExecutor):
    """
    Executor that runs Python tools in a sandboxed container environment.

    This executor sends tool invocation requests to a sandbox worker via
    Solace broker and waits for the response. It supports:
    - Configurable timeout
    - Status message forwarding during execution
    - Artifact pre-loading and result processing
    - Dev mode fallback to local execution

    Configuration:
        module: The Python module path (e.g., "mypackage.tools.data_tools")
        function: The function name within the module
        sandbox_worker_id: ID of the sandbox worker to route to
        timeout_seconds: Maximum execution time (default: 300)
        sandbox_profile: nsjail profile (restrictive, standard, permissive)
        dev_mode: Skip sandboxing and run locally (default: False)
    """

    def __init__(
        self,
        module: str,
        function: str,
        sandbox_worker_id: str = "sandbox-worker-001",
        timeout_seconds: int = 300,
        sandbox_profile: str = "standard",
        dev_mode: bool = False,
    ):
        """
        Initialize the sandboxed executor.

        Args:
            module: Python module path containing the tool
            function: Name of the function to call
            sandbox_worker_id: ID of the sandbox worker instance
            timeout_seconds: Maximum execution time in seconds
            sandbox_profile: nsjail profile to use
            dev_mode: If True, fall back to local execution
        """
        self._module_path = module
        self._function_name = function
        self._sandbox_worker_id = sandbox_worker_id
        self._timeout_seconds = timeout_seconds
        self._sandbox_profile = sandbox_profile
        self._dev_mode = dev_mode

        # Will be set during initialize()
        self._component: Optional["SamAgentComponent"] = None
        self._namespace: Optional[str] = None
        self._agent_name: Optional[str] = None

        # For dev mode fallback
        self._local_executor: Optional[ToolExecutor] = None

        # Track pending requests
        self._pending_responses: Dict[str, asyncio.Future] = {}

    @property
    def executor_type(self) -> str:
        return "sandboxed_python"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """
        Initialize the executor.

        Sets up the connection to the host component for publishing
        and subscribing to Solace topics.

        Args:
            component: The host SamAgentComponent
            executor_config: Executor-specific configuration
        """
        log_id = f"[SandboxedExecutor:{self._module_path}.{self._function_name}]"
        log.info("%s Initializing...", log_id)

        self._component = component
        self._namespace = component.namespace
        self._agent_name = component.agent_name

        # If dev_mode is enabled, initialize local executor as fallback
        if self._dev_mode:
            log.info("%s Dev mode enabled, setting up local executor fallback", log_id)
            from .python_executor import LocalPythonExecutor

            self._local_executor = LocalPythonExecutor(
                module=self._module_path,
                function=self._function_name,
            )
            await self._local_executor.initialize(component, executor_config)

        log.info(
            "%s Initialized (sandbox_worker=%s, timeout=%ds, dev_mode=%s)",
            log_id,
            self._sandbox_worker_id,
            self._timeout_seconds,
            self._dev_mode,
        )

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> Union[ToolExecutionResult, ToolResult]:
        """
        Execute the tool in the sandbox.

        Sends an invocation request to the sandbox worker via Solace
        and waits for the response.

        Args:
            args: The arguments passed to the tool
            tool_context: The ADK ToolContext for accessing services
            tool_config: Tool-specific configuration

        Returns:
            ToolExecutionResult or ToolResult from the sandboxed execution
        """
        log_id = f"[SandboxedExecutor:{self._module_path}.{self._function_name}]"

        # Dev mode fallback
        if self._dev_mode and self._local_executor:
            log.debug("%s Using local executor (dev mode)", log_id)
            return await self._local_executor.execute(args, tool_context, tool_config)

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
                session_id = getattr(invocation_context, "session_id", "unknown")
            else:
                app_name = self._agent_name
                user_id = "unknown"
                session_id = "unknown"

            # Build the invocation request
            params = SandboxInvokeParams(
                task_id=correlation_id,
                tool_name=f"{self._module_path}.{self._function_name}",
                module=self._module_path,
                function=self._function_name,
                args=args,
                tool_config=tool_config,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                timeout_seconds=self._timeout_seconds,
                sandbox_profile=self._sandbox_profile,
            )

            request = SandboxToolInvocationRequest(
                id=correlation_id,
                params=params,
            )

            # Build topics
            request_topic = get_sandbox_request_topic(
                self._namespace, self._sandbox_worker_id
            )
            reply_to = get_sandbox_response_topic(
                self._namespace, self._agent_name, correlation_id
            )
            status_topic = get_sandbox_status_topic(
                self._namespace, self._agent_name, correlation_id
            )

            # User properties for routing (following A2A patterns)
            user_properties = {
                "replyTo": reply_to,
                "a2aStatusTopic": status_topic,
                "clientId": self._agent_name,
                "userId": user_id,
            }

            log.info(
                "%s Sending request to sandbox worker: id=%s, topic=%s",
                log_id,
                correlation_id,
                request_topic,
            )

            # Create a future for the response
            response_future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending_responses[correlation_id] = response_future

            try:
                # Publish the request
                self._component.publish_a2a_message(
                    payload=request.model_dump(exclude_none=True),
                    topic=request_topic,
                    user_properties=user_properties,
                )

                # Wait for response with timeout
                # Note: In a full implementation, we'd need to subscribe to the
                # response topic and have a callback that resolves the future.
                # For now, this is a placeholder that will timeout.
                try:
                    response_payload = await asyncio.wait_for(
                        response_future,
                        timeout=self._timeout_seconds + 10,  # Buffer for network
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

                        return ToolExecutionResult.ok(
                            data=response.result.tool_result,
                            metadata={
                                "execution_time_ms": response.result.execution_time_ms,
                                "created_artifacts": [
                                    a.model_dump()
                                    for a in response.result.created_artifacts
                                ],
                            },
                        )

                    return ToolExecutionResult.fail(
                        error="Empty response from sandbox worker",
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
                        error=f"No response from sandbox worker within {self._timeout_seconds}s",
                        error_code=SandboxErrorCodes.TIMEOUT,
                        metadata={"execution_time_ms": execution_time_ms},
                    )

            finally:
                # Clean up pending request
                self._pending_responses.pop(correlation_id, None)

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            log.exception("%s Execution failed: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Sandbox execution failed: {str(e)}",
                error_code=SandboxErrorCodes.EXECUTION_ERROR,
                metadata={"execution_time_ms": execution_time_ms},
            )

    def handle_response(self, correlation_id: str, payload: Dict[str, Any]) -> None:
        """
        Handle a response from the sandbox worker.

        This method should be called by the agent component when it receives
        a message on the sandbox response topic.

        Args:
            correlation_id: The correlation ID from the response
            payload: The response payload
        """
        future = self._pending_responses.get(correlation_id)
        if future and not future.done():
            future.set_result(payload)
        else:
            log.warning(
                "[SandboxedExecutor] Received response for unknown or completed "
                "request: correlation_id=%s",
                correlation_id,
            )

    def handle_status(self, correlation_id: str, status_text: str) -> None:
        """
        Handle a status update from the sandbox worker.

        This method should be called by the agent component when it receives
        a status message during tool execution.

        Args:
            correlation_id: The correlation ID (task_id)
            status_text: The status message
        """
        # TODO: Forward status to the appropriate handler
        # This could be used to update UI or send progress to the client
        log.debug(
            "[SandboxedExecutor] Status update for %s: %s",
            correlation_id,
            status_text,
        )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """
        Clean up executor resources.

        Args:
            component: The host SamAgentComponent
            executor_config: Executor-specific configuration
        """
        log_id = f"[SandboxedExecutor:{self._module_path}.{self._function_name}]"

        # Cancel any pending requests
        for correlation_id, future in self._pending_responses.items():
            if not future.done():
                future.cancel()
                log.debug("%s Cancelled pending request: %s", log_id, correlation_id)

        self._pending_responses.clear()

        # Clean up local executor if used
        if self._local_executor:
            await self._local_executor.cleanup(component, executor_config)

        self._component = None
        log.info("%s Cleaned up", log_id)
