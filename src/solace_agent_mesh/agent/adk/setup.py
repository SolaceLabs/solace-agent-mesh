"""
Handles ADK Agent and Runner initialization, including tool loading and callback assignment.
"""

from typing import Dict, List, Optional, Union, Callable, Tuple, Set
import functools
import inspect
from solace_ai_connector.common.log import log
from solace_ai_connector.common.utils import import_module

from .app_llm_agent import AppLlmAgent
from .tool_wrapper import ADKToolWrapper
from google.adk.runners import Runner
from google.adk.models import BaseLlm
from google.adk.tools import BaseTool, ToolContext
from google.adk import tools as adk_tools_module
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams, StdioConnectionParams

from mcp import StdioServerParameters

from ..tools.registry import tool_registry
from ..tools.tool_definition import BuiltinTool


from ...agent.adk import callbacks as adk_callbacks
from ...agent.adk.models.lite_llm import LiteLlm


async def load_adk_tools(
    component,
) -> Tuple[List[Union[BaseTool, Callable]], List[BuiltinTool]]:
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

    Raises:
        ImportError: If a configured tool or its dependencies cannot be loaded.
    """
    loaded_tools: List[Union[BaseTool, Callable]] = []
    enabled_builtin_tools: List[BuiltinTool] = []
    loaded_tool_names: Set[str] = set()
    tools_config = component.get_config("tools", [])

    if not tools_config:
        log.info(
            "%s No explicit tools configured in 'tools' list.", component.log_identifier
        )
    else:
        log.info(
            "%s Loading tools from 'tools' list configuration...",
            component.log_identifier,
        )
        for tool_config in tools_config:
            tool_type = tool_config.get("tool_type", "").lower()

            try:
                if tool_type == "python":
                    module_name = tool_config.get("component_module")
                    function_name = tool_config.get("function_name")
                    tool_name = tool_config.get("tool_name")
                    tool_description = tool_config.get("tool_description")
                    base_path = tool_config.get("component_base_path")
                    if not module_name or not function_name:
                        raise ValueError(
                            "'component_module' and 'function_name' required for python tool."
                        )

                    module = import_module(module_name, base_path=base_path)
                    func = getattr(module, function_name)
                    if not callable(func):
                        raise TypeError(
                            f"'{function_name}' in module '{module_name}' is not callable."
                        )

                    specific_tool_config = tool_config.get("tool_config")
                    tool_callable = ADKToolWrapper(
                        func,
                        specific_tool_config,
                        function_name,
                        raw_string_args=tool_config.get("raw_string_args", []),
                    )

                    if tool_name:
                        function_name = tool_name
                        tool_callable.__name__ = tool_name

                    if tool_description:
                        tool_callable.__doc__ = tool_description

                    if function_name not in loaded_tool_names:
                        loaded_tools.append(tool_callable)
                        loaded_tool_names.add(function_name)
                        log.info(
                            "%s Loaded Python tool: %s from %s.",
                            component.log_identifier,
                            function_name,
                            module_name,
                        )
                    else:
                        log.debug(
                            "%s Python tool '%s' already loaded. Skipping duplicate.",
                            component.log_identifier,
                            function_name,
                        )

                elif tool_type == "builtin":
                    tool_name = tool_config.get("tool_name")
                    if not tool_name:
                        raise ValueError("'tool_name' required for builtin tool.")

                    if tool_name in loaded_tool_names:
                        log.debug(
                            "%s Tool '%s' already loaded. Skipping duplicate.",
                            component.log_identifier,
                            tool_name,
                        )
                        continue

                    sam_tool_def = tool_registry.get_tool_by_name(tool_name)
                    if sam_tool_def:
                        specific_tool_config = tool_config.get("tool_config")
                        tool_callable = ADKToolWrapper(
                            sam_tool_def.implementation,
                            specific_tool_config,
                            sam_tool_def.name,
                            raw_string_args=sam_tool_def.raw_string_args,
                        )
                        loaded_tools.append(tool_callable)
                        enabled_builtin_tools.append(sam_tool_def)
                        loaded_tool_names.add(sam_tool_def.name)
                        log.info(
                            "%s Loaded SAM built-in tool: %s",
                            component.log_identifier,
                            sam_tool_def.name,
                        )
                        continue

                    adk_tool = getattr(adk_tools_module, tool_name, None)
                    if adk_tool and isinstance(adk_tool, (BaseTool, Callable)):
                        loaded_tools.append(adk_tool)
                        loaded_tool_names.add(tool_name)
                        log.info(
                            "%s Loaded ADK built-in tool: %s",
                            component.log_identifier,
                            tool_name,
                        )
                        continue

                    raise ValueError(
                        f"Built-in tool '{tool_name}' not found in SAM or ADK registry."
                    )

                elif tool_type == "builtin-group":
                    group_name = tool_config.get("group_name")
                    if not group_name:
                        raise ValueError("'group_name' required for builtin-group.")

                    tools_in_group = tool_registry.get_tools_by_category(group_name)
                    if not tools_in_group:
                        log.warning("No tools found for built-in group: %s", group_name)
                        continue

                    initializers_to_run: Dict[Callable, Dict] = {}
                    for tool_def in tools_in_group:
                        if (
                            tool_def.initializer
                            and tool_def.initializer not in initializers_to_run
                        ):
                            initializers_to_run[tool_def.initializer] = tool_config.get(
                                "config", {}
                            )

                    for init_func, init_config in initializers_to_run.items():
                        try:
                            log.info(
                                "%s Running initializer '%s' for tool group '%s'.",
                                component.log_identifier,
                                init_func.__name__,
                                group_name,
                            )
                            init_func(component, init_config)
                            log.info(
                                "%s Successfully executed initializer '%s' for tool group '%s'.",
                                component.log_identifier,
                                init_func.__name__,
                                group_name,
                            )
                        except Exception as e:
                            log.exception(
                                "%s Failed to run initializer '%s' for tool group '%s': %s",
                                component.log_identifier,
                                init_func.__name__,
                                group_name,
                                e,
                            )
                            raise e

                    group_tool_count = 0
                    for tool_def in tools_in_group:
                        if tool_def.name not in loaded_tool_names:
                            specific_tool_config = tool_config.get(
                                "tool_configs", {}
                            ).get(tool_def.name)
                            tool_callable = ADKToolWrapper(
                                tool_def.implementation,
                                specific_tool_config,
                                tool_def.name,
                                raw_string_args=tool_def.raw_string_args,
                            )
                            loaded_tools.append(tool_callable)
                            enabled_builtin_tools.append(tool_def)
                            loaded_tool_names.add(tool_def.name)
                            group_tool_count += 1
                    log.info(
                        "Loaded %d tools from built-in group: %s",
                        group_tool_count,
                        group_name,
                    )

                elif tool_type == "mcp":
                    tool_name = tool_config.get("tool_name")
                    if not tool_name:
                        log.info(
                            "%s No specific 'tool_name' for MCP tool, will load all tools from server unless tool_filter is specified in MCPToolset itself.",
                            component.log_identifier,
                        )

                    connection_params_config = tool_config.get("connection_params")
                    if not connection_params_config:
                        raise ValueError("'connection_params' required for mcp tool.")

                    connection_type = connection_params_config.get("type", "").lower()
                    connection_args = {
                        k: v for k, v in connection_params_config.items() if k != "type"
                    }
                    connection_args["timeout"] = connection_args.get("timeout", 30)


                    environment_variables = tool_config.get("environment_variables")
                    env_param = {}
                    if connection_type == "stdio" and environment_variables:
                        if isinstance(environment_variables, dict):
                            env_param = environment_variables
                            log.debug(
                                "%s Found environment_variables for stdio MCP tool.",
                                component.log_identifier,
                            )
                        else:
                            log.warning(
                                "%s 'environment_variables' provided for stdio MCP tool but it is not a dictionary. Ignoring.",
                                component.log_identifier,
                            )

                    if connection_type == "stdio":
                        cmd_arg = connection_args.get("command")
                        args_list = connection_args.get("args", [])
                        if isinstance(cmd_arg, list):
                            command_str = " ".join(cmd_arg)
                        elif isinstance(cmd_arg, str):
                            command_str = cmd_arg
                        else:
                            raise ValueError(
                                f"MCP tool 'command' parameter must be a string or a list of strings, got {type(cmd_arg)}"
                            )
                        if not isinstance(args_list, list):
                            raise ValueError(
                                f"MCP tool 'args' parameter must be a list, got {type(args_list)}"
                            )
                        final_connection_args = {
                            k: v
                            for k, v in connection_args.items()
                            if k not in ["command", "args", "timeout"]
                        }
                        connection_params = StdioConnectionParams(
                            server_params=StdioServerParameters(
                                command=command_str,
                                args=args_list,
                                **final_connection_args,
                                env=env_param if env_param else None,
                            ),
                            timeout=connection_args.get("timeout")
                        )
                        
                    elif connection_type == "sse":
                        connection_params = SseServerParams(**connection_args)
                    else:
                        raise ValueError(
                            f"Unsupported MCP connection type: {connection_type}"
                        )

                    tool_filter_list = [tool_name] if tool_name else None
                    if tool_filter_list:
                        log.info(
                            "%s MCP tool config specifies tool_name: '%s'. Applying as tool_filter.",
                            component.log_identifier,
                            tool_name,
                        )

                    mcp_toolset_instance = MCPToolset(
                        connection_params=connection_params,
                        tool_filter=tool_filter_list,
                    )
                    loaded_tools.append(mcp_toolset_instance)
                    log.info(
                        "%s Initialized MCPToolset (filter: %s) for server: %s",
                        component.log_identifier,
                        (tool_filter_list if tool_filter_list else "none (all tools)"),
                        connection_params,
                    )

                else:
                    log.warning(
                        "%s Unknown tool type '%s' in config: %s",
                        component.log_identifier,
                        tool_type,
                        tool_config,
                    )

            except Exception as e:
                log.error(
                    "%s Failed to load tool config %s: %s",
                    component.log_identifier,
                    tool_config,
                    e,
                )
                raise e

    internal_tool_names = ["_notify_artifact_save"]
    if component.get_config("enable_auto_continuation", True):
        internal_tool_names.append("_continue_generation")

    for tool_name in internal_tool_names:
        if tool_name in loaded_tool_names:
            log.debug(
                "%s Internal tool '%s' was already loaded explicitly. Skipping implicit load.",
                component.log_identifier,
                tool_name,
            )
            continue

        tool_def = tool_registry.get_tool_by_name(tool_name)
        if tool_def:
            # Wrap the implementation to ensure its description is passed to the LLM
            tool_callable = ADKToolWrapper(
                tool_def.implementation,
                None,  # No specific config for internal tools
                tool_def.name,
            )

            tool_callable.__doc__ = tool_def.description

            loaded_tools.append(tool_callable)
            enabled_builtin_tools.append(tool_def)
            loaded_tool_names.add(tool_def.name)
            log.info(
                "%s Implicitly loaded internal framework tool: %s",
                component.log_identifier,
                tool_def.name,
            )
        else:
            log.warning(
                "%s Could not find internal framework tool '%s' in registry. Related features may not work.",
                component.log_identifier,
                tool_name,
            )

    log.info(
        "%s Finished loading tools. Total tools for ADK: %d. Total SAM built-ins for prompt: %d. Peer tools added dynamically.",
        component.log_identifier,
        len(loaded_tools),
        len(enabled_builtin_tools),
    )
    return loaded_tools, enabled_builtin_tools


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
