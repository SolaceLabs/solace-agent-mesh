"""
Handles ADK Agent and Runner initialization, including tool loading and callback assignment.
"""

from typing import Dict, List, Optional, Union, Callable, Tuple, Set, Any, TYPE_CHECKING, Type
import functools
import inspect
from solace_ai_connector.common.log import log
from solace_ai_connector.common.utils import import_module
from ...common.utils.type_utils import is_subclass_by_name

from .app_llm_agent import AppLlmAgent
from .tool_wrapper import ADKToolWrapper
from .embed_resolving_mcp_toolset import EmbedResolvingMCPToolset
from google.adk.runners import Runner
from google.adk.models import BaseLlm
from google.adk.tools import BaseTool, ToolContext
from google.adk import tools as adk_tools_module
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseServerParams,
    StdioConnectionParams,
)

from mcp import StdioServerParameters

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

from ..tools.registry import tool_registry
from ..tools.tool_definition import BuiltinTool
from ..tools.dynamic_tool import DynamicTool, DynamicToolProvider
from ..tools.tool_config_types import AnyToolConfig


from ...agent.adk import callbacks as adk_callbacks
from ...agent.adk.models.lite_llm import LiteLlm


# Define a clear return type for all tool-loading helpers
ToolLoadingResult = Tuple[List[Union[BaseTool, Callable]], List[BuiltinTool], List[Callable]]


def _find_dynamic_tool_class(module) -> Optional[type]:
    """Finds a single non-abstract DynamicTool subclass in a module."""
    found_classes = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            is_subclass_by_name(obj, "DynamicTool")
            and not is_subclass_by_name(obj, "DynamicToolProvider")
            and not inspect.isabstract(obj)
        ):
            found_classes.append(obj)
    if len(found_classes) > 1:
        raise TypeError(
            f"Module '{module.__name__}' contains multiple DynamicTool subclasses. "
            "Please specify which one to use with 'class_name' in the config."
        )
    return found_classes[0] if found_classes else None


async def _execute_lifecycle_hook(
    component: "SamAgentComponent",
    func_name: Optional[str],
    module_name: str,
    base_path: Optional[str],
    tool_config_model: AnyToolConfig,
):
    """Dynamically loads and executes a lifecycle hook function."""
    if not func_name:
        return

    log.info(
        "%s Executing lifecycle hook: %s.%s",
        component.log_identifier,
        module_name,
        func_name,
    )

    try:
        module = import_module(module_name, base_path=base_path)
        func = getattr(module, func_name)

        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"Lifecycle hook '{func_name}' in module '{module_name}' must be an async function."
            )

        await func(component, tool_config_model)
        log.info(
            "%s Successfully executed lifecycle hook: %s.%s",
            component.log_identifier,
            module_name,
            func_name,
        )
    except Exception as e:
        log.exception(
            "%s Fatal error during lifecycle hook execution for '%s.%s': %s",
            component.log_identifier,
            module_name,
            func_name,
            e,
        )
        raise RuntimeError(f"Tool lifecycle initialization failed: {e}") from e


def _create_cleanup_partial(
    component: "SamAgentComponent",
    func_name: Optional[str],
    module_name: str,
    base_path: Optional[str],
    tool_config_model: AnyToolConfig,
) -> Optional[Callable]:
    """Creates a functools.partial for a cleanup hook function."""
    if not func_name:
        return None

    try:
        module = import_module(module_name, base_path=base_path)
        func = getattr(module, func_name)

        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"Lifecycle hook '{func_name}' in module '{module_name}' must be an async function."
            )

        return functools.partial(func, component, tool_config_model)
    except Exception as e:
        log.exception(
            "%s Fatal error creating partial for cleanup hook '%s.%s': %s",
            component.log_identifier,
            module_name,
            func_name,
            e,
        )
        raise RuntimeError(f"Tool lifecycle setup failed: {e}") from e


def _find_dynamic_tool_provider_class(module) -> Optional[type]:
    """Finds a single non-abstract DynamicToolProvider subclass in a module."""
    found_classes = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if is_subclass_by_name(obj, "DynamicToolProvider") and not inspect.isabstract(
            obj
        ):
            found_classes.append(obj)
    if len(found_classes) > 1:
        raise TypeError(
            f"Module '{module.__name__}' contains multiple DynamicToolProvider subclasses. "
            "Only one is permitted per module."
        )
    return found_classes[0] if found_classes else None


def _check_and_register_tool_name(name: str, source: str, loaded_tool_names: Set[str]):
    """Checks for duplicate tool names and raises ValueError if found."""
    if name in loaded_tool_names:
        raise ValueError(
            f"Configuration Error: Duplicate tool name '{name}' found from source '{source}'. "
            "This name is already in use. Please resolve the conflict by renaming or "
            "disabling one of the tools in your agent's configuration."
        )
    loaded_tool_names.add(name)


async def _load_python_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    # To be implemented in Step 4
    pass

async def _load_builtin_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    # To be implemented in Step 5
    pass

async def _load_builtin_group_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    # To be implemented in Step 5
    pass

async def _load_mcp_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    # To be implemented in Step 5
    pass

def _load_internal_tools(component: "SamAgentComponent", loaded_tool_names: Set[str]) -> ToolLoadingResult:
    # To be implemented in Step 6
    pass


async def load_adk_tools(
    component,
) -> Tuple[List[Union[BaseTool, Callable]], List[BuiltinTool], List[Callable]]:
    """
    Loads all configured tools for the agent.
    - Explicitly configured tools (Python, MCP, ADK Built-ins) from YAML.
    - SAM Built-in tools (Artifact, Data, etc.) from the tool registry,
      filtered by agent configuration.

    Args:
        component: The SamAgentComponent instance.

    Returns:
        A tuple containing:
        - A list of loaded tool callables/instances for the ADK agent.
        - A list of enabled BuiltinTool definition objects for prompt generation.
        - A list of awaitable cleanup functions for the tools.

    Raises:
        ImportError: If a configured tool or its dependencies cannot be loaded.
    """
    loaded_tools: List[Union[BaseTool, Callable]] = []
    enabled_builtin_tools: List[BuiltinTool] = []
    loaded_tool_names: Set[str] = set()
    cleanup_hooks: List[Callable] = []
    tools_config = component.get_config("tools", [])

    from pydantic import TypeAdapter, ValidationError

    any_tool_adapter = TypeAdapter(AnyToolConfig)

    if not tools_config:
        log.info(
            "%s No explicit tools configured in 'tools' list.", component.log_identifier
        )
    else:
        log.info(
            "%s Loading %d tool(s) from 'tools' list configuration...",
            component.log_identifier,
            len(tools_config),
        )
        for tool_config in tools_config:
            try:
                tool_config_model = any_tool_adapter.validate_python(tool_config)
                tool_type = tool_config_model.tool_type.lower()

                new_tools, new_builtins, new_cleanups = [], [], []

                if tool_type == "python":
                    (
                        new_tools,
                        new_builtins,
                        new_cleanups,
                    ) = await _load_python_tool(component, tool_config)
                elif tool_type == "builtin":
                    (
                        new_tools,
                        new_builtins,
                        new_cleanups,
                    ) = await _load_builtin_tool(component, tool_config)
                elif tool_type == "builtin-group":
                    (
                        new_tools,
                        new_builtins,
                        new_cleanups,
                    ) = await _load_builtin_group_tool(component, tool_config)
                elif tool_type == "mcp":
                    (
                        new_tools,
                        new_builtins,
                        new_cleanups,
                    ) = await _load_mcp_tool(component, tool_config)
                else:
                    log.warning(
                        "%s Unknown tool type '%s' in config: %s",
                        component.log_identifier,
                        tool_type,
                        tool_config,
                    )

                # Centralized name checking and result aggregation
                for tool in new_tools:
                    if isinstance(tool, EmbedResolvingMCPToolset):
                        # Special handling for MCPToolset which can load multiple tools
                        try:
                            mcp_tools = await tool.get_tools()
                            for mcp_tool in mcp_tools:
                                _check_and_register_tool_name(
                                    mcp_tool.name, "mcp", loaded_tool_names
                                )
                        except Exception as e:
                            log.error(
                                "%s Failed to discover tools from MCP server for name registration: %s",
                                component.log_identifier,
                                str(e),
                            )
                            raise
                    else:
                        tool_name = getattr(
                            tool, "name", getattr(tool, "__name__", None)
                        )
                        if tool_name:
                            _check_and_register_tool_name(
                                tool_name, tool_type, loaded_tool_names
                            )

                loaded_tools.extend(new_tools)
                enabled_builtin_tools.extend(new_builtins)
                # Prepend cleanup hooks to maintain LIFO execution order
                cleanup_hooks = new_cleanups + cleanup_hooks

            except Exception as e:
                log.error(
                    "%s Failed to load tool config %s: %s",
                    component.log_identifier,
                    tool_config,
                    e,
                )
                raise e

    # Load internal framework tools
    (
        internal_tools,
        internal_builtins,
        internal_cleanups,
    ) = _load_internal_tools(component, loaded_tool_names)
    loaded_tools.extend(internal_tools)
    enabled_builtin_tools.extend(internal_builtins)
    cleanup_hooks.extend(internal_cleanups)

    log.info(
        "%s Finished loading tools. Total tools for ADK: %d. Total SAM built-ins for prompt: %d. Total cleanup hooks: %d. Peer tools added dynamically.",
        component.log_identifier,
        len(loaded_tools),
        len(enabled_builtin_tools),
        len(cleanup_hooks),
    )
    return loaded_tools, enabled_builtin_tools, cleanup_hooks


def initialize_adk_agent(
    component,
    loaded_explicit_tools: List[Union[BaseTool, Callable]],
    enabled_builtin_tools: List[BuiltinTool],
) -> AppLlmAgent:
    """
    Initializes the ADK LlmAgent based on component configuration.
    Assigns callbacks for peer tool injection, dynamic instruction injection,
    artifact metadata injection, embed resolution, and logging.

    Args:
        component: The A2A_ADK_HostComponent instance.
        loaded_explicit_tools: The list of pre-loaded non-peer tools.

    Returns:
        An initialized LlmAgent instance.

    Raises:
        ValueError: If configuration is invalid.
        ImportError: If required dependencies are missing.
        Exception: For other initialization errors.
    """
    agent_name = component.get_config("agent_name")
    log.info(
        "%s Initializing ADK Agent '%s' (Peer tools & instructions added via callback)...",
        component.log_identifier,
        agent_name,
    )

    model_config = component.get_config("model")
    adk_model_instance: Union[str, BaseLlm]
    if isinstance(model_config, str):
        adk_model_instance = model_config
    elif isinstance(model_config, dict):
        if model_config.get("type") is None:
            # Use setdefault to add keys only if they are not already present in the YAML
            model_config.setdefault("num_retries", 3)
            model_config.setdefault("timeout", 120)
            log.info(
                "%s Applying default resilience settings for LiteLlm model (num_retries=%s, timeout=%s). These can be overridden in YAML.",
                component.log_identifier,
                model_config["num_retries"],
                model_config["timeout"],
            )

        try:

            adk_model_instance = LiteLlm(**model_config)
            log.info(
                "%s Initialized LiteLlm model: %s",
                component.log_identifier,
                model_config.get("model"),
            )
        except ImportError:
            log.error(
                "%s LiteLlm dependency not found. Cannot use dictionary model config.",
                component.log_identifier,
            )
            raise
        except Exception as e:
            log.error(
                "%s Failed to initialize model from dictionary config: %s",
                component.log_identifier,
                e,
            )
            raise
    else:
        raise ValueError(
            f"{component.log_identifier} Invalid 'model' configuration type: {type(model_config)}"
        )

    instruction = component._resolve_instruction_provider(
        component.get_config("instruction", "")
    )
    global_instruction = component._resolve_instruction_provider(
        component.get_config("global_instruction", "")
    )
    planner = component.get_config("planner")
    code_executor = component.get_config("code_executor")

    try:
        agent = AppLlmAgent(
            name=agent_name,
            model=adk_model_instance,
            instruction=instruction,
            global_instruction=global_instruction,
            tools=loaded_explicit_tools,
            planner=planner,
            code_executor=code_executor,
        )

        agent.host_component = component
        log.debug(
            "%s Attached host_component reference to AppLlmAgent.",
            component.log_identifier,
        )
        callbacks_in_order_for_before_model = []

        callbacks_in_order_for_before_model.append(
            adk_callbacks.repair_history_callback
        )
        log.info(
            "%s Added repair_history_callback to before_model chain.",
            component.log_identifier,
        )

        if hasattr(component, "_inject_peer_tools_callback"):
            callbacks_in_order_for_before_model.append(
                component._inject_peer_tools_callback
            )
            log.info(
                "%s Added _inject_peer_tools_callback to before_model chain.",
                component.log_identifier,
            )

        if hasattr(component, "_filter_tools_by_capability_callback"):
            callbacks_in_order_for_before_model.append(
                component._filter_tools_by_capability_callback
            )
            log.info(
                "%s Added _filter_tools_by_capability_callback to before_model chain.",
                component.log_identifier,
            )
        if hasattr(component, "_inject_gateway_instructions_callback"):
            callbacks_in_order_for_before_model.append(
                component._inject_gateway_instructions_callback
            )
            log.info(
                "%s Added _inject_gateway_instructions_callback to before_model chain.",
                component.log_identifier,
            )

        dynamic_instruction_callback_with_component = functools.partial(
            adk_callbacks.inject_dynamic_instructions_callback,
            host_component=component,
            active_builtin_tools=enabled_builtin_tools,
        )
        callbacks_in_order_for_before_model.append(
            dynamic_instruction_callback_with_component
        )
        log.info(
            "%s Added inject_dynamic_instructions_callback to before_model chain.",
            component.log_identifier,
        )

        solace_llm_trigger_callback_with_component = functools.partial(
            adk_callbacks.solace_llm_invocation_callback, host_component=component
        )

        def final_before_model_wrapper(
            callback_context: CallbackContext, llm_request: LlmRequest
        ) -> Optional[LlmResponse]:
            early_response: Optional[LlmResponse] = None
            for cb_func in callbacks_in_order_for_before_model:
                response = cb_func(callback_context, llm_request)
                if response:
                    early_response = response
                    break

            solace_llm_trigger_callback_with_component(callback_context, llm_request)

            if early_response:
                return early_response

            return None

        agent.before_model_callback = final_before_model_wrapper
        log.info(
            "%s Final before_model_callback chain (Solace logging now occurs last) assigned to agent.",
            component.log_identifier,
        )

        tool_invocation_start_cb_with_component = functools.partial(
            adk_callbacks.notify_tool_invocation_start_callback,
            host_component=component,
        )
        agent.before_tool_callback = tool_invocation_start_cb_with_component
        log.info(
            "%s Assigned notify_tool_invocation_start_callback as before_tool_callback.",
            component.log_identifier,
        )

        large_response_cb_with_component = functools.partial(
            adk_callbacks.manage_large_mcp_tool_responses_callback,
            host_component=component,
        )
        metadata_injection_cb_with_component = functools.partial(
            adk_callbacks.after_tool_callback_inject_metadata, host_component=component
        )
        track_artifacts_cb_with_component = functools.partial(
            adk_callbacks.track_produced_artifacts_callback, host_component=component
        )
        notify_tool_result_cb_with_component = functools.partial(
            adk_callbacks.notify_tool_execution_result_callback,
            host_component=component,
        )

        async def chained_after_tool_callback(
            tool: BaseTool,
            args: Dict,
            tool_context: ToolContext,
            tool_response: Dict,
        ) -> Optional[Dict]:
            log.debug(
                "%s Tool callback chain started for tool: %s, response type: %s",
                component.log_identifier,
                tool.name,
                type(tool_response).__name__,
            )

            try:
                # First, notify the UI about the raw result.
                # This is a fire-and-forget notification that does not modify the response.
                notify_tool_result_cb_with_component(
                    tool, args, tool_context, tool_response
                )

                # Now, proceed with the existing chain that modifies the response for the LLM.
                processed_by_large_handler = await large_response_cb_with_component(
                    tool, args, tool_context, tool_response
                )
                response_for_metadata_injector = (
                    processed_by_large_handler
                    if processed_by_large_handler is not None
                    else tool_response
                )

                final_response_after_metadata = (
                    await metadata_injection_cb_with_component(
                        tool, args, tool_context, response_for_metadata_injector
                    )
                )

                final_result = (
                    final_response_after_metadata
                    if final_response_after_metadata is not None
                    else response_for_metadata_injector
                )

                # Track produced artifacts. This callback does not modify the response.
                await track_artifacts_cb_with_component(
                    tool, args, tool_context, final_result
                )

                log.debug(
                    "%s Tool callback chain completed for tool: %s, final response type: %s",
                    component.log_identifier,
                    tool.name,
                    type(final_result).__name__,
                )

                return final_result

            except Exception as e:
                log.exception(
                    "%s Error in tool callback chain for tool %s: %s",
                    component.log_identifier,
                    tool.name,
                    e,
                )
                return tool_response

        agent.after_tool_callback = chained_after_tool_callback
        log.info(
            "%s Chained 'manage_large_mcp_tool_responses_callback' and 'after_tool_callback_inject_metadata' as after_tool_callback.",
            component.log_identifier,
        )

        # --- After Model Callbacks Chain ---
        # The callbacks are executed in the order they are added to this list.
        callbacks_in_order_for_after_model = []

        # 1. Fenced Artifact Block Processing (must run before auto-continue)
        artifact_block_cb = functools.partial(
            adk_callbacks.process_artifact_blocks_callback, host_component=component
        )
        callbacks_in_order_for_after_model.append(artifact_block_cb)
        log.info(
            "%s Added process_artifact_blocks_callback to after_model chain.",
            component.log_identifier,
        )

        # 2. Auto-Continuation (may short-circuit the chain)
        auto_continue_cb = functools.partial(
            adk_callbacks.auto_continue_on_max_tokens_callback, host_component=component
        )
        callbacks_in_order_for_after_model.append(auto_continue_cb)
        log.info(
            "%s Added auto_continue_on_max_tokens_callback to after_model chain.",
            component.log_identifier,
        )

        # 3. Solace LLM Response Logging
        solace_llm_response_cb = functools.partial(
            adk_callbacks.solace_llm_response_callback, host_component=component
        )
        callbacks_in_order_for_after_model.append(solace_llm_response_cb)

        # 4. Chunk Logging
        log_chunk_cb = functools.partial(
            adk_callbacks.log_streaming_chunk_callback, host_component=component
        )
        callbacks_in_order_for_after_model.append(log_chunk_cb)

        async def final_after_model_wrapper(
            callback_context: CallbackContext, llm_response: LlmResponse
        ) -> Optional[LlmResponse]:
            for cb_func in callbacks_in_order_for_after_model:
                # Await async callbacks, call sync callbacks
                if inspect.iscoroutinefunction(cb_func):
                    response = await cb_func(callback_context, llm_response)
                else:
                    response = cb_func(callback_context, llm_response)

                # If a callback returns a response, it hijacks the flow.
                if response:
                    return response
            return None

        agent.after_model_callback = final_after_model_wrapper
        log.info(
            "%s Chained all after_model_callbacks and assigned to agent.",
            component.log_identifier,
        )

        log.info(
            "%s ADK Agent '%s' created. Callbacks assigned.",
            component.log_identifier,
            agent_name,
        )
        return agent
    except Exception as e:
        log.error(
            "%s Failed to create ADK Agent '%s': %s",
            component.log_identifier,
            agent_name,
            e,
        )
        raise


def initialize_adk_runner(component) -> Runner:
    """
    Initializes the ADK Runner.

    Args:
        component: The A2A_ADK_HostComponent instance.

    Returns:
        An initialized Runner instance.

    Raises:
        Exception: For runner initialization errors.
    """
    agent_name = component.get_config("agent_name")
    log.info(
        "%s Initializing ADK Runner for agent '%s'...",
        component.log_identifier,
        agent_name,
    )
    try:
        runner = Runner(
            app_name=agent_name,
            agent=component.adk_agent,
            session_service=component.session_service,
            artifact_service=component.artifact_service,
            memory_service=component.memory_service,
        )
        log.info("%s ADK Runner created successfully.", component.log_identifier)
        return runner
    except Exception as e:
        log.error("%s Failed to create ADK Runner: %s", component.log_identifier, e)
        raise
