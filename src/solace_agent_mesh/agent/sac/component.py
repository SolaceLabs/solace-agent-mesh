"""
Custom Solace AI Connector Component to Host Google ADK Agents via A2A Protocol.
"""

import asyncio
import concurrent.futures
import fnmatch
import functools
import inspect
import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

from litellm.exceptions import BadRequestError

from ...common.error_handlers import get_error_message

from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.types import Artifact as A2AArtifact
from a2a.types import Message as A2AMessage
from google.adk.agents import LlmAgent, RunConfig
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.run_config import StreamingMode
from google.adk.artifacts import BaseArtifactService
from google.adk.auth.credential_service.base_credential_service import (
    BaseCredentialService,
)
from google.adk.events import Event as ADKEvent
from google.adk.memory import BaseMemoryService
from google.adk.models import LlmResponse
from google.adk.models.llm_request import LlmRequest
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.openapi_tool import OpenAPIToolset
from google.genai import types as adk_types
from pydantic import BaseModel, ValidationError
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.common.utils import import_module

from ...agent.adk.runner import TaskCancelledError, run_adk_async_task_thread_wrapper
from ...agent.adk.services import (
    initialize_artifact_service,
    initialize_credential_service,
    initialize_memory_service,
    initialize_session_service,
)
from ...agent.adk.setup import (
    initialize_adk_agent,
    initialize_adk_runner,
    load_adk_tools,
)
from ...agent.protocol.event_handlers import process_event, publish_agent_card
from ...agent.tools.peer_agent_tool import (
    CORRELATION_DATA_PREFIX,
    PEER_TOOL_PREFIX,
    PeerAgentTool,
)
from ...agent.tools.workflow_tool import WorkflowAgentTool
from ...agent.tools.registry import tool_registry
from ...agent.utils.config_parser import resolve_instruction_provider
from ...common import a2a
from ...common.a2a.translation import format_and_route_adk_event
from ...common.agent_registry import AgentRegistry
from ...common.constants import (
    DEFAULT_COMMUNICATION_TIMEOUT,
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_TTL_SECONDS,
    EXTENSION_URI_AGENT_TYPE,
    EXTENSION_URI_SCHEMAS,
)
from ...common.a2a.types import ArtifactInfo
from ...common.data_parts import AgentProgressUpdateData, ArtifactSavedData
from ...common.middleware.registry import MiddlewareRegistry
from ...common.sac.sam_component_base import SamComponentBase
from ...common.utils.rbac_utils import validate_agent_access
from .structured_invocation.handler import StructuredInvocationHandler

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .app import AgentInitCleanupConfig
    from .task_execution_context import TaskExecutionContext

info = {
    "class_name": "SamAgentComponent",
    "description": (
        "Hosts a Google ADK agent and bridges communication via the A2A protocol over Solace. "
        "NOTE: Configuration is defined in the app-level 'app_config' block "
        "and validated by 'SamAgentApp.app_schema' when using the associated App class."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "description": "Not typically used; component reacts to events.",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used; component publishes results to Solace.",
        "properties": {},
    },
}
InstructionProvider = Callable[[ReadonlyContext], str]


class SamAgentComponent(SamComponentBase):
    """
    A Solace AI Connector component that hosts a Google ADK agent,
    communicating via the A2A protocol over Solace.
    """

    CORRELATION_DATA_PREFIX = CORRELATION_DATA_PREFIX
    HOST_COMPONENT_VERSION = "1.0.0-alpha"
    HEALTH_CHECK_TIMER_ID = "agent_health_check"

    def __init__(self, **kwargs):
        """
        Initializes the A2A_ADK_HostComponent.
        Args:
            **kwargs: Configuration parameters passed from the SAC framework.
                      Expects configuration under app_config.
        """
        if "component_config" in kwargs and "app_config" in kwargs["component_config"]:
            name = kwargs["component_config"]["app_config"].get("agent_name")
            if name:
                kwargs.setdefault("name", name)

        super().__init__(info, **kwargs)
        self.agent_name = self.get_config("agent_name")
        log.info(
            "%s Initializing agent: %s (A2A ADK Host Component)...",
            self.log_identifier,
            self.agent_name,
        )

        # Initialize the agent registry for health tracking
        self.agent_registry = AgentRegistry()
        try:
            self.namespace = self.get_config("namespace")
            if not self.namespace:
                raise ValueError("Internal Error: Namespace missing after validation.")
            self.supports_streaming = self.get_config("supports_streaming", False)
            self.stream_batching_threshold_bytes = self.get_config(
                "stream_batching_threshold_bytes", 0
            )
            self.agent_name = self.get_config("agent_name")
            if not self.agent_name:
                raise ValueError("Internal Error: Agent name missing after validation.")
            self.model_config = self.get_config("model")
            if not self.model_config:
                raise ValueError(
                    "Internal Error: Model config missing after validation."
                )
            self.instruction_config = self.get_config("instruction", "")
            self.global_instruction_config = self.get_config("global_instruction", "")
            self.tools_config = self.get_config("tools", [])
            self.planner_config = self.get_config("planner")
            self.code_executor_config = self.get_config("code_executor")
            self.session_service_config = self.get_config("session_service")
            if not self.session_service_config:
                raise ValueError(
                    "Internal Error: Session service config missing after validation."
                )
            self.default_session_behavior = self.session_service_config.get(
                "default_behavior", "PERSISTENT"
            ).upper()
            if self.default_session_behavior not in ["PERSISTENT", "RUN_BASED"]:
                log.warning(
                    "%s Invalid 'default_behavior' in session_service_config: '%s'. Defaulting to PERSISTENT.",
                    self.log_identifier,
                    self.default_session_behavior,
                )
                self.default_session_behavior = "PERSISTENT"
            log.info(
                "%s Default session behavior set to: %s",
                self.log_identifier,
                self.default_session_behavior,
            )
            self.artifact_service_config = self.get_config(
                "artifact_service", {"type": "memory"}
            )
            self.memory_service_config = self.get_config(
                "memory_service", {"type": "memory"}
            )
            self.artifact_handling_mode = self.get_config(
                "artifact_handling_mode", "ignore"
            ).lower()
            if self.artifact_handling_mode not in ["ignore", "embed", "reference"]:
                log.warning(
                    "%s Invalid artifact_handling_mode '%s'. Defaulting to 'ignore'.",
                    self.log_identifier,
                    self.artifact_handling_mode,
                )
                self.artifact_handling_mode = "ignore"
            log.info(
                "%s Artifact Handling Mode: %s",
                self.log_identifier,
                self.artifact_handling_mode,
            )
            if self.artifact_handling_mode == "reference":
                log.warning(
                    "%s Artifact handling mode 'reference' selected, but this component does not currently host an endpoint to serve artifacts. Clients may not be able to retrieve referenced artifacts.",
                    self.log_identifier,
                )
            self.agent_card_config = self.get_config("agent_card")
            if not self.agent_card_config:
                raise ValueError(
                    "Internal Error: Agent card config missing after validation."
                )
            self.agent_card_publishing_config = self.get_config("agent_card_publishing")
            if not self.agent_card_publishing_config:
                raise ValueError(
                    "Internal Error: Agent card publishing config missing after validation."
                )
            self.agent_discovery_config = self.get_config("agent_discovery")
            if not self.agent_discovery_config:
                raise ValueError(
                    "Internal Error: Agent discovery config missing after validation."
                )
            self.inter_agent_communication_config = self.get_config(
                "inter_agent_communication"
            )
            if not self.inter_agent_communication_config:
                raise ValueError(
                    "Internal Error: Inter-agent comms config missing after validation."
                )

            self.max_message_size_bytes = self.get_config(
                "max_message_size_bytes", 10_000_000
            )

        except Exception as e:
            log.error(
                "%s Failed to retrieve configuration via get_config: %s",
                self.log_identifier,
                e,
            )
            raise ValueError(f"Configuration retrieval error: {e}") from e
        self.session_service: BaseSessionService = None
        self.artifact_service: BaseArtifactService = None
        self.memory_service: BaseMemoryService = None
        self.credential_service: Optional[BaseCredentialService] = None
        self.adk_agent: LlmAgent = None
        self.runner: Runner = None
        self.agent_card_tool_manifest: List[Dict[str, Any]] = []
        self.peer_agents: Dict[str, Any] = {}  # Keep for backward compatibility
        self._card_publish_timer_id: str = f"publish_card_{self.agent_name}"
        self._async_init_future = None
        self.peer_response_queues: Dict[str, asyncio.Queue] = {}
        self.peer_response_queue_lock = threading.Lock()
        self.agent_specific_state: Dict[str, Any] = {}
        self.active_tasks: Dict[str, "TaskExecutionContext"] = {}
        self.active_tasks_lock = threading.Lock()
        self._tool_cleanup_hooks: List[Callable] = []
        self._agent_system_instruction_string: Optional[str] = None
        self._agent_system_instruction_callback: Optional[
            Callable[[CallbackContext, LlmRequest], Optional[str]]
        ] = None
        self._active_background_tasks = set()

        # Initialize structured invocation support
        self.structured_invocation_handler = StructuredInvocationHandler(self)

        try:
            self.agent_specific_state: Dict[str, Any] = {}
            init_func_details = self.get_config("agent_init_function")

            try:
                log.info(
                    "%s Initializing synchronous ADK services...", self.log_identifier
                )
                self.session_service = initialize_session_service(self)
                self.artifact_service = initialize_artifact_service(self)
                self.memory_service = initialize_memory_service(self)
                self.credential_service = initialize_credential_service(self)

                log.info(
                    "%s Initialized Synchronous ADK services.", self.log_identifier
                )
            except Exception as service_err:
                log.exception(
                    "%s Failed to initialize synchronous ADK services: %s",
                    self.log_identifier,
                    service_err,
                )
                raise RuntimeError(
                    f"Failed to initialize synchronous ADK services: {service_err}"
                ) from service_err

            # initialize enterprise features if available
            try:
                from solace_agent_mesh_enterprise.init_enterprise_component import (
                    init_enterprise_component_features,
                )

                init_enterprise_component_features(self)
            except ImportError:
                # Community edition
                # Contact Solace support for enterprise features
                pass

            from .app import (
                AgentInitCleanupConfig,
            )  # delayed import to avoid circular dependency

            if init_func_details and isinstance(
                init_func_details, AgentInitCleanupConfig
            ):
                module_name = init_func_details.get("module")
                func_name = init_func_details.get("name")
                base_path = init_func_details.get("base_path")
                specific_init_params_dict = init_func_details.get("config", {})
                if module_name and func_name:
                    log.info(
                        "%s Attempting to load init_function: %s.%s",
                        self.log_identifier,
                        module_name,
                        func_name,
                    )
                    try:
                        module = import_module(module_name, base_path=base_path)
                        init_function = getattr(module, func_name)
                        if not callable(init_function):
                            raise TypeError(
                                f"Init function '{func_name}' in module '{module_name}' is not callable."
                            )
                        sig = inspect.signature(init_function)
                        pydantic_config_model = None
                        config_param_name = None
                        validated_config_arg = specific_init_params_dict
                        for param_name_sig, param_sig in sig.parameters.items():
                            if (
                                param_sig.annotation is not inspect.Parameter.empty
                                and isinstance(param_sig.annotation, type)
                                and issubclass(param_sig.annotation, BaseModel)
                            ):
                                pydantic_config_model = param_sig.annotation
                                config_param_name = param_name_sig
                                break
                        if pydantic_config_model and config_param_name:
                            log.info(
                                "%s Found Pydantic config model '%s' for init_function parameter '%s'.",
                                self.log_identifier,
                                pydantic_config_model.__name__,
                                config_param_name,
                            )
                            try:
                                validated_config_arg = pydantic_config_model(
                                    **specific_init_params_dict
                                )
                            except ValidationError as ve:
                                log.error(
                                    "%s Validation error for init_function config using Pydantic model '%s': %s",
                                    self.log_identifier,
                                    pydantic_config_model.__name__,
                                    ve,
                                )
                                raise ValueError(
                                    f"Invalid configuration for init_function '{func_name}': {ve}"
                                ) from ve
                        elif (
                            config_param_name
                            and param_sig.annotation is not inspect.Parameter.empty
                        ):
                            log.warning(
                                "%s Config parameter '%s' for init_function '%s' has a type hint '%s', but it's not a Pydantic BaseModel. Passing raw dict.",
                                self.log_identifier,
                                config_param_name,
                                func_name,
                                param_sig.annotation,
                            )
                        else:
                            log.info(
                                "%s No Pydantic model type hint found for a config parameter of init_function '%s'. Passing raw dict if a config param exists, or only host_component.",
                                self.log_identifier,
                                func_name,
                            )
                        func_params_list = list(sig.parameters.values())
                        num_actual_params = len(func_params_list)
                        if num_actual_params == 1:
                            if specific_init_params_dict:
                                log.warning(
                                    "%s Init function '%s' takes 1 argument, but 'config' was provided in YAML. Config will be ignored.",
                                    self.log_identifier,
                                    func_name,
                                )
                            init_function(self)
                        elif num_actual_params == 2:
                            actual_config_param_name_in_signature = func_params_list[
                                1
                            ].name
                            init_function(
                                self,
                                **{
                                    actual_config_param_name_in_signature: validated_config_arg
                                },
                            )
                        else:
                            raise TypeError(
                                f"Init function '{func_name}' has an unsupported signature. "
                                f"Expected (host_component_instance) or (host_component_instance, config_param), "
                                f"but got {num_actual_params} parameters."
                            )
                        log.info(
                            "%s Successfully executed init_function: %s.%s",
                            self.log_identifier,
                            module_name,
                            func_name,
                        )
                    except Exception as e:
                        log.exception(
                            "%s Fatal error during agent initialization via init_function '%s.%s': %s",
                            self.log_identifier,
                            module_name,
                            func_name,
                            e,
                        )
                        raise RuntimeError(
                            f"Agent custom initialization failed: {e}"
                        ) from e

            # Async init is now handled by the base class `run` method.
            # We still need a future to signal completion from the async thread.
            self._async_init_future = concurrent.futures.Future()

            # Set up health check timer if enabled
            health_check_interval_seconds = self.agent_discovery_config.get(
                "health_check_interval_seconds", HEALTH_CHECK_INTERVAL_SECONDS
            )
            if health_check_interval_seconds > 0:
                log.info(
                    "%s Scheduling agent health check every %d seconds.",
                    self.log_identifier,
                    health_check_interval_seconds,
                )
                self.add_timer(
                    delay_ms=health_check_interval_seconds * 1000,
                    timer_id=self.HEALTH_CHECK_TIMER_ID,
                    interval_ms=health_check_interval_seconds * 1000,
                    callback=lambda timer_data: self._check_agent_health(),
                )
            else:
                log.warning(
                    "%s Agent health check interval not configured or invalid, health checks will not run periodically.",
                    self.log_identifier,
                )

            log.info(
                "%s Initialized agent: %s",
                self.log_identifier,
                self.agent_name,
            )
        except Exception as e:
            log.exception("%s Initialization failed: %s", self.log_identifier, e)
            raise

    def _get_component_id(self) -> str:
        """Returns the agent name as the component identifier."""
        return self.agent_name

    def _get_component_type(self) -> str:
        """Returns 'agent' as the component type."""
        return "agent"

    def invoke(self, message: SolaceMessage, data: dict) -> dict:
        """Placeholder invoke method. Primary logic resides in _handle_message."""
        log.warning(
            "%s 'invoke' method called, but primary logic resides in '_handle_message'. This should not happen in normal operation.",
            self.log_identifier,
        )
        return None

    async def _handle_message_async(self, message: SolaceMessage, topic: str) -> None:
        """
        Async handler for incoming messages.

        Routes the message to the async event handler.

        Args:
            message: The Solace message
            topic: The topic the message was received on
        """
        # Create event and process asynchronously
        event = Event(EventType.MESSAGE, message)
        await process_event(self, event)

    def handle_timer_event(self, timer_data: Dict[str, Any]):
        """Handles timer events for agent card publishing and health checks."""
        log.debug("%s Received timer event: %s", self.log_identifier, timer_data)
        timer_id = timer_data.get("timer_id")

        if timer_id == self._card_publish_timer_id:
            publish_agent_card(self)
        elif timer_id == self.HEALTH_CHECK_TIMER_ID:
            self._check_agent_health()

    async def handle_cache_expiry_event(self, cache_data: Dict[str, Any]):
        """
        Handles cache expiry events for peer timeouts by calling the atomic claim helper.
        """
        log.debug("%s Received cache expiry event: %s", self.log_identifier, cache_data)
        sub_task_id = cache_data.get("key")
        logical_task_id = cache_data.get("expired_data")

        if not (
            sub_task_id
            and sub_task_id.startswith(CORRELATION_DATA_PREFIX)
            and logical_task_id
        ):
            log.debug(
                "%s Cache expiry for key '%s' is not a peer sub-task timeout or is missing data.",
                self.log_identifier,
                sub_task_id,
            )
            return

        correlation_data = await self._claim_peer_sub_task_completion(
            sub_task_id=sub_task_id, logical_task_id_from_event=logical_task_id
        )

        if correlation_data:
            log.warning(
                "%s Detected timeout for sub-task %s (Main Task: %s). Claimed successfully.",
                self.log_identifier,
                sub_task_id,
                logical_task_id,
            )
            await self._handle_peer_timeout(sub_task_id, correlation_data)
        else:
            log.info(
                "%s Ignoring timeout event for sub-task %s as it was already completed.",
                self.log_identifier,
                sub_task_id,
            )

    async def get_main_task_context(
        self, logical_task_id: str
    ) -> Optional["TaskExecutionContext"]:
        """
        Retrieves the main task context for a given logical task ID.

        This method is used when the current agent is the target agent for the task.
        It returns the TaskExecutionContext which contains the full task state including
        a2a_context, active_peer_sub_tasks, and other task execution details.

        Args:
            logical_task_id: The unique logical ID of the task

        Returns:
            The TaskExecutionContext if the task is active, None otherwise

        Raises:
            ValueError: If logical_task_id is None or empty
        """
        if not logical_task_id:
            raise ValueError("logical_task_id cannot be None or empty")

        with self.active_tasks_lock:
            active_task_context = self.active_tasks.get(logical_task_id)
            if active_task_context is None:
                log.warning(
                    f"No active task context found for logical_task_id: {logical_task_id}"
                )
                return None

            return active_task_context

    async def get_all_sub_task_correlation_data_from_logical_task_id(
        self, logical_task_id: str
    ) -> list[dict[str, Any]]:
        """
        Retrieves correlation data for all active peer sub-tasks of a given logical task.

        This method is used when forwarding requests to other agents in an A2A workflow.
        It returns a list of correlation data dictionaries, each containing information
        about a peer sub-task including peer_task_id, peer_agent_name, and original_task_context.

        Args:
            logical_task_id: The unique logical ID of the parent task

        Returns:
            List of correlation data dictionaries for active peer sub-tasks.
            Returns empty list if no active peer sub-tasks exist.

        Raises:
            ValueError: If logical_task_id is None or empty
        """
        if not logical_task_id:
            raise ValueError("logical_task_id cannot be None or empty")

        with self.active_tasks_lock:
            active_task_context = self.active_tasks.get(logical_task_id)
            if active_task_context is None:
                log.warning(
                    f"No active task context found for logical_task_id: {logical_task_id}"
                )
                return []

            active_peer_sub_tasks = active_task_context.active_peer_sub_tasks
            if not active_peer_sub_tasks:
                log.debug(
                    f"No active peer sub-tasks found for logical_task_id: {logical_task_id}"
                )
                return []

            results = []
            for sub_task_id, correlation_data in active_peer_sub_tasks.items():
                if sub_task_id is not None and correlation_data is not None:
                    results.append(correlation_data)

            return results

    async def _get_correlation_data_for_sub_task(
        self, sub_task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Non-destructively retrieves correlation data for a sub-task.
        Used for intermediate events where the sub-task should remain active.
        """
        logical_task_id = self.cache_service.get_data(sub_task_id)
        if not logical_task_id:
            log.warning(
                "%s No cache entry for sub-task %s. Cannot get correlation data.",
                self.log_identifier,
                sub_task_id,
            )
            return None

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.error(
                "%s TaskExecutionContext not found for task %s, but cache entry existed for sub-task %s. This may indicate a cleanup issue.",
                self.log_identifier,
                logical_task_id,
                sub_task_id,
            )
            return None

        with task_context.lock:
            return task_context.active_peer_sub_tasks.get(sub_task_id)

    async def _claim_peer_sub_task_completion(
        self, sub_task_id: str, logical_task_id_from_event: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically claims a sub-task as complete, preventing race conditions.
        This is a destructive operation that removes state.

        Args:
            sub_task_id: The ID of the sub-task to claim.
            logical_task_id_from_event: The parent task ID, if provided by the event (e.g., a timeout).
                                        If not provided, it will be looked up from the cache.
        """
        log_id = f"{self.log_identifier}[ClaimSubTask:{sub_task_id}]"
        logical_task_id = logical_task_id_from_event

        if not logical_task_id:
            logical_task_id = self.cache_service.get_data(sub_task_id)
            if not logical_task_id:
                log.warning(
                    "%s No cache entry found. Task has likely timed out and been cleaned up. Cannot claim.",
                    log_id,
                )
                return None

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.error(
                "%s TaskExecutionContext not found for task %s. Cleaning up stale cache entry.",
                log_id,
                logical_task_id,
            )
            self.cache_service.remove_data(sub_task_id)
            return None

        correlation_data = task_context.claim_sub_task_completion(sub_task_id)

        if correlation_data:
            # If we successfully claimed the task, remove the timeout tracker from the cache.
            self.cache_service.remove_data(sub_task_id)
            log.info("%s Successfully claimed completion.", log_id)
            return correlation_data
        else:
            # This means the task was already claimed by a competing event (e.g., timeout vs. response).
            log.warning("%s Failed to claim; it was already completed.", log_id)
            return None

    async def reset_peer_timeout(self, sub_task_id: str):
        """
        Resets the timeout for a given peer sub-task.
        """
        log_id = f"{self.log_identifier}[ResetTimeout:{sub_task_id}]"
        log.debug("%s Resetting timeout for peer sub-task.", log_id)

        # Get the original logical task ID from the cache without removing it
        logical_task_id = self.cache_service.get_data(sub_task_id)
        if not logical_task_id:
            log.warning(
                "%s No active task found for sub-task %s. Cannot reset timeout.",
                log_id,
                sub_task_id,
            )
            return

        # Get the configured timeout
        timeout_sec = self.inter_agent_communication_config.get(
            "request_timeout_seconds", DEFAULT_COMMUNICATION_TIMEOUT
        )

        # Update the cache with a new expiry
        self.cache_service.add_data(
            key=sub_task_id,
            value=logical_task_id,
            expiry=timeout_sec,
            component=self,
        )
        log.info(
            "%s Timeout for sub-task %s has been reset to %d seconds.",
            log_id,
            sub_task_id,
            timeout_sec,
        )

    async def _retrigger_agent_with_peer_responses(
        self,
        results_to_inject: list,
        correlation_data: dict,
        task_context: "TaskExecutionContext",
    ):
        """
        Injects peer tool responses into the session history and re-triggers the ADK runner.
        This function contains the logic to correctly merge parallel tool call responses.
        """
        original_task_context = correlation_data.get("original_task_context")
        logical_task_id = correlation_data.get("logical_task_id")
        paused_invocation_id = correlation_data.get("invocation_id")
        log_retrigger = f"{self.log_identifier}[RetriggerManager:{logical_task_id}]"

        # Clear paused state - task is resuming now
        task_context.set_paused(False)
        log.debug(
            "%s Task %s resuming from paused state with peer responses.",
            log_retrigger,
            logical_task_id,
        )

        try:
            effective_session_id = original_task_context.get("effective_session_id")
            user_id = original_task_context.get("user_id")
            session = await self.session_service.get_session(
                app_name=self.agent_name,
                user_id=user_id,
                session_id=effective_session_id,
            )
            if not session:
                raise RuntimeError(
                    f"Could not find ADK session '{effective_session_id}'"
                )

            new_response_parts = []
            for result in results_to_inject:
                part = adk_types.Part.from_function_response(
                    name=result["peer_tool_name"],
                    response=result["payload"],
                )
                part.function_response.id = result["adk_function_call_id"]
                new_response_parts.append(part)

            # Always create a new event for the incoming peer responses.
            # The ADK's `contents` processor is responsible for merging multiple
            # tool responses into a single message before the next LLM call.
            log.info(
                "%s Creating a new tool response event for %d peer responses.",
                log_retrigger,
                len(new_response_parts),
            )
            new_tool_response_content = adk_types.Content(
                role="tool", parts=new_response_parts
            )

            # Always use SSE streaming mode for the ADK runner, even on re-trigger.
            # This ensures that real-time callbacks for status updates and artifact
            # creation can function correctly for all turns of a task.
            streaming_mode = StreamingMode.SSE
            max_llm_calls = self.get_config("max_llm_calls_per_task", 20)
            run_config = RunConfig(
                streaming_mode=streaming_mode, max_llm_calls=max_llm_calls
            )

            log.info(
                "%s Re-triggering ADK runner for main task %s.",
                log_retrigger,
                logical_task_id,
            )
            try:
                await run_adk_async_task_thread_wrapper(
                    self,
                    session,
                    new_tool_response_content,
                    run_config,
                    original_task_context,
                    append_context_event=False,
                )
            finally:
                log.info(
                    "%s Cleaning up parallel invocation state for invocation %s.",
                    log_retrigger,
                    paused_invocation_id,
                )
                task_context.clear_parallel_invocation_state(paused_invocation_id)

        except Exception as e:
            log.exception(
                "%s Failed to re-trigger ADK runner for task %s: %s",
                log_retrigger,
                logical_task_id,
                e,
            )
            if original_task_context:
                loop = self.get_async_loop()
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.finalize_task_error(e, original_task_context), loop
                    )
                else:
                    log.error(
                        "%s Async loop not available. Cannot schedule error finalization for task %s.",
                        log_retrigger,
                        logical_task_id,
                    )

    async def _handle_peer_timeout(
        self,
        sub_task_id: str,
        correlation_data: Dict[str, Any],
    ):
        """
        Handles the timeout of a peer agent task. It sends a cancellation request
        to the peer, updates the local completion counter, and potentially
        re-triggers the runner if all parallel tasks are now complete.
        """
        logical_task_id = correlation_data.get("logical_task_id")
        invocation_id = correlation_data.get("invocation_id")
        log_retrigger = f"{self.log_identifier}[RetriggerManager:{logical_task_id}]"

        log.warning(
            "%s Peer request timed out for sub-task: %s (Invocation: %s)",
            log_retrigger,
            sub_task_id,
            invocation_id,
        )

        # Proactively send a cancellation request to the peer agent.
        peer_agent_name = correlation_data.get("peer_agent_name")
        if peer_agent_name:
            try:
                log.info(
                    "%s Sending CancelTaskRequest to peer '%s' for timed-out sub-task %s.",
                    log_retrigger,
                    peer_agent_name,
                    sub_task_id,
                )
                task_id_for_peer = sub_task_id.replace(CORRELATION_DATA_PREFIX, "", 1)
                cancel_request = a2a.create_cancel_task_request(
                    task_id=task_id_for_peer
                )
                user_props = {"clientId": self.agent_name}
                peer_topic = self._get_agent_request_topic(peer_agent_name)
                self.publish_a2a_message(
                    payload=cancel_request.model_dump(exclude_none=True),
                    topic=peer_topic,
                    user_properties=user_props,
                )
            except Exception as e:
                log.error(
                    "%s Failed to send CancelTaskRequest to peer '%s' for sub-task %s: %s",
                    log_retrigger,
                    peer_agent_name,
                    sub_task_id,
                    e,
                )

        # Process the timeout locally.
        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.warning(
                "%s TaskExecutionContext not found for task %s. Ignoring timeout event.",
                log_retrigger,
                logical_task_id,
            )
            return

        timeout_value = self.inter_agent_communication_config.get(
            "request_timeout_seconds", DEFAULT_COMMUNICATION_TIMEOUT
        )
        all_sub_tasks_completed = task_context.handle_peer_timeout(
            sub_task_id, correlation_data, timeout_value, invocation_id
        )

        if not all_sub_tasks_completed:
            log.info(
                "%s Waiting for more peer responses for invocation %s after timeout of sub-task %s.",
                log_retrigger,
                invocation_id,
                sub_task_id,
            )
            return

        log.info(
            "%s All peer responses/timeouts received for invocation %s. Retriggering agent.",
            log_retrigger,
            invocation_id,
        )
        results_to_inject = task_context.parallel_tool_calls[invocation_id].get(
            "results", []
        )

        await self._retrigger_agent_with_peer_responses(
            results_to_inject, correlation_data, task_context
        )

    def _inject_peer_tools_callback(
        self, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """
        ADK before_model_callback to dynamically add PeerAgentTools to the LLM request
        and generate the corresponding instruction text for the LLM.
        """
        log.debug("%s Running _inject_peer_tools_callback...", self.log_identifier)
        if not self.peer_agents:
            log.debug("%s No peer agents currently discovered.", self.log_identifier)
            return None

        a2a_context = callback_context.state.get("a2a_context", {})
        user_config = (
            a2a_context.get("a2a_user_config", {})
            if isinstance(a2a_context, dict)
            else {}
        )

        inter_agent_config = self.get_config("inter_agent_communication", {})
        allow_list = inter_agent_config.get("allow_list", ["*"])
        deny_list = set(self.get_config("deny_list", []))
        self_name = self.get_config("agent_name")

        peer_tools_to_add = []
        allowed_peer_descriptions = []

        # Sort peer agents alphabetically to ensure consistent tool ordering for prompt caching
        for peer_name, agent_card in sorted(self.peer_agents.items()):
            if not isinstance(agent_card, AgentCard) or peer_name == self_name:
                continue

            is_allowed = any(
                fnmatch.fnmatch(peer_name, p) for p in allow_list
            ) and not any(fnmatch.fnmatch(peer_name, p) for p in deny_list)

            if is_allowed:
                config_resolver = MiddlewareRegistry.get_config_resolver()
                operation_spec = {
                    "operation_type": "peer_delegation",
                    "target_agent": peer_name,
                    "delegation_context": "peer_discovery",
                }
                validation_context = {
                    "discovery_phase": "peer_enumeration",
                    "agent_context": {"component_type": "peer_discovery"},
                }
                validation_result = config_resolver.validate_operation_config(
                    user_config, operation_spec, validation_context
                )
                if not validation_result.get("valid", True):
                    log.debug(
                        "%s Peer agent '%s' filtered out by user configuration.",
                        self.log_identifier,
                        peer_name,
                    )
                    is_allowed = False

            if not is_allowed:
                continue

            try:
                # Determine agent type and schemas
                agent_type = "standard"
                input_schema = None

                if agent_card.capabilities and agent_card.capabilities.extensions:
                    for ext in agent_card.capabilities.extensions:
                        if ext.uri == EXTENSION_URI_AGENT_TYPE:
                            agent_type = ext.params.get("type", "standard")
                        elif ext.uri == EXTENSION_URI_SCHEMAS:
                            input_schema = ext.params.get("input_schema")

                tool_instance = None
                tool_description_line = ""

                if agent_type == "workflow":
                    # Default schema if none provided
                    if not input_schema:
                        input_schema = {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        }

                    tool_instance = WorkflowAgentTool(
                        target_agent_name=peer_name,
                        input_schema=input_schema,
                        host_component=self,
                    )

                    desc = (
                        getattr(agent_card, "description", "No description")
                        or "No description"
                    )
                    tool_description_line = f"- `{tool_instance.name}`: {desc}"

                else:
                    # Standard Peer Agent
                    tool_instance = PeerAgentTool(
                        target_agent_name=peer_name, host_component=self
                    )
                    # Get enhanced description from the tool instance
                    # which includes capabilities, skills, and tools
                    enhanced_desc = tool_instance._build_enhanced_description(
                        agent_card
                    )
                    tool_description_line = f"\n### `peer_{peer_name}`\n{enhanced_desc}"

                if tool_instance.name not in llm_request.tools_dict:
                    peer_tools_to_add.append(tool_instance)
                    allowed_peer_descriptions.append(tool_description_line)

            except Exception as e:
                log.error(
                    "%s Failed to create tool for '%s': %s",
                    self.log_identifier,
                    peer_name,
                    e,
                )

        if allowed_peer_descriptions:
            peer_list_str = "\n".join(allowed_peer_descriptions)
            instruction_text = (
                "## Peer Agent and Workflow Delegation\n\n"
                "You can delegate tasks to other specialized agents or workflows if they are better suited.\n\n"
                "**How to delegate to peer agents:**\n"
                "- Use the `peer_<agent_name>(task_description: str)` tool for delegation\n"
                "- Replace `<agent_name>` with the actual name of the target agent\n"
                "- Provide a clear and detailed `task_description` for the peer agent\n"
                "- **Important:** The peer agent does not have access to your session history, "
                "so you must provide all required context necessary to fulfill the request\n\n"
                "**How to delegate to workflows:**\n"
                "- Use the `workflow_<agent_name>` tool for workflow delegation\n"
                "- Follow the specific parameter requirements defined in the tool schema\n"
                "- Workflows also do not have access to your session history\n\n"
                "IMPORTANT: When a peer agent's response contains citation markers like [[cite:search0]], [[cite:file1]], etc., "
                "you MUST preserve these markers in your response to the user. These markers link to source references and are "
                "essential for proper attribution. Include them exactly as they appear in the peer's response. DO NOT repeat them without markers.\n\n"
                "## Available Peer Agents and Workflows\n"
                f"{peer_list_str}"
            )
            callback_context.state["peer_tool_instructions"] = instruction_text
            log.debug(
                "%s Stored peer tool instructions in callback_context.state.",
                self.log_identifier,
            )

        if peer_tools_to_add:
            try:
                if llm_request.config.tools is None:
                    llm_request.config.tools = []
                if len(llm_request.config.tools) > 0:
                    for tool in peer_tools_to_add:
                        llm_request.tools_dict[tool.name] = tool
                        declaration = tool._get_declaration()
                        llm_request.config.tools[0].function_declarations.append(
                            declaration
                        )
                else:
                    llm_request.append_tools(peer_tools_to_add)
                log.debug(
                    "%s Dynamically added %d PeerAgentTool(s) to LLM request.",
                    self.log_identifier,
                    len(peer_tools_to_add),
                )
            except Exception as e:
                log.error(
                    "%s Failed to append dynamic peer tools to LLM request: %s",
                    self.log_identifier,
                    e,
                    exc_info=True,
                )
        return None

    def _filter_tools_by_capability_callback(
        self, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """
        ADK before_model_callback to filter tools in the LlmRequest based on user configuration.
        This callback modifies `llm_request.config.tools` in place by potentially
        removing individual FunctionDeclarations from genai.Tool objects or removing
        entire genai.Tool objects if all their declarations are filtered out.
        """
        log_id_prefix = f"{self.log_identifier}[ToolCapabilityFilter]"
        log.debug("%s Running _filter_tools_by_capability_callback...", log_id_prefix)

        a2a_context = callback_context.state.get("a2a_context", {})
        if not isinstance(a2a_context, dict):
            log.warning(
                "%s 'a2a_context' in session state is not a dictionary. Using empty configuration.",
                log_id_prefix,
            )
            a2a_context = {}
        user_config = a2a_context.get("a2a_user_config", {})
        if not isinstance(user_config, dict):
            log.warning(
                "%s 'a2a_user_config' in a2a_context is not a dictionary. Using empty configuration.",
                log_id_prefix,
            )
            user_config = {}

        log.debug(
            "%s User configuration for filtering: %s",
            log_id_prefix,
            {k: v for k, v in user_config.items() if not k.startswith("_")},
        )

        config_resolver = MiddlewareRegistry.get_config_resolver()

        if not llm_request.config or not llm_request.config.tools:
            log.debug("%s No tools in request to filter.", log_id_prefix)
            return None

        explicit_tools_config = self.get_config("tools", [])
        final_filtered_genai_tools: List[adk_types.Tool] = []
        original_genai_tools_count = len(llm_request.config.tools)
        original_function_declarations_count = 0

        for original_tool in llm_request.config.tools:
            if not original_tool.function_declarations:
                log.warning(
                    "%s genai.Tool object has no function declarations. Keeping it.",
                    log_id_prefix,
                )
                final_filtered_genai_tools.append(original_tool)
                continue

            original_function_declarations_count += len(
                original_tool.function_declarations
            )
            permitted_declarations_for_this_tool: List[
                adk_types.FunctionDeclaration
            ] = []

            for func_decl in original_tool.function_declarations:
                func_decl_name = func_decl.name
                tool_object = llm_request.tools_dict.get(func_decl_name)
                origin = SamAgentComponent._extract_tool_origin(tool_object)

                feature_descriptor = {
                    "feature_type": "tool_function",
                    "function_name": func_decl_name,
                    "tool_source": origin,
                    "tool_metadata": {"function_name": func_decl_name},
                }

                if origin == "peer_agent":
                    peer_name = func_decl_name.replace(PEER_TOOL_PREFIX, "", 1)
                    feature_descriptor["tool_metadata"]["peer_agent_name"] = peer_name
                elif origin == "builtin":
                    tool_def = tool_registry.get_tool_by_name(func_decl_name)
                    if tool_def:
                        feature_descriptor["tool_metadata"][
                            "tool_category"
                        ] = tool_def.category
                        feature_descriptor["tool_metadata"][
                            "required_scopes"
                        ] = tool_def.required_scopes
                elif origin in ["python", "mcp", "adk_builtin"]:
                    # Find the explicit config for this tool to pass to the resolver
                    for tool_cfg in explicit_tools_config:
                        cfg_tool_type = tool_cfg.get("tool_type")
                        cfg_tool_name = tool_cfg.get("tool_name")
                        cfg_func_name = tool_cfg.get("function_name")
                        if (
                            cfg_tool_type == "python"
                            and cfg_func_name == func_decl_name
                        ) or (
                            cfg_tool_type in ["builtin", "mcp"]
                            and cfg_tool_name == func_decl_name
                        ):
                            feature_descriptor["tool_metadata"][
                                "tool_config"
                            ] = tool_cfg
                            break

                context = {
                    "agent_context": self.get_agent_context(),
                    "filter_phase": "pre_llm",
                    "tool_configurations": {
                        "explicit_tools": explicit_tools_config,
                    },
                }

                if config_resolver.is_feature_enabled(
                    user_config, feature_descriptor, context
                ):
                    permitted_declarations_for_this_tool.append(func_decl)
                    log.debug(
                        "%s FunctionDeclaration '%s' (Source: %s) permitted.",
                        log_id_prefix,
                        func_decl_name,
                        origin,
                    )
                else:
                    log.info(
                        "%s FunctionDeclaration '%s' (Source: %s) FILTERED OUT due to configuration restrictions.",
                        log_id_prefix,
                        func_decl_name,
                        origin,
                    )

            if permitted_declarations_for_this_tool:
                scoped_tool = original_tool.model_copy(deep=True)
                scoped_tool.function_declarations = permitted_declarations_for_this_tool

                final_filtered_genai_tools.append(scoped_tool)
                log.debug(
                    "%s Keeping genai.Tool as it has %d permitted FunctionDeclaration(s).",
                    log_id_prefix,
                    len(permitted_declarations_for_this_tool),
                )
            else:
                log.info(
                    "%s Entire genai.Tool (original declarations: %s) FILTERED OUT as all its FunctionDeclarations were denied by configuration.",
                    log_id_prefix,
                    [fd.name for fd in original_tool.function_declarations],
                )

        final_function_declarations_count = sum(
            len(t.function_declarations)
            for t in final_filtered_genai_tools
            if t.function_declarations
        )

        if final_function_declarations_count != original_function_declarations_count:
            log.info(
                "%s Tool list modified by capability filter. Original genai.Tools: %d (Total Declarations: %d). Filtered genai.Tools: %d (Total Declarations: %d).",
                log_id_prefix,
                original_genai_tools_count,
                original_function_declarations_count,
                len(final_filtered_genai_tools),
                final_function_declarations_count,
            )
            llm_request.config.tools = (
                final_filtered_genai_tools if final_filtered_genai_tools else None
            )
        else:
            log.debug(
                "%s Tool list and FunctionDeclarations unchanged after capability filtering.",
                log_id_prefix,
            )

        return None

    @staticmethod
    def _extract_tool_origin(tool) -> str:
        """
        Helper method to extract the origin of a tool from various possible attributes.
        """
        if hasattr(tool, "origin") and tool.origin is not None:
            return tool.origin
        elif (
            hasattr(tool, "func")
            and hasattr(tool.func, "origin")
            and tool.func.origin is not None
        ):
            return tool.func.origin
        else:
            return getattr(tool, "origin", "unknown")

    def get_agent_context(self) -> Dict[str, Any]:
        """Get agent context for middleware calls."""
        return {
            "agent_name": getattr(self, "agent_name", "unknown"),
            "component_type": "sac_agent",
        }

    def _inject_gateway_instructions_callback(
        self, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """
        ADK before_model_callback to dynamically prepend gateway-defined system_purpose
        and response_format to the agent's llm_request.config.system_instruction.
        """
        log_id_prefix = f"{self.log_identifier}[GatewayInstrInject]"
        log.debug(
            "%s Running _inject_gateway_instructions_callback to modify system_instruction...",
            log_id_prefix,
        )

        a2a_context = callback_context.state.get("a2a_context", {})
        if not isinstance(a2a_context, dict):
            log.warning(
                "%s 'a2a_context' in session state is not a dictionary. Skipping instruction injection.",
                log_id_prefix,
            )
            return None

        system_purpose = a2a_context.get("system_purpose")
        response_format = a2a_context.get("response_format")
        user_profile = a2a_context.get("a2a_user_config", {}).get("user_profile")

        inject_purpose = self.get_config("inject_system_purpose", False)
        inject_format = self.get_config("inject_response_format", False)
        inject_user_profile = self.get_config("inject_user_profile", False)

        gateway_instructions_to_add = []

        if (
            inject_purpose
            and system_purpose
            and isinstance(system_purpose, str)
            and system_purpose.strip()
        ):
            gateway_instructions_to_add.append(
                f"System Purpose:\n{system_purpose.strip()}"
            )
            log.debug(
                "%s Prepared system_purpose for system_instruction.", log_id_prefix
            )

        if (
            inject_format
            and response_format
            and isinstance(response_format, str)
            and response_format.strip()
        ):
            gateway_instructions_to_add.append(
                f"Desired Response Format:\n{response_format.strip()}"
            )
            log.debug(
                "%s Prepared response_format for system_instruction.", log_id_prefix
            )

        if (
            inject_user_profile
            and user_profile
            and (isinstance(user_profile, str) or isinstance(user_profile, dict))
        ):
            if isinstance(user_profile, dict):
                user_profile = json.dumps(user_profile, indent=2, default=str)
            gateway_instructions_to_add.append(
                f"Inquiring User Profile:\n{user_profile.strip()}\n"
            )
            log.debug("%s Prepared user_profile for system_instruction.", log_id_prefix)

        if not gateway_instructions_to_add:
            log.debug(
                "%s No gateway instructions to inject into system_instruction.",
                log_id_prefix,
            )
            return None

        if llm_request.config is None:
            log.warning(
                "%s llm_request.config is None, cannot append gateway instructions to system_instruction.",
                log_id_prefix,
            )
            return None

        if llm_request.config.system_instruction is None:
            llm_request.config.system_instruction = ""

        combined_new_instructions = "\n\n".join(gateway_instructions_to_add)

        if llm_request.config.system_instruction:
            llm_request.config.system_instruction += (
                f"\n\n---\n\n{combined_new_instructions}"
            )
        else:
            llm_request.config.system_instruction = combined_new_instructions

        log.info(
            "%s Injected %d gateway instruction block(s) into llm_request.config.system_instruction.",
            log_id_prefix,
            len(gateway_instructions_to_add),
        )

        return None

    async def _publish_text_as_partial_a2a_status_update(
        self,
        text_content: str,
        a2a_context: Dict,
        is_stream_terminating_content: bool = False,
    ):
        """
        Constructs and publishes a TaskStatusUpdateEvent for the given text.
        The 'final' flag is determined by is_stream_terminating_content.
        This method skips buffer flushing since it's used for LLM streaming text.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_identifier_helper = (
            f"{self.log_identifier}[PublishPartialText:{logical_task_id}]"
        )

        if not text_content:
            log.debug(
                "%s No text content to publish as update (final=%s).",
                log_identifier_helper,
                is_stream_terminating_content,
            )
            return

        try:
            a2a_message = a2a.create_agent_text_message(
                text=text_content,
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
            )
            event_metadata = {"agent_name": self.agent_name}
            status_update_event = a2a.create_status_update(
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
                message=a2a_message,
                is_final=is_stream_terminating_content,
                metadata=event_metadata,
            )

            await self._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=True,
            )

            log.debug(
                "%s Published LLM streaming text (length: %d bytes, final: %s).",
                log_identifier_helper,
                len(text_content.encode("utf-8")),
                is_stream_terminating_content,
            )

        except Exception as e:
            log.exception(
                "%s Error in _publish_text_as_partial_a2a_status_update: %s",
                log_identifier_helper,
                e,
            )

    async def _publish_agent_status_signal_update(
        self, status_text: str, a2a_context: Dict
    ):
        """
        Constructs and publishes a TaskStatusUpdateEvent specifically for agent_status_message signals.
        This method will flush the buffer before publishing to maintain proper message ordering.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_identifier_helper = (
            f"{self.log_identifier}[PublishAgentSignal:{logical_task_id}]"
        )

        if not status_text:
            log.debug(
                "%s No text content for agent status signal.", log_identifier_helper
            )
            return

        try:
            progress_data = AgentProgressUpdateData(status_text=status_text)
            status_update_event = a2a.create_data_signal_event(
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
                signal_data=progress_data,
                agent_name=self.agent_name,
                part_metadata={"source_embed_type": "status_update"},
            )

            await self._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=False,
            )

            log.debug(
                "%s Published agent_status_message signal ('%s').",
                log_identifier_helper,
                status_text,
            )

        except Exception as e:
            log.exception(
                "%s Error in _publish_agent_status_signal_update: %s",
                log_identifier_helper,
                e,
            )

    async def _flush_buffer_if_needed(
        self, a2a_context: Dict, reason: str = "status_update"
    ) -> bool:
        """
        Flushes streaming buffer if it contains content.

        Args:
            a2a_context: The A2A context dictionary for the current task
            reason: The reason for flushing (for logging purposes)

        Returns:
            bool: True if buffer was flushed, False if no content to flush
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_identifier = f"{self.log_identifier}[BufferFlush:{logical_task_id}]"

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.warning(
                "%s TaskExecutionContext not found for task %s. Cannot flush buffer.",
                log_identifier,
                logical_task_id,
            )
            return False

        buffer_content = task_context.get_streaming_buffer_content()
        if not buffer_content:
            log.debug(
                "%s No buffer content to flush (reason: %s).",
                log_identifier,
                reason,
            )
            return False

        buffer_size = len(buffer_content.encode("utf-8"))
        log.info(
            "%s Flushing buffer content (size: %d bytes, reason: %s).",
            log_identifier,
            buffer_size,
            reason,
        )

        try:
            resolved_text, unprocessed_tail = await self._flush_and_resolve_buffer(
                a2a_context, is_final=False
            )

            if resolved_text:
                await self._publish_text_as_partial_a2a_status_update(
                    resolved_text,
                    a2a_context,
                    is_stream_terminating_content=False,
                )
                log.debug(
                    "%s Successfully flushed and published buffer content (resolved: %d bytes).",
                    log_identifier,
                    len(resolved_text.encode("utf-8")),
                )
                return True
            else:
                log.debug(
                    "%s Buffer flush completed but no resolved text to publish.",
                    log_identifier,
                )
                return False

        except Exception as e:
            log.exception(
                "%s Error during buffer flush (reason: %s): %s",
                log_identifier,
                reason,
                e,
            )
            return False

    async def notify_artifact_saved(
        self,
        artifact_info: ArtifactInfo,
        a2a_context: Dict[str, Any],
        function_call_id: Optional[str] = None,
    ) -> None:
        """
        Publishes an artifact saved notification signal.

        This is a separate event from ArtifactCreationProgressData and does not
        follow the start->updates->end protocol. It's a single notification that
        an artifact has been successfully saved to storage.

        Args:
            artifact_info: Information about the saved artifact
            a2a_context: The A2A context dictionary for the current task
            function_call_id: Optional function call ID if artifact was created by a tool
        """
        log_identifier = (
            f"{self.log_identifier}[ArtifactSaved:{artifact_info.filename}]"
        )

        try:
            # Create artifact saved signal
            artifact_signal = ArtifactSavedData(
                type="artifact_saved",
                filename=artifact_info.filename,
                version=artifact_info.version,
                mime_type=artifact_info.mime_type or "application/octet-stream",
                size_bytes=artifact_info.size,
                description=artifact_info.description,
                function_call_id=function_call_id,
            )

            # Create and publish status update event
            logical_task_id = a2a_context.get("logical_task_id")
            context_id = a2a_context.get("contextId")

            status_update_event = a2a.create_data_signal_event(
                task_id=logical_task_id,
                context_id=context_id,
                signal_data=artifact_signal,
                agent_name=self.agent_name,
            )

            await self._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=False,
            )

            log.debug(
                "%s Published artifact saved notification for '%s' v%s.",
                log_identifier,
                artifact_info.filename,
                artifact_info.version,
            )
        except Exception as e:
            log.error(
                "%s Failed to publish artifact saved notification: %s",
                log_identifier,
                e,
            )

    async def _publish_status_update_with_buffer_flush(
        self,
        status_update_event: TaskStatusUpdateEvent,
        a2a_context: Dict,
        skip_buffer_flush: bool = False,
    ) -> None:
        """
        Central method for publishing status updates with automatic buffer flushing.

        Args:
            status_update_event: The status update event to publish
            a2a_context: The A2A context dictionary for the current task
            skip_buffer_flush: If True, skip buffer flushing (used for LLM streaming text)
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
        log_identifier = f"{self.log_identifier}[StatusUpdate:{logical_task_id}]"

        status_type = "unknown"
        if status_update_event.metadata:
            if status_update_event.metadata.get("type") == "tool_invocation_start":
                status_type = "tool_invocation_start"
            elif "agent_name" in status_update_event.metadata:
                status_type = "agent_status"

        if (
            status_update_event.status
            and status_update_event.status.message
            and status_update_event.status.message.parts
        ):
            for part in status_update_event.status.message.parts:
                if hasattr(part, "data") and part.data:
                    if part.data.get("a2a_signal_type") == "agent_status_message":
                        status_type = "agent_status_signal"
                        break
                    elif "tool_error" in part.data:
                        status_type = "tool_failure"
                        break

        log.debug(
            "%s Publishing status update (type: %s, skip_buffer_flush: %s).",
            log_identifier,
            status_type,
            skip_buffer_flush,
        )

        if not skip_buffer_flush:
            buffer_was_flushed = await self._flush_buffer_if_needed(
                a2a_context, reason=f"before_{status_type}_status"
            )
            if buffer_was_flushed:
                log.info(
                    "%s Buffer flushed before %s status update.",
                    log_identifier,
                    status_type,
                )

        try:
            rpc_response = a2a.create_success_response(
                result=status_update_event, request_id=jsonrpc_request_id
            )
            payload_to_publish = rpc_response.model_dump(exclude_none=True)

            target_topic = a2a_context.get(
                "statusTopic"
            ) or a2a.get_gateway_status_topic(
                self.namespace, self.get_gateway_id(), logical_task_id
            )

            # Construct user_properties to ensure ownership can be determined by gateways
            user_properties = {
                "a2aUserConfig": a2a_context.get("a2a_user_config"),
                "clientId": a2a_context.get("client_id"),
                "delegating_agent_name": self.get_config("agent_name"),
            }

            self._publish_a2a_event(
                payload_to_publish, target_topic, a2a_context, user_properties
            )

            log.debug(
                "%s Published %s status update to %s.",
                log_identifier,
                status_type,
                target_topic,
            )

        except Exception as e:
            log.exception(
                "%s Error publishing %s status update: %s",
                log_identifier,
                status_type,
                e,
            )
            raise

    async def _filter_text_from_final_streaming_event(
        self, adk_event: ADKEvent, a2a_context: Dict
    ) -> ADKEvent:
        """
        Filters out text parts from the final ADKEvent of a turn for PERSISTENT streaming sessions.
        This prevents sending redundant, aggregated text that was already streamed.
        Non-text parts like function calls are preserved.
        """
        is_run_based_session = a2a_context.get("is_run_based_session", False)
        is_streaming = a2a_context.get("is_streaming", False)
        is_final_turn_event = not adk_event.partial
        has_content_parts = adk_event.content and adk_event.content.parts

        # Only filter for PERSISTENT (not run-based) streaming sessions.
        if (
            not is_run_based_session
            and is_streaming
            and is_final_turn_event
            and has_content_parts
        ):
            log_id = f"{self.log_identifier}[FilterFinalStreamEvent:{a2a_context.get('logical_task_id', 'unknown')}]"
            log.debug(
                "%s Filtering final streaming event to remove redundant text.", log_id
            )

            non_text_parts = [
                part for part in adk_event.content.parts if part.text is None
            ]

            if len(non_text_parts) < len(adk_event.content.parts):
                event_copy = adk_event.model_copy(deep=True)
                event_copy.content = (
                    adk_types.Content(parts=non_text_parts) if non_text_parts else None
                )
                log.info(
                    "%s Removed text from final streaming event. Kept %d non-text part(s).",
                    log_id,
                    len(non_text_parts),
                )
                return event_copy

        return adk_event

    async def process_and_publish_adk_event(
        self, adk_event: ADKEvent, a2a_context: Dict
    ):
        """
        Main orchestrator for processing ADK events.
        Handles text buffering, embed resolution, and event routing based on
        whether the event is partial or the final event of a turn.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_id_main = (
            f"{self.log_identifier}[ProcessADKEvent:{logical_task_id}:{adk_event.id}]"
        )
        log.debug(
            "%s Received ADKEvent (Partial: %s, Final Turn: %s).",
            log_id_main,
            adk_event.partial,
            not adk_event.partial,
        )

        if adk_event.content and adk_event.content.parts:
            if any(
                p.function_response
                and p.function_response.name == "_continue_generation"
                for p in adk_event.content.parts
            ):
                log.debug(
                    "%s Discarding _continue_generation tool response event.",
                    log_id_main,
                )
                return

        if adk_event.custom_metadata and adk_event.custom_metadata.get(
            "was_interrupted"
        ):
            log.debug(
                "%s Found 'was_interrupted' signal. Skipping event.",
                log_id_main,
            )
            return

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.error(
                "%s TaskExecutionContext not found for task %s. Cannot process ADK event.",
                log_id_main,
                logical_task_id,
            )
            return

        is_run_based_session = a2a_context.get("is_run_based_session", False)
        is_final_turn_event = not adk_event.partial

        try:
            from solace_agent_mesh_enterprise.auth.tool_auth import (
                handle_tool_auth_event,
            )

            auth_status_update = await handle_tool_auth_event(
                adk_event, self, a2a_context
            )
            if auth_status_update:
                await self._publish_status_update_with_buffer_flush(
                    auth_status_update,
                    a2a_context,
                    skip_buffer_flush=False,
                )
                return
        except ImportError:
            pass

        if not is_final_turn_event:
            if adk_event.content and adk_event.content.parts:
                for part in adk_event.content.parts:
                    if part.text is not None:
                        # Check if this is a new turn by comparing invocation_id
                        if adk_event.invocation_id:
                            task_context.check_and_update_invocation(
                                adk_event.invocation_id
                            )
                            is_first_text = task_context.is_first_text_in_turn()
                            should_add_spacing = task_context.should_add_turn_spacing()

                            # Add spacing if this is the first text of a new turn
                            # We add it BEFORE the text, regardless of current buffer content
                            if should_add_spacing and is_first_text:
                                # Add double newline to separate turns (new paragraph)
                                task_context.append_to_streaming_buffer("\n\n")
                                log.debug(
                                    "%s Added turn spacing before new invocation %s",
                                    log_id_main,
                                    adk_event.invocation_id,
                                )

                        task_context.append_to_streaming_buffer(part.text)
                        log.debug(
                            "%s Appended text to buffer. New buffer size: %d bytes",
                            log_id_main,
                            len(
                                task_context.get_streaming_buffer_content().encode(
                                    "utf-8"
                                )
                            ),
                        )

            buffer_content = task_context.get_streaming_buffer_content()
            batching_disabled = self.stream_batching_threshold_bytes <= 0
            buffer_has_content = bool(buffer_content)
            threshold_met = (
                buffer_has_content
                and not batching_disabled
                and (
                    len(buffer_content.encode("utf-8"))
                    >= self.stream_batching_threshold_bytes
                )
            )

            if buffer_has_content and (batching_disabled or threshold_met):
                log.debug(
                    "%s Partial event triggered buffer flush due to size/batching config.",
                    log_id_main,
                )
                resolved_text, _ = await self._flush_and_resolve_buffer(
                    a2a_context, is_final=False
                )

                if resolved_text:
                    if is_run_based_session:
                        task_context.append_to_run_based_buffer(resolved_text)
                        log.debug(
                            "%s [RUN_BASED] Appended %d bytes to run_based_response_buffer.",
                            log_id_main,
                            len(resolved_text.encode("utf-8")),
                        )
                    else:
                        await self._publish_text_as_partial_a2a_status_update(
                            resolved_text, a2a_context
                        )
        else:
            buffer_content = task_context.get_streaming_buffer_content()
            if buffer_content:
                log.debug(
                    "%s Final event triggered flush of remaining buffer content.",
                    log_id_main,
                )
                resolved_text, _ = await self._flush_and_resolve_buffer(
                    a2a_context, is_final=True
                )
                if resolved_text:
                    if is_run_based_session:
                        task_context.append_to_run_based_buffer(resolved_text)
                        log.debug(
                            "%s [RUN_BASED] Appended final %d bytes to run_based_response_buffer.",
                            log_id_main,
                            len(resolved_text.encode("utf-8")),
                        )
                    else:
                        await self._publish_text_as_partial_a2a_status_update(
                            resolved_text, a2a_context
                        )

            # Prepare and publish the final event for observability
            event_to_publish = await self._filter_text_from_final_streaming_event(
                adk_event, a2a_context
            )

            (
                a2a_payload,
                target_topic,
                user_properties,
                _,
            ) = await format_and_route_adk_event(event_to_publish, a2a_context, self)

            if a2a_payload and target_topic:
                self._publish_a2a_event(a2a_payload, target_topic, a2a_context)
                log.debug(
                    "%s Published final turn event (e.g., tool call) to %s.",
                    log_id_main,
                    target_topic,
                )
            else:
                log.debug(
                    "%s Final turn event did not result in a publishable A2A message.",
                    log_id_main,
                )

            await self._handle_artifact_return_signals(adk_event, a2a_context)

    async def _flush_and_resolve_buffer(
        self, a2a_context: Dict, is_final: bool
    ) -> Tuple[str, str]:
        """Flushes buffer, resolves embeds, handles signals, returns (resolved_text, unprocessed_tail)."""
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_id = f"{self.log_identifier}[FlushBuffer:{logical_task_id}]"

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.error(
                "%s TaskExecutionContext not found for task %s. Cannot flush/resolve buffer.",
                log_id,
                logical_task_id,
            )
            return "", ""

        text_to_process = task_context.flush_streaming_buffer()

        resolved_text, signals_found, unprocessed_tail = (
            await self._resolve_early_embeds_and_handle_signals(
                text_to_process, a2a_context
            )
        )

        if not is_final:
            if unprocessed_tail:
                task_context.append_to_streaming_buffer(unprocessed_tail)
                log.debug(
                    "%s Placed unprocessed tail (length %d) back into buffer.",
                    log_id,
                    len(unprocessed_tail.encode("utf-8")),
                )
        else:
            if unprocessed_tail is not None and unprocessed_tail != "":
                resolved_text = resolved_text + unprocessed_tail

        if signals_found:
            log.info(
                "%s Handling %d signals from buffer resolution.",
                log_id,
                len(signals_found),
            )
            for _signal_index, signal_data_tuple, _placeholder in signals_found:
                if (
                    isinstance(signal_data_tuple, tuple)
                    and len(signal_data_tuple) == 3
                    and signal_data_tuple[0] is None
                    and signal_data_tuple[1] == "SIGNAL_STATUS_UPDATE"
                ):
                    status_text = signal_data_tuple[2]
                    log.info(
                        "%s Publishing SIGNAL_STATUS_UPDATE from buffer: '%s'",
                        log_id,
                        status_text,
                    )
                    await self._publish_agent_status_signal_update(
                        status_text, a2a_context
                    )
                    resolved_text = resolved_text.replace(_placeholder, "")

        return resolved_text, unprocessed_tail

    async def _handle_artifact_return_signals(
        self, adk_event: ADKEvent, a2a_context: Dict
    ):
        """
        Processes artifact return signals.
        This method is triggered by a placeholder in state_delta, but reads the
        actual list of signals from the TaskExecutionContext.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_id = f"{self.log_identifier}[ArtifactSignals:{logical_task_id}]"

        # Check for the trigger in state_delta. The presence of any key is enough.
        has_signal_trigger = (
            adk_event.actions
            and adk_event.actions.state_delta
            and any(
                k.startswith("temp:a2a_return_artifact:")
                for k in adk_event.actions.state_delta
            )
        )

        if not has_signal_trigger:
            return

        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)

        if not task_context:
            log.warning(
                "%s No TaskExecutionContext found for task %s. Cannot process artifact signals.",
                log_id,
                logical_task_id,
            )
            return

        all_signals = task_context.get_and_clear_artifact_signals()

        if not all_signals:
            log.info(
                "%s Triggered for artifact signals, but none were found in the execution context.",
                log_id,
            )
            return

        log.info(
            "%s Found %d artifact return signal(s) in the execution context.",
            log_id,
            len(all_signals),
        )

        original_session_id = a2a_context.get("session_id")
        user_id = a2a_context.get("user_id")
        adk_app_name = self.get_config("agent_name")

        peer_status_topic = a2a_context.get("statusTopic")
        namespace = self.get_config("namespace")
        gateway_id = self.get_gateway_id()

        artifact_topic = peer_status_topic or a2a.get_gateway_status_topic(
            namespace, gateway_id, logical_task_id
        )

        if not self.artifact_service:
            log.error("%s Artifact service not available.", log_id)
            return
        if not artifact_topic:
            log.error("%s Could not determine artifact topic.", log_id)
            return

        for item in all_signals:
            try:
                filename = item["filename"]
                version = item["version"]

                log.info(
                    "%s Processing artifact return signal for '%s' v%d from context.",
                    log_id,
                    filename,
                    version,
                )

                loaded_adk_part = await self.artifact_service.load_artifact(
                    app_name=adk_app_name,
                    user_id=user_id,
                    session_id=original_session_id,
                    filename=filename,
                    version=version,
                )

                if not loaded_adk_part:
                    log.warning(
                        "%s Failed to load artifact '%s' v%d.",
                        log_id,
                        filename,
                        version,
                    )
                    continue

                a2a_file_part = await a2a.translate_adk_part_to_a2a_filepart(
                    adk_part=loaded_adk_part,
                    filename=filename,
                    a2a_context=a2a_context,
                    artifact_service=self.artifact_service,
                    artifact_handling_mode=self.artifact_handling_mode,
                    adk_app_name=self.get_config("agent_name"),
                    log_identifier=self.log_identifier,
                    version=version,
                )

                if a2a_file_part:
                    a2a_message = a2a.create_agent_parts_message(
                        parts=[a2a_file_part],
                        task_id=logical_task_id,
                        context_id=original_session_id,
                    )
                    task_status = a2a.create_task_status(
                        state=TaskState.working, message=a2a_message
                    )
                    status_update_event = TaskStatusUpdateEvent(
                        task_id=logical_task_id,
                        context_id=original_session_id,
                        status=task_status,
                        final=False,
                        kind="status-update",
                    )
                    artifact_payload = a2a.create_success_response(
                        result=status_update_event,
                        request_id=a2a_context.get("jsonrpc_request_id"),
                    ).model_dump(exclude_none=True)

                    self._publish_a2a_event(
                        artifact_payload, artifact_topic, a2a_context
                    )

                    log.info(
                        "%s Published TaskStatusUpdateEvent with FilePart for '%s' to %s",
                        log_id,
                        filename,
                        artifact_topic,
                    )
                else:
                    log.warning(
                        "%s Failed to translate artifact '%s' v%d to A2A FilePart.",
                        log_id,
                        filename,
                        version,
                    )

            except Exception as e:
                log.exception(
                    "%s Error processing artifact signal item %s from context: %s",
                    log_id,
                    item,
                    e,
                )

    def _format_final_task_status(
        self, last_event: Optional[ADKEvent], override_text: Optional[str] = None
    ) -> TaskStatus:
        """Helper to format the final TaskStatus based on the last ADK event."""
        log.debug(
            "%s Formatting final task status from last ADK event %s",
            self.log_identifier,
            last_event.id if last_event else "None",
        )
        a2a_state = TaskState.completed
        a2a_parts = []

        if override_text is not None:
            a2a_parts.append(a2a.create_text_part(text=override_text))
            # Add non-text parts from the last event
            if last_event and last_event.content and last_event.content.parts:
                for part in last_event.content.parts:
                    if part.text is None:
                        if part.function_response:
                            a2a_parts.extend(
                                a2a.translate_adk_function_response_to_a2a_parts(part)
                            )
        else:
            # Original logic
            if last_event and last_event.content and last_event.content.parts:
                for part in last_event.content.parts:
                    if part.text:
                        a2a_parts.append(a2a.create_text_part(text=part.text))
                    elif part.function_response:
                        a2a_parts.extend(
                            a2a.translate_adk_function_response_to_a2a_parts(part)
                        )

        if last_event and last_event.actions:
            if last_event.actions.requested_auth_configs:
                a2a_state = TaskState.input_required
                a2a_parts.append(
                    a2a.create_text_part(text="[Agent requires input/authentication]")
                )

        if not a2a_parts:
            a2a_message = a2a.create_agent_text_message(text="")
        else:
            a2a_message = a2a.create_agent_parts_message(parts=a2a_parts)
        return a2a.create_task_status(state=a2a_state, message=a2a_message)

    async def finalize_task_success(self, a2a_context: Dict):
        """
        Finalizes a task successfully. Fetches final state, publishes final A2A response,
        and ACKs the original message.
        For RUN_BASED tasks, it uses the aggregated response buffer.
        For STREAMING tasks, it uses the content of the last ADK event.
        """
        logical_task_id = a2a_context.get("logical_task_id")

        # Retrieve the original Solace message from TaskExecutionContext
        original_message: Optional[SolaceMessage] = None
        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)
            if task_context:
                original_message = task_context.get_original_solace_message()

        log.info(
            "%s Finalizing task %s successfully.", self.log_identifier, logical_task_id
        )
        try:
            session_id_to_retrieve = a2a_context.get(
                "effective_session_id", a2a_context.get("session_id")
            )
            original_session_id = a2a_context.get("session_id")
            user_id = a2a_context.get("user_id")
            client_id = a2a_context.get("client_id")
            jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
            peer_reply_topic = a2a_context.get("replyToTopic")
            namespace = self.get_config("namespace")
            agent_name = self.get_config("agent_name")
            is_run_based_session = a2a_context.get("is_run_based_session", False)

            final_status: TaskStatus

            with self.active_tasks_lock:
                task_context = self.active_tasks.get(logical_task_id)

            final_adk_session = await self.session_service.get_session(
                app_name=agent_name,
                user_id=user_id,
                session_id=session_id_to_retrieve,
            )
            if not final_adk_session:
                raise RuntimeError(
                    f"Could not retrieve final session state for {session_id_to_retrieve}"
                )

            last_event = (
                final_adk_session.events[-1] if final_adk_session.events else None
            )

            if is_run_based_session:
                aggregated_text = ""
                if task_context:
                    aggregated_text = task_context.run_based_response_buffer
                    log.info(
                        "%s Using aggregated response buffer for RUN_BASED task %s (length: %d bytes).",
                        self.log_identifier,
                        logical_task_id,
                        len(aggregated_text.encode("utf-8")),
                    )
                final_status = self._format_final_task_status(
                    last_event, override_text=aggregated_text
                )
            else:
                if last_event:
                    final_status = self._format_final_task_status(last_event)
                else:
                    final_status = a2a.create_task_status(
                        state=TaskState.completed,
                        message=a2a.create_agent_text_message(text="Task completed."),
                    )

            final_a2a_artifacts: List[A2AArtifact] = []
            log.debug(
                "%s Final artifact bundling is removed. Artifacts sent via TaskArtifactUpdateEvent.",
                self.log_identifier,
            )

            final_task_metadata = {"agent_name": agent_name}
            if task_context and task_context.produced_artifacts:
                final_task_metadata["produced_artifacts"] = (
                    task_context.produced_artifacts
                )
                log.info(
                    "%s Attaching manifest of %d produced artifacts to final task metadata.",
                    self.log_identifier,
                    len(task_context.produced_artifacts),
                )
            else:
                if not task_context:
                    log.warning(
                        "%s TaskExecutionContext not found for task %s during finalization, cannot attach produced artifacts.",
                        self.log_identifier,
                        logical_task_id,
                    )
                else:
                    log.debug(
                        "%s No produced artifacts to attach for task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )

            # Add token usage summary
            if task_context:
                token_summary = task_context.get_token_usage_summary()
                if token_summary["total_tokens"] > 0:
                    final_task_metadata["token_usage"] = token_summary
                    log.info(
                        "%s Task %s used %d total tokens (input: %d, output: %d, cached: %d)",
                        self.log_identifier,
                        logical_task_id,
                        token_summary["total_tokens"],
                        token_summary["total_input_tokens"],
                        token_summary["total_output_tokens"],
                        token_summary["total_cached_input_tokens"],
                    )

            final_task = a2a.create_final_task(
                task_id=logical_task_id,
                context_id=original_session_id,
                final_status=final_status,
                artifacts=(final_a2a_artifacts if final_a2a_artifacts else None),
                metadata=final_task_metadata,
            )
            final_response = a2a.create_success_response(
                result=final_task, request_id=jsonrpc_request_id
            )
            a2a_payload = final_response.model_dump(exclude_none=True)
            target_topic = peer_reply_topic or a2a.get_client_response_topic(
                namespace, client_id
            )

            self._publish_a2a_event(a2a_payload, target_topic, a2a_context)
            log.info(
                "%s Published final successful response for task %s to %s (Artifacts NOT bundled).",
                self.log_identifier,
                logical_task_id,
                target_topic,
            )
            if original_message:
                try:
                    original_message.call_acknowledgements()
                    log.info(
                        "%s Called ACK for original message of task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as ack_e:
                    log.error(
                        "%s Failed to call ACK for task %s: %s",
                        self.log_identifier,
                        logical_task_id,
                        ack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found in context for task %s. Cannot ACK.",
                    self.log_identifier,
                    logical_task_id,
                )

        except Exception as e:
            log.exception(
                "%s Error during successful finalization of task %s: %s",
                self.log_identifier,
                logical_task_id,
                e,
            )
            if original_message:
                try:
                    original_message.call_negative_acknowledgements()
                    log.warning(
                        "%s Called NACK for original message of task %s due to finalization error.",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as nack_e:
                    log.error(
                        "%s Failed to call NACK for task %s after finalization error: %s",
                        self.log_identifier,
                        logical_task_id,
                        nack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found in context for task %s during finalization error. Cannot NACK.",
                    self.log_identifier,
                    logical_task_id,
                )

            try:
                jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
                client_id = a2a_context.get("client_id")
                peer_reply_topic = a2a_context.get("replyToTopic")
                namespace = self.get_config("namespace")
                error_response = a2a.create_internal_error_response(
                    message=f"Failed to finalize successful task: {e}",
                    request_id=jsonrpc_request_id,
                    data={"taskId": logical_task_id},
                )
                target_topic = peer_reply_topic or a2a.get_client_response_topic(
                    namespace, client_id
                )
                self.publish_a2a_message(
                    error_response.model_dump(exclude_none=True), target_topic
                )
            except Exception as report_err:
                log.error(
                    "%s Failed to report finalization error for task %s: %s",
                    self.log_identifier,
                    logical_task_id,
                    report_err,
                )

    def finalize_task_canceled(self, a2a_context: Dict):
        """
        Finalizes a task as CANCELED. Publishes A2A Task response with CANCELED state
        and ACKs the original message if available.
        Called by the background ADK thread wrapper when a task is cancelled.
        """
        logical_task_id = a2a_context.get("logical_task_id")

        # Retrieve the original Solace message from TaskExecutionContext
        original_message: Optional[SolaceMessage] = None
        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)
            if task_context:
                original_message = task_context.get_original_solace_message()

        log.info(
            "%s Finalizing task %s as CANCELED.", self.log_identifier, logical_task_id
        )
        try:
            jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
            client_id = a2a_context.get("client_id")
            peer_reply_topic = a2a_context.get("replyToTopic")
            namespace = self.get_config("namespace")

            canceled_status = a2a.create_task_status(
                state=TaskState.canceled,
                message=a2a.create_agent_text_message(
                    text="Task cancelled by request."
                ),
            )
            agent_name = self.get_config("agent_name")
            final_task = a2a.create_final_task(
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
                final_status=canceled_status,
                metadata={"agent_name": agent_name},
            )
            final_response = a2a.create_success_response(
                result=final_task, request_id=jsonrpc_request_id
            )
            a2a_payload = final_response.model_dump(exclude_none=True)
            target_topic = peer_reply_topic or a2a.get_client_response_topic(
                namespace, client_id
            )

            self._publish_a2a_event(a2a_payload, target_topic, a2a_context)
            log.info(
                "%s Published final CANCELED response for task %s to %s.",
                self.log_identifier,
                logical_task_id,
                target_topic,
            )

            if original_message:
                try:
                    original_message.call_acknowledgements()
                    log.info(
                        "%s Called ACK for original message of cancelled task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as ack_e:
                    log.error(
                        "%s Failed to call ACK for cancelled task %s: %s",
                        self.log_identifier,
                        logical_task_id,
                        ack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found in context for cancelled task %s. Cannot ACK.",
                    self.log_identifier,
                    logical_task_id,
                )

        except Exception as e:
            log.exception(
                "%s Error during CANCELED finalization of task %s: %s",
                self.log_identifier,
                logical_task_id,
                e,
            )
            if original_message:
                try:
                    original_message.call_negative_acknowledgements()
                except Exception:
                    pass

    async def _publish_tool_failure_status(
        self, exception: Exception, a2a_context: Dict
    ):
        """
        Publishes an intermediate status update indicating a tool execution has failed.
        This method will flush the buffer before publishing to maintain proper message ordering.
        """
        logical_task_id = a2a_context.get("logical_task_id")
        log_identifier_helper = (
            f"{self.log_identifier}[ToolFailureStatus:{logical_task_id}]"
        )
        try:
            # Create the status update event
            tool_error_data_part = a2a.create_data_part(
                data={
                    "a2a_signal_type": "tool_execution_error",
                    "error_message": str(exception),
                    "details": "An unhandled exception occurred during tool execution.",
                }
            )

            status_message = a2a.create_agent_parts_message(
                parts=[tool_error_data_part],
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
            )
            status_update_event = a2a.create_status_update(
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
                message=status_message,
                is_final=False,
                metadata={"agent_name": self.get_config("agent_name")},
            )

            await self._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=False,
            )

            log.debug(
                "%s Published tool failure status update.",
                log_identifier_helper,
            )

        except Exception as e:
            log.error(
                "%s Failed to publish intermediate tool failure status: %s",
                log_identifier_helper,
                e,
            )

    async def _repair_session_history_on_error(
        self, exception: Exception, a2a_context: Dict
    ):
        """
        Reactively repairs the session history if the last event was a tool call.
        This is "the belt" in the belt-and-suspenders strategy.
        """
        log_identifier = f"{self.log_identifier}[HistoryRepair]"
        try:
            from ...agent.adk.callbacks import create_dangling_tool_call_repair_content

            session_id = a2a_context.get("effective_session_id")
            user_id = a2a_context.get("user_id")
            agent_name = self.get_config("agent_name")

            if not all([session_id, user_id, agent_name, self.session_service]):
                log.warning(
                    "%s Skipping history repair due to missing context.", log_identifier
                )
                return

            session = await self.session_service.get_session(
                app_name=agent_name, user_id=user_id, session_id=session_id
            )

            if not session or not session.events:
                log.debug(
                    "%s No session or events found for history repair.", log_identifier
                )
                return

            last_event = session.events[-1]
            function_calls = last_event.get_function_calls()

            if not function_calls:
                log.debug(
                    "%s Last event was not a function call. No repair needed.",
                    log_identifier,
                )
                return

            log.info(
                "%s Last event contained function_call(s). Repairing session history.",
                log_identifier,
            )

            repair_content = create_dangling_tool_call_repair_content(
                dangling_calls=function_calls,
                error_message=f"Tool execution failed with an unhandled exception: {str(exception)}",
            )

            repair_event = ADKEvent(
                invocation_id=last_event.invocation_id,
                author=agent_name,
                content=repair_content,
            )

            await self.session_service.append_event(session=session, event=repair_event)
            log.info(
                "%s Session history repaired successfully with an error function_response.",
                log_identifier,
            )

        except Exception as e:
            log.exception(
                "%s Critical error during session history repair: %s", log_identifier, e
            )

    def finalize_task_limit_reached(
        self, a2a_context: Dict, exception: LlmCallsLimitExceededError
    ):
        """
        Finalizes a task when the LLM call limit is reached, prompting the user to continue.
        Sends a COMPLETED status with an informative message.
        """
        logical_task_id = a2a_context.get("logical_task_id")

        # Retrieve the original Solace message from TaskExecutionContext
        original_message: Optional[SolaceMessage] = None
        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)
            if task_context:
                original_message = task_context.get_original_solace_message()

        log.info(
            "%s Finalizing task %s as COMPLETED (LLM call limit reached).",
            self.log_identifier,
            logical_task_id,
        )
        try:
            jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
            client_id = a2a_context.get("client_id")
            peer_reply_topic = a2a_context.get("replyToTopic")
            namespace = self.get_config("namespace")
            agent_name = self.get_config("agent_name")
            original_session_id = a2a_context.get("session_id")

            limit_message_text = (
                f"This interaction has reached its processing limit. "
                "If you'd like to continue this conversation, please type 'continue'. "
                "Otherwise, you can start a new topic."
            )

            final_response = a2a.create_internal_error_response(
                message=limit_message_text,
                request_id=jsonrpc_request_id,
                data={"taskId": logical_task_id, "reason": "llm_call_limit_reached"},
            )
            a2a_payload = final_response.model_dump(exclude_none=True)

            target_topic = peer_reply_topic or a2a.get_client_response_topic(
                namespace, client_id
            )

            self._publish_a2a_event(a2a_payload, target_topic, a2a_context)
            log.info(
                "%s Published ERROR response for task %s to %s (LLM limit reached, user guided to continue).",
                self.log_identifier,
                logical_task_id,
                target_topic,
            )

            if original_message:
                try:
                    original_message.call_acknowledgements()
                    log.info(
                        "%s Called ACK for original message of task %s (LLM limit reached).",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as ack_e:
                    log.error(
                        "%s Failed to call ACK for task %s (LLM limit reached): %s",
                        self.log_identifier,
                        logical_task_id,
                        ack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found in context for task %s (LLM limit reached). Cannot ACK.",
                    self.log_identifier,
                    logical_task_id,
                )

        except Exception as e:
            log.exception(
                "%s Error during COMPLETED (LLM limit) finalization of task %s: %s",
                self.log_identifier,
                logical_task_id,
                e,
            )
            self.finalize_task_error(e, a2a_context)

    async def finalize_task_error(self, exception: Exception, a2a_context: Dict):
        """
        Finalizes a task with an error. Publishes a final A2A Task with a FAILED
        status and NACKs the original message.
        Called by the background ADK thread wrapper.
        """
        logical_task_id = a2a_context.get("logical_task_id")

        # Retrieve the original Solace message from TaskExecutionContext
        original_message: Optional[SolaceMessage] = None
        with self.active_tasks_lock:
            task_context = self.active_tasks.get(logical_task_id)
            if task_context:
                original_message = task_context.get_original_solace_message()

        log.error(
            "%s Finalizing task %s with error: %s",
            self.log_identifier,
            logical_task_id,
            exception,
        )
        try:
            await self._repair_session_history_on_error(exception, a2a_context)

            await self._publish_tool_failure_status(exception, a2a_context)

            client_id = a2a_context.get("client_id")
            jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
            peer_reply_topic = a2a_context.get("replyToTopic")
            namespace = self.get_config("namespace")

            # Detect context limit errors and provide user-friendly message
            error_message = "An unexpected error occurred during tool execution. Please try your request again. If the problem persists, contact an administrator."

            if isinstance(exception, BadRequestError):
                # Use centralized error handler
                error_message, is_context_limit = get_error_message(exception)

                if is_context_limit:
                    log.error(
                        "%s Context limit exceeded for task %s. Error: %s",
                        self.log_identifier,
                        logical_task_id,
                        exception,
                    )

            failed_status = a2a.create_task_status(
                state=TaskState.failed,
                message=a2a.create_agent_text_message(text=error_message),
            )

            final_task = a2a.create_final_task(
                task_id=logical_task_id,
                context_id=a2a_context.get("contextId"),
                final_status=failed_status,
                metadata={"agent_name": self.get_config("agent_name")},
            )

            final_response = a2a.create_success_response(
                result=final_task, request_id=jsonrpc_request_id
            )
            a2a_payload = final_response.model_dump(exclude_none=True)
            target_topic = peer_reply_topic or a2a.get_client_response_topic(
                namespace, client_id
            )

            self._publish_a2a_event(a2a_payload, target_topic, a2a_context)
            log.info(
                "%s Published final FAILED Task response for task %s to %s",
                self.log_identifier,
                logical_task_id,
                target_topic,
            )

            if original_message:
                try:
                    original_message.call_negative_acknowledgements()
                    log.info(
                        "%s Called NACK for original message of failed task %s.",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as nack_e:
                    log.error(
                        "%s Failed to call NACK for failed task %s: %s",
                        self.log_identifier,
                        logical_task_id,
                        nack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found in context for failed task %s. Cannot NACK.",
                    self.log_identifier,
                    logical_task_id,
                )

        except Exception as e:
            log.exception(
                "%s Error during error finalization of task %s: %s",
                self.log_identifier,
                logical_task_id,
                e,
            )
            if original_message:
                try:
                    original_message.call_negative_acknowledgements()
                    log.warning(
                        "%s Called NACK for task %s during error finalization fallback.",
                        self.log_identifier,
                        logical_task_id,
                    )
                except Exception as nack_e:
                    log.error(
                        "%s Failed to call NACK for task %s during error finalization fallback: %s",
                        self.log_identifier,
                        logical_task_id,
                        nack_e,
                    )
            else:
                log.warning(
                    "%s Original Solace message not found for task %s during error finalization fallback. Cannot NACK.",
                    self.log_identifier,
                    logical_task_id,
                )

    async def finalize_task_with_cleanup(
        self, a2a_context: Dict, is_paused: bool, exception: Optional[Exception] = None
    ):
        """
        Centralized async method to finalize a task and perform all necessary cleanup.
        This is scheduled on the component's event loop to ensure it runs after
        any pending status updates.

        Args:
            a2a_context: The context dictionary for the task.
            is_paused: Boolean indicating if the task is paused for a long-running tool.
            exception: The exception that occurred, if any.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        log_id = f"{self.log_identifier}[FinalizeTask:{logical_task_id}]"
        log.info(
            "%s Starting finalization and cleanup. Paused: %s, Exception: %s",
            log_id,
            is_paused,
            type(exception).__name__ if exception else "None",
        )

        try:
            if is_paused:
                log.info(
                    "%s Task is paused for a long-running tool. Skipping finalization logic.",
                    log_id,
                )
            else:
                try:
                    if exception:
                        if isinstance(exception, TaskCancelledError):
                            self.finalize_task_canceled(a2a_context)
                        elif isinstance(exception, LlmCallsLimitExceededError):
                            self.finalize_task_limit_reached(a2a_context, exception)
                        else:
                            await self.finalize_task_error(exception, a2a_context)
                    else:
                        await self.finalize_task_success(a2a_context)
                except Exception as e:
                    log.exception(
                        "%s An unexpected error occurred during the finalization logic itself: %s",
                        log_id,
                        e,
                    )
                    # Retrieve the original Solace message from TaskExecutionContext for fallback NACK
                    original_message: Optional[SolaceMessage] = None
                    with self.active_tasks_lock:
                        task_context = self.active_tasks.get(logical_task_id)
                        if task_context:
                            original_message = (
                                task_context.get_original_solace_message()
                            )

                    if original_message:
                        try:
                            original_message.call_negative_acknowledgements()
                        except Exception as nack_err:
                            log.error(
                                "%s Fallback NACK failed during finalization error: %s",
                                log_id,
                                nack_err,
                            )
        finally:
            if not is_paused:
                # Cleanup for RUN_BASED sessions remains, as it's a service-level concern
                if a2a_context.get("is_run_based_session"):
                    temp_session_id_to_delete = a2a_context.get(
                        "temporary_run_session_id_for_cleanup"
                    )
                    agent_name_for_session = a2a_context.get("agent_name_for_session")
                    user_id_for_session = a2a_context.get("user_id_for_session")

                    if (
                        temp_session_id_to_delete
                        and agent_name_for_session
                        and user_id_for_session
                    ):
                        log.info(
                            "%s Cleaning up RUN_BASED session (app: %s, user: %s, id: %s) from shared service for task_id='%s'",
                            log_id,
                            agent_name_for_session,
                            user_id_for_session,
                            temp_session_id_to_delete,
                            logical_task_id,
                        )
                        try:
                            if self.session_service:
                                await self.session_service.delete_session(
                                    app_name=agent_name_for_session,
                                    user_id=user_id_for_session,
                                    session_id=temp_session_id_to_delete,
                                )
                            else:
                                log.error(
                                    "%s self.session_service is None, cannot delete RUN_BASED session %s.",
                                    log_id,
                                    temp_session_id_to_delete,
                                )
                        except AttributeError:
                            log.error(
                                "%s self.session_service does not support 'delete_session'. Cleanup for RUN_BASED session (app: %s, user: %s, id: %s) skipped.",
                                log_id,
                                agent_name_for_session,
                                user_id_for_session,
                                temp_session_id_to_delete,
                            )
                        except Exception as e_cleanup:
                            log.error(
                                "%s Error cleaning up RUN_BASED session (app: %s, user: %s, id: %s) from shared service: %s",
                                log_id,
                                agent_name_for_session,
                                user_id_for_session,
                                temp_session_id_to_delete,
                                e_cleanup,
                                exc_info=True,
                            )
                    else:
                        log.warning(
                            "%s Could not clean up RUN_BASED session for task %s due to missing context (id_to_delete: %s, agent_name: %s, user_id: %s).",
                            log_id,
                            logical_task_id,
                            temp_session_id_to_delete,
                            agent_name_for_session,
                            user_id_for_session,
                        )

                with self.active_tasks_lock:
                    removed_task_context = self.active_tasks.pop(logical_task_id, None)
                    if removed_task_context:
                        log.debug(
                            "%s Removed TaskExecutionContext for task %s.",
                            log_id,
                            logical_task_id,
                        )
                    else:
                        log.warning(
                            "%s TaskExecutionContext for task %s was already removed.",
                            log_id,
                            logical_task_id,
                        )
            else:
                log.info(
                    "%s Task %s is paused for a long-running tool. Skipping all cleanup.",
                    log_id,
                    logical_task_id,
                )

            log.info(
                "%s Finalization and cleanup complete for task %s.",
                log_id,
                logical_task_id,
            )

    def _resolve_instruction_provider(
        self, config_value: Any
    ) -> Union[str, InstructionProvider]:
        """Resolves instruction config using helper."""
        return resolve_instruction_provider(self, config_value)

    def _get_a2a_base_topic(self) -> str:
        """Returns the base topic prefix using helper."""
        return a2a.get_a2a_base_topic(self.namespace)

    def _get_discovery_topic(self) -> str:
        """Returns the agent discovery topic for publishing."""
        return a2a.get_agent_discovery_topic(self.namespace)

    def _get_agent_request_topic(self, agent_id: str) -> str:
        """Returns the agent request topic using helper."""
        return a2a.get_agent_request_topic(self.namespace, agent_id)

    def _get_agent_response_topic(
        self, delegating_agent_name: str, sub_task_id: str
    ) -> str:
        """Returns the agent response topic using helper."""
        return a2a.get_agent_response_topic(
            self.namespace, delegating_agent_name, sub_task_id
        )

    def _get_peer_agent_status_topic(
        self, delegating_agent_name: str, sub_task_id: str
    ) -> str:
        """Returns the peer agent status topic using helper."""
        return a2a.get_peer_agent_status_topic(
            self.namespace, delegating_agent_name, sub_task_id
        )

    def _get_client_response_topic(self, client_id: str) -> str:
        """Returns the client response topic using helper."""
        return a2a.get_client_response_topic(self.namespace, client_id)

    def _publish_a2a_event(
        self,
        payload: Dict,
        topic: str,
        a2a_context: Dict,
        user_properties_override: Optional[Dict] = None,
    ):
        """
        Centralized helper to publish an A2A event, ensuring user properties
        are consistently attached from the a2a_context or an override.
        """
        if user_properties_override is not None:
            user_properties = user_properties_override
        else:
            user_properties = {}
            if a2a_context.get("a2a_user_config"):
                user_properties["a2aUserConfig"] = a2a_context["a2a_user_config"]

        self.publish_a2a_message(payload, topic, user_properties)

    def submit_a2a_task(
        self,
        target_agent_name: str,
        a2a_message: A2AMessage,
        user_id: str,
        user_config: Dict[str, Any],
        sub_task_id: str,
    ) -> str:
        """
        Submits a task to a peer agent in a non-blocking way.
        Returns the sub_task_id for correlation.
        """
        log_identifier_helper = (
            f"{self.log_identifier}[SubmitA2ATask:{target_agent_name}]"
        )
        main_task_id = a2a_message.metadata.get("parentTaskId", "unknown_parent")

        log.debug(
            "%s Submitting non-blocking task for main task %s",
            log_identifier_helper,
            main_task_id,
        )

        # Validate agent access is allowed
        validate_agent_access(
            user_config=user_config,
            target_agent_name=target_agent_name,
            validation_context={
                "delegating_agent": self.get_config("agent_name"),
                "source": "agent_delegation",
            },
            log_identifier=log_identifier_helper,
        )

        peer_request_topic = self._get_agent_request_topic(target_agent_name)

        # Create a compliant SendMessageRequest
        send_params = MessageSendParams(message=a2a_message)
        a2a_request = SendMessageRequest(id=sub_task_id, params=send_params)

        delegating_agent_name = self.get_config("agent_name")
        reply_to_topic = self._get_agent_response_topic(
            delegating_agent_name=delegating_agent_name,
            sub_task_id=sub_task_id,
        )
        status_topic = self._get_peer_agent_status_topic(
            delegating_agent_name=delegating_agent_name,
            sub_task_id=sub_task_id,
        )

        user_properties = {
            "replyTo": reply_to_topic,
            "a2aStatusTopic": status_topic,
            "userId": user_id,
            "delegating_agent_name": delegating_agent_name,
        }
        if isinstance(user_config, dict):
            user_properties["a2aUserConfig"] = user_config

        # Retrieve call depth and auth token from parent task context
        parent_task_id = a2a_message.metadata.get("parentTaskId")
        current_depth = 0
        if parent_task_id:
            with self.active_tasks_lock:
                parent_task_context = self.active_tasks.get(parent_task_id)

            if parent_task_context:
                # Get current call depth from parent context
                current_depth = parent_task_context.a2a_context.get("call_depth", 0)

                auth_token = parent_task_context.get_security_data("auth_token")
                if auth_token:
                    user_properties["authToken"] = auth_token
                    log.debug(
                        "%s Propagating authentication token to peer agent %s for sub-task %s",
                        log_identifier_helper,
                        target_agent_name,
                        sub_task_id,
                    )
                else:
                    log.debug(
                        "%s No authentication token found in parent task context for sub-task %s",
                        log_identifier_helper,
                        sub_task_id,
                    )
            else:
                log.warning(
                    "%s Parent task context not found for task %s, cannot propagate authentication token",
                    log_identifier_helper,
                    parent_task_id,
                )

        # Add call depth to user properties (increment for outgoing call)
        user_properties["callDepth"] = current_depth + 1

        self.publish_a2a_message(
            payload=a2a_request.model_dump(by_alias=True, exclude_none=True),
            topic=peer_request_topic,
            user_properties=user_properties,
        )
        log.info(
            "%s Published delegation request to %s (Sub-Task ID: %s, ReplyTo: %s, StatusTo: %s)",
            log_identifier_helper,
            peer_request_topic,
            sub_task_id,
            reply_to_topic,
            status_topic,
        )

        return sub_task_id

    def _handle_scheduled_task_completion(
        self, future: concurrent.futures.Future, event_type_for_log: EventType
    ):
        """Callback to handle completion of futures from run_coroutine_threadsafe."""
        try:
            if future.cancelled():
                log.warning(
                    "%s Coroutine for event type %s (scheduled via run_coroutine_threadsafe) was cancelled.",
                    self.log_identifier,
                    event_type_for_log,
                )
            elif future.done() and future.exception() is not None:
                exception = future.exception()
                log.error(
                    "%s Coroutine for event type %s (scheduled via run_coroutine_threadsafe) failed with exception: %s",
                    self.log_identifier,
                    event_type_for_log,
                    exception,
                    exc_info=exception,
                )
            else:
                pass
        except Exception as e:
            log.error(
                "%s Error during _handle_scheduled_task_completion (for run_coroutine_threadsafe future) for event type %s: %s",
                self.log_identifier,
                event_type_for_log,
                e,
                exc_info=e,
            )

    async def _perform_async_init(self):
        """Coroutine executed on the dedicated loop to perform async initialization."""
        try:
            log.info(
                "%s Loading tools asynchronously in dedicated thread...",
                self.log_identifier,
            )
            (
                loaded_tools,
                enabled_builtin_tools,
                self._tool_cleanup_hooks,
            ) = await load_adk_tools(self)
            log.info(
                "%s Initializing ADK Agent/Runner asynchronously in dedicated thread...",
                self.log_identifier,
            )
            self.adk_agent = initialize_adk_agent(
                self, loaded_tools, enabled_builtin_tools
            )
            self.runner = initialize_adk_runner(self)

            log.info("%s Populating agent card tool manifest...", self.log_identifier)
            tool_manifest = []
            for tool in loaded_tools:
                if isinstance(tool, MCPToolset):
                    try:
                        log.debug(
                            "%s Retrieving tools from MCPToolset for Agent %s...",
                            self.log_identifier,
                            self.agent_name,
                        )
                        mcp_tools = await tool.get_tools()
                    except Exception as e:
                        log.error(
                            "%s Error retrieving tools from MCPToolset for Agent Card %s: %s",
                            self.log_identifier,
                            self.agent_name,
                            e,
                        )
                        continue
                    for mcp_tool in mcp_tools:
                        tool_manifest.append(
                            {
                                "id": mcp_tool.name,
                                "name": mcp_tool.name,
                                "description": mcp_tool.description
                                or "No description available.",
                            }
                        )
                elif isinstance(tool, OpenAPIToolset):
                    try:
                        log.debug(
                            "%s Retrieving tools from OpenAPIToolset for Agent %s...",
                            self.log_identifier,
                            self.agent_name,
                        )
                        openapi_tools = await tool.get_tools()
                    except Exception as e:
                        log.error(
                            "%s Error retrieving tools from OpenAPIToolset for Agent Card %s: %s",
                            self.log_identifier,
                            self.agent_name,
                            e,
                        )
                        continue
                    for openapi_tool in openapi_tools:
                        tool_manifest.append(
                            {
                                "id": openapi_tool.name,
                                "name": openapi_tool.name,
                                "description": openapi_tool.description
                                or "No description available.",
                            }
                        )
                else:
                    tool_name = getattr(tool, "name", getattr(tool, "__name__", None))
                    if tool_name is not None:
                        tool_manifest.append(
                            {
                                "id": tool_name,
                                "name": tool_name,
                                "description": getattr(
                                    tool, "description", getattr(tool, "__doc__", None)
                                )
                                or "No description available.",
                            }
                        )

            self.agent_card_tool_manifest = tool_manifest
            log.info(
                "%s Agent card tool manifest populated with %d tools.",
                self.log_identifier,
                len(self.agent_card_tool_manifest),
            )

            log.info(
                "%s Async initialization steps complete in dedicated thread.",
                self.log_identifier,
            )
            if self._async_init_future and not self._async_init_future.done():
                log.info(
                    "%s _perform_async_init: Signaling success to main thread.",
                    self.log_identifier,
                )
                self._async_loop.call_soon_threadsafe(
                    self._async_init_future.set_result, True
                )
            else:
                log.warning(
                    "%s _perform_async_init: _async_init_future is None or already done before signaling success.",
                    self.log_identifier,
                )
        except Exception as e:
            log.exception(
                "%s _perform_async_init: Error during async initialization in dedicated thread: %s",
                self.log_identifier,
                e,
            )
            if self._async_init_future and not self._async_init_future.done():
                log.error(
                    "%s _perform_async_init: Signaling failure to main thread.",
                    self.log_identifier,
                )
                self._async_loop.call_soon_threadsafe(
                    self._async_init_future.set_exception, e
                )
            else:
                log.warning(
                    "%s _perform_async_init: _async_init_future is None or already done before signaling failure.",
                    self.log_identifier,
                )
            raise e

    def cleanup(self):
        """Clean up resources on component shutdown."""
        log.info("%s Cleaning up A2A ADK Host Component.", self.log_identifier)
        self.cancel_timer(self._card_publish_timer_id)
        self.cancel_timer(self.HEALTH_CHECK_TIMER_ID)

        cleanup_func_details = self.get_config("agent_cleanup_function")

        from .app import AgentInitCleanupConfig  # Avoid circular import

        if cleanup_func_details and isinstance(
            cleanup_func_details, AgentInitCleanupConfig
        ):
            module_name = cleanup_func_details.get("module")
            func_name = cleanup_func_details.get("name")
            base_path = cleanup_func_details.get("base_path")

            if module_name and func_name:
                log.info(
                    "%s Attempting to load and execute cleanup_function: %s.%s",
                    self.log_identifier,
                    module_name,
                    func_name,
                )
                try:
                    module = import_module(module_name, base_path=base_path)
                    cleanup_function = getattr(module, func_name)

                    if not callable(cleanup_function):
                        log.error(
                            "%s Cleanup function '%s' in module '%s' is not callable. Skipping.",
                            self.log_identifier,
                            func_name,
                            module_name,
                        )
                    else:
                        cleanup_function(self)
                        log.info(
                            "%s Successfully executed cleanup_function: %s.%s",
                            self.log_identifier,
                            module_name,
                            func_name,
                        )
                except Exception as e:
                    log.exception(
                        "%s Error during agent cleanup via cleanup_function '%s.%s': %s",
                        self.log_identifier,
                        module_name,
                        func_name,
                        e,
                    )
        if self._tool_cleanup_hooks:
            log.info(
                "%s Executing %d tool cleanup hooks...",
                self.log_identifier,
                len(self._tool_cleanup_hooks),
            )
            if self._async_loop and self._async_loop.is_running():

                async def run_tool_cleanup():
                    results = await asyncio.gather(
                        *[hook() for hook in self._tool_cleanup_hooks],
                        return_exceptions=True,
                    )
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            log.error(
                                "%s Error during tool cleanup hook #%d: %s",
                                self.log_identifier,
                                i,
                                result,
                                exc_info=result,
                            )

                future = asyncio.run_coroutine_threadsafe(
                    run_tool_cleanup(), self._async_loop
                )
                try:
                    future.result(timeout=15)  # Wait for cleanup to complete
                    log.info("%s All tool cleanup hooks executed.", self.log_identifier)
                except Exception as e:
                    log.error(
                        "%s Exception while waiting for tool cleanup hooks to finish: %s",
                        self.log_identifier,
                        e,
                    )
            else:
                log.warning(
                    "%s Cannot execute tool cleanup hooks because the async loop is not running.",
                    self.log_identifier,
                )

        # The base class cleanup() will handle stopping the async loop and joining the thread.
        # We just need to cancel any active tasks before that happens.
        with self.active_tasks_lock:
            if self._async_loop and self._async_loop.is_running():
                for task_context in self.active_tasks.values():
                    task_context.cancel()
            self.active_tasks.clear()
            log.debug("%s Cleared all active tasks.", self.log_identifier)

        super().cleanup()
        log.info("%s Component cleanup finished.", self.log_identifier)

    def set_agent_specific_state(self, key: str, value: Any):
        """
        Sets a key-value pair in the agent-specific state.
        Intended to be used by the custom init_function.
        """
        if not hasattr(self, "agent_specific_state"):
            self.agent_specific_state = {}
        self.agent_specific_state[key] = value
        log.debug("%s Set agent_specific_state['%s']", self.log_identifier, key)

    def get_agent_specific_state(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Gets a value from the agent-specific state.
        Intended to be used by tools and the custom cleanup_function.
        """
        if not hasattr(self, "agent_specific_state"):
            return default
        return self.agent_specific_state.get(key, default)

    def get_async_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Returns the dedicated asyncio event loop for this component's async tasks."""
        return self._async_loop

    def publish_data_signal_from_thread(
        self,
        a2a_context: Dict[str, Any],
        signal_data: BaseModel,
        skip_buffer_flush: bool = False,
        log_identifier: Optional[str] = None,
    ) -> bool:
        """
        Publishes a data signal status update from any thread by scheduling it on the async loop.

        This is a convenience method for tools and callbacks that need to publish status updates
        but are not running in an async context. It handles:
        1. Extracting task_id and context_id from a2a_context
        2. Creating the status update event
        3. Checking if the async loop is available and running
        4. Scheduling the publish operation on the async loop

        Args:
            a2a_context: The A2A context dictionary containing logical_task_id and contextId
            signal_data: A Pydantic BaseModel instance (e.g., AgentProgressUpdateData,
                        DeepResearchProgressData, ArtifactCreationProgressData)
            skip_buffer_flush: If True, skip buffer flushing before publishing
            log_identifier: Optional log identifier for debugging

        Returns:
            bool: True if the publish was successfully scheduled, False otherwise
        """
        from ...common import a2a

        log_id = log_identifier or f"{self.log_identifier}[PublishDataSignal]"

        if not a2a_context:
            log.error("%s No a2a_context provided. Cannot publish data signal.", log_id)
            return False

        logical_task_id = a2a_context.get("logical_task_id")
        context_id = a2a_context.get("contextId")

        if not logical_task_id:
            log.error("%s No logical_task_id in a2a_context. Cannot publish data signal.", log_id)
            return False

        # Create status update event using the standard data signal pattern
        status_update_event = a2a.create_data_signal_event(
            task_id=logical_task_id,
            context_id=context_id,
            signal_data=signal_data,
            agent_name=self.agent_name,
        )

        # Get the async loop and schedule the publish
        loop = self.get_async_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._publish_status_update_with_buffer_flush(
                    status_update_event,
                    a2a_context,
                    skip_buffer_flush=skip_buffer_flush,
                ),
                loop,
            )
            log.debug(
                "%s Scheduled data signal status update (type: %s).",
                log_id,
                type(signal_data).__name__,
            )
            return True
        else:
            log.error(
                "%s Async loop not available or not running. Cannot publish data signal.",
                log_id,
            )
            return False

    def set_agent_system_instruction_string(self, instruction_string: str) -> None:
        """
        Sets a static string to be injected into the LLM system prompt.
        Called by the agent's init_function.
        """
        if not isinstance(instruction_string, str):
            log.error(
                "%s Invalid type for instruction_string: %s. Must be a string.",
                self.log_identifier,
                type(instruction_string),
            )
            return
        self._agent_system_instruction_string = instruction_string
        self._agent_system_instruction_callback = None
        log.info("%s Static agent system instruction string set.", self.log_identifier)

    def set_agent_system_instruction_callback(
        self,
        callback_function: Optional[
            Callable[[CallbackContext, LlmRequest], Optional[str]]
        ],
    ) -> None:
        """
        Sets a callback function to dynamically generate system prompt injections.
        Called by the agent's init_function.
        """
        if callback_function is not None and not callable(callback_function):
            log.error(
                "%s Invalid type for callback_function: %s. Must be callable.",
                self.log_identifier,
                type(callback_function),
            )
            return
        self._agent_system_instruction_callback = callback_function
        self._agent_system_instruction_string = None
        log.info("%s Agent system instruction callback set.", self.log_identifier)

    def get_gateway_id(self) -> str:
        """
        Returns a unique identifier for this specific gateway/host instance.
        For now, using the agent name, but could be made more robust (e.g., hostname + agent name).
        """
        return self.agent_name

    def _check_agent_health(self):
        """
        Checks the health of peer agents and de-registers unresponsive ones.
        This is called periodically by the health check timer.
        Uses TTL-based expiration to determine if an agent is unresponsive.
        """

        log.debug("%s Performing agent health check...", self.log_identifier)

        ttl_seconds = self.agent_discovery_config.get(
            "health_check_ttl_seconds", HEALTH_CHECK_TTL_SECONDS
        )
        health_check_interval = self.agent_discovery_config.get(
            "health_check_interval_seconds", HEALTH_CHECK_INTERVAL_SECONDS
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
            # Skip our own agent
            if agent_name == self.agent_name:
                continue

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
        registry_removed = self.agent_registry.remove_agent(agent_name)

        # Always remove from peer_agents regardless of registry result
        peer_removed = False
        if agent_name in self.peer_agents:
            del self.peer_agents[agent_name]
            peer_removed = True
            log.info(
                "%s Removed agent '%s' from peer_agents dictionary",
                self.log_identifier,
                agent_name,
            )

        # Publish de-registration event if agent was in either data structure
        if registry_removed or peer_removed:
            try:
                # Create a de-registration event topic
                namespace = self.get_config("namespace")
                deregistration_topic = f"{namespace}/a2a/events/agent/deregistered"

                current_time = time.time()

                # Create the payload
                deregistration_payload = {
                    "event_type": "agent.deregistered",
                    "agent_name": agent_name,
                    "reason": "health_check_failure",
                    "metadata": {
                        "timestamp": current_time,
                        "deregistered_by": self.agent_name,
                    },
                }

                # Publish the event
                self.publish_a2a_message(
                    payload=deregistration_payload, topic=deregistration_topic
                )

                log.info(
                    "%s Published de-registration event for agent '%s' to topic '%s'",
                    self.log_identifier,
                    agent_name,
                    deregistration_topic,
                )
            except Exception as e:
                log.error(
                    "%s Failed to publish de-registration event for agent '%s': %s",
                    self.log_identifier,
                    agent_name,
                    e,
                )

    async def _resolve_early_embeds_and_handle_signals(
        self, raw_text: str, a2a_context: Dict
    ) -> Tuple[str, List[Tuple[int, Any]], str]:
        """
        Resolves early-stage embeds in raw text and extracts signals.
        Returns the resolved text, a list of signals, and any unprocessed tail.
        This is called by process_and_publish_adk_event.
        """
        logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
        method_context_log_identifier = (
            f"{self.log_identifier}[ResolveEmbeds:{logical_task_id}]"
        )
        log.debug(
            "%s Resolving early embeds for text (length: %d).",
            method_context_log_identifier,
            len(raw_text),
        )

        original_session_id = a2a_context.get("session_id")
        user_id = a2a_context.get("user_id")
        adk_app_name = self.get_config("agent_name")

        if not all([self.artifact_service, original_session_id, user_id, adk_app_name]):
            log.error(
                "%s Missing necessary context for embed resolution (artifact_service, session_id, user_id, or adk_app_name). Skipping.",
                method_context_log_identifier,
            )
            return (
                raw_text,
                [],
                "",
            )
        context_for_embeds = {
            "artifact_service": self.artifact_service,
            "session_context": {
                "app_name": adk_app_name,
                "user_id": user_id,
                "session_id": original_session_id,
            },
            "config": {
                "gateway_max_artifact_resolve_size_bytes": self.get_config(
                    "tool_output_llm_return_max_bytes", 4096
                ),
                "gateway_recursive_embed_depth": self.get_config(
                    "gateway_recursive_embed_depth", 12
                ),
            },
        }

        resolver_config = context_for_embeds["config"]

        try:
            from ...common.utils.embeds.constants import EARLY_EMBED_TYPES
            from ...common.utils.embeds.types import ResolutionMode
            from ...common.utils.embeds.resolver import (
                evaluate_embed,
                resolve_embeds_in_string,
            )

            resolved_text, processed_until_index, signals_found = (
                await resolve_embeds_in_string(
                    text=raw_text,
                    context=context_for_embeds,
                    resolver_func=evaluate_embed,
                    types_to_resolve=EARLY_EMBED_TYPES,
                    resolution_mode=ResolutionMode.TOOL_PARAMETER,
                    log_identifier=method_context_log_identifier,
                    config=resolver_config,
                )
            )
            unprocessed_tail = raw_text[processed_until_index:]
            log.debug(
                "%s Embed resolution complete. Resolved text: '%s...', Signals found: %d, Unprocessed tail: '%s...'",
                method_context_log_identifier,
                resolved_text[:100],
                len(signals_found),
                unprocessed_tail[:100],
            )
            return resolved_text, signals_found, unprocessed_tail
        except Exception as e:
            log.exception(
                "%s Error during embed resolution: %s", method_context_log_identifier, e
            )
            return raw_text, [], ""

    def _publish_agent_card(self) -> None:
        """
        Schedules periodic publishing of the agent card based on configuration.
        """
        try:
            publish_interval_sec = self.agent_card_publishing_config.get(
                "interval_seconds"
            )
            if publish_interval_sec and publish_interval_sec > 0:
                log.info(
                    "%s Scheduling agent card publishing every %d seconds.",
                    self.log_identifier,
                    publish_interval_sec,
                )
                # Register timer with callback
                self.add_timer(
                    delay_ms=1000,
                    timer_id=self._card_publish_timer_id,
                    interval_ms=publish_interval_sec * 1000,
                    callback=lambda timer_data: publish_agent_card(self),
                )
            else:
                log.warning(
                    "%s Agent card publishing interval not configured or invalid, card will not be published periodically.",
                    self.log_identifier,
                )
        except Exception as e:
            log.exception(
                "%s Error during _publish_agent_card setup: %s",
                self.log_identifier,
                e,
            )
            raise e

    async def _async_setup_and_run(self) -> None:
        """
        Main async logic for the agent component.
        This is called by the base class's `_run_async_operations`.
        """
        try:
            # Call base class to initialize Trust Manager
            await super()._async_setup_and_run()

            # Perform agent-specific async initialization
            await self._perform_async_init()

            self._publish_agent_card()

        except Exception as e:
            log.exception(
                "%s Error during _async_setup_and_run: %s",
                self.log_identifier,
                e,
            )
            self.cleanup()
            raise e

    def _pre_async_cleanup(self) -> None:
        """
        Pre-cleanup actions for the agent component.
        Called by the base class before stopping the async loop.
        """
        # Cleanup Trust Manager if present (ENTERPRISE FEATURE)
        if self.trust_manager:
            try:
                self.trust_manager.cleanup(self.cancel_timer)
            except Exception as e:
                log.error(
                    "%s Error during Trust Manager cleanup: %s", self.log_identifier, e
                )
