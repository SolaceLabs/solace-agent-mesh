"""
Handles ADK Agent and Runner initialization, including tool loading and callback assignment.
"""

import functools
import inspect
import logging
import os
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from google.adk import tools as adk_tools_module
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.tools import BaseTool, ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseServerParams,
    StdioConnectionParams,
    StreamableHTTPServerParams,
)
from mcp import StdioServerParameters
from solace_ai_connector.common.utils import import_module

from ...agent.adk import callbacks as adk_callbacks
from ...agent.adk.models.lite_llm import LiteLlm
from ...common.utils.type_utils import is_subclass_by_name
from ..tools.dynamic_tool import DynamicTool, DynamicToolProvider
from ..tools.registry import tool_registry
from ..tools.tool_config_types import (
    AnyToolConfig,
    BuiltinGroupToolConfig,
    BuiltinToolConfig,
    McpToolConfig,
    PythonToolConfig,
)
from ..tools.tool_definition import BuiltinTool
from .app_llm_agent import AppLlmAgent
from .embed_resolving_mcp_toolset import EmbedResolvingMCPToolset
from .mcp_ssl_config import SslConfig
from .tool_wrapper import ADKToolWrapper

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)

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


async def _create_python_tool_lifecycle_hooks(
    component: "SamAgentComponent",
    tool_config_model: "PythonToolConfig",
    loaded_python_tools: List[Union[BaseTool, Callable]],
) -> List[Callable]:
    """
    Executes init hooks and collects cleanup hooks for a Python tool.
    Handles both YAML-defined hooks and class-based init/cleanup methods.
    Returns cleanup hooks in LIFO order.
    """
    module_name = tool_config_model.component_module
    base_path = tool_config_model.component_base_path
    cleanup_hooks = []

    # 1. YAML Init (runs first)
    await _execute_lifecycle_hook(
        component,
        tool_config_model.init_function,
        module_name,
        base_path,
        tool_config_model,
    )

    # 2. DynamicTool/Provider Init (runs second)
    for tool_instance in loaded_python_tools:
        if is_subclass_by_name(type(tool_instance), "DynamicTool"):
            log.info(
                "%s Executing .init() method for DynamicTool '%s'.",
                component.log_identifier,
                tool_instance.tool_name,
            )
            await tool_instance.init(component, tool_config_model)

    # 3. Collect Cleanup Hooks (in reverse order of init)
    # Class-based cleanup hook (will be executed first)
    for tool_instance in loaded_python_tools:
        if is_subclass_by_name(type(tool_instance), "DynamicTool"):
            cleanup_hooks.append(
                functools.partial(
                    tool_instance.cleanup, component, tool_config_model
                )
            )

    # YAML-based cleanup hook (will be executed second)
    yaml_cleanup_partial = _create_cleanup_partial(
        component,
        tool_config_model.cleanup_function,
        module_name,
        base_path,
        tool_config_model,
    )
    if yaml_cleanup_partial:
        cleanup_hooks.append(yaml_cleanup_partial)

    # Return in LIFO order relative to init
    return list(reversed(cleanup_hooks))


def _load_python_class_based_tool(
    module: Any,
    tool_config: Dict,
    component: "SamAgentComponent",
) -> List[DynamicTool]:
    """
    Loads a class-based tool, which can be a single DynamicTool or a
    DynamicToolProvider that generates multiple tools.
    """
    from pydantic import BaseModel, ValidationError

    specific_tool_config = tool_config.get("tool_config")
    dynamic_tools: List[DynamicTool] = []
    module_name = module.__name__

    # Determine the class to load
    tool_class = None
    class_name = tool_config.get("class_name")
    if class_name:
        tool_class = getattr(module, class_name)
    else:
        # Auto-discover: provider first, then single tool
        tool_class = _find_dynamic_tool_provider_class(module)
        if not tool_class:
            tool_class = _find_dynamic_tool_class(module)

    if not tool_class:
        raise TypeError(
            f"Module '{module_name}' does not contain a 'function_name' or 'class_name' to load, "
            "and no DynamicTool or DynamicToolProvider subclass could be auto-discovered."
        )

    # Check for a Pydantic model declaration on the tool class
    config_model: Optional[Type["BaseModel"]] = getattr(
        tool_class, "config_model", None
    )
    validated_config: Union[dict, "BaseModel"] = specific_tool_config

    if config_model:
        log.debug(
            "%s Found config_model '%s' for tool class '%s'. Validating...",
            component.log_identifier,
            config_model.__name__,
            tool_class.__name__,
        )
        try:
            # Validate the raw dict and get a Pydantic model instance
            validated_config = config_model.model_validate(specific_tool_config or {})
            log.debug(
                "%s Successfully validated tool_config for '%s'.",
                component.log_identifier,
                tool_class.__name__,
            )
        except ValidationError as e:
            # Provide a clear error message and raise
            error_msg = (
                f"Configuration error for tool '{tool_class.__name__}' from module '{module_name}'. "
                f"The provided 'tool_config' in your YAML is invalid:\n{e}"
            )
            log.error("%s %s", component.log_identifier, error_msg)
            raise ValueError(error_msg) from e

    # Instantiate tools from the class
    if is_subclass_by_name(tool_class, "DynamicToolProvider"):
        provider_instance = tool_class()
        dynamic_tools = provider_instance.get_all_tools_for_framework(
            tool_config=validated_config
        )
        log.info(
            "%s Loaded %d tools from DynamicToolProvider '%s' in %s",
            component.log_identifier,
            len(dynamic_tools),
            tool_class.__name__,
            module_name,
        )
    elif is_subclass_by_name(tool_class, "DynamicTool"):
        tool_instance = tool_class(tool_config=validated_config)
        dynamic_tools = [tool_instance]
    else:
        raise TypeError(
            f"Class '{tool_class.__name__}' in module '{module_name}' is not a valid "
            "DynamicTool or DynamicToolProvider subclass."
        )

    # Post-process all generated tools
    for tool in dynamic_tools:
        tool.origin = "dynamic"
        declaration = tool._get_declaration()
        if not declaration:
            log.warning(
                "Dynamic tool '%s' from module '%s' did not generate a valid declaration. Skipping.",
                tool.__class__.__name__,
                module_name,
            )
            continue
        log.info(
            "%s Loaded dynamic tool: %s from %s",
            component.log_identifier,
            declaration.name,
            module_name,
        )

    return dynamic_tools


async def _load_python_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    from pydantic import TypeAdapter

    python_tool_adapter = TypeAdapter(PythonToolConfig)
    tool_config_model = python_tool_adapter.validate_python(tool_config)

    module_name = tool_config_model.component_module
    base_path = tool_config_model.component_base_path
    if not module_name:
        raise ValueError("'component_module' is required for python tools.")
    module = import_module(module_name, base_path=base_path)

    loaded_python_tools: List[Union[BaseTool, Callable]] = []

    # Case 1: Simple function-based tool
    if tool_config_model.function_name:
        func = getattr(module, tool_config_model.function_name)
        if not callable(func):
            raise TypeError(
                f"'{tool_config_model.function_name}' in module '{module_name}' is not callable."
            )

        tool_callable = ADKToolWrapper(
            func,
            tool_config_model.tool_config,
            tool_config_model.function_name,
            origin="python",
            raw_string_args=tool_config_model.raw_string_args,
        )

        if tool_config_model.tool_name:
            tool_callable.__name__ = tool_config_model.tool_name
        if tool_config_model.tool_description:
            tool_callable.__doc__ = tool_config_model.tool_description

        loaded_python_tools.append(tool_callable)
        log.info(
            "%s Loaded Python tool: %s from %s.",
            component.log_identifier,
            tool_callable.__name__,
            module_name,
        )
    # Case 2: Advanced class-based dynamic tool or provider
    else:
        dynamic_tools = _load_python_class_based_tool(module, tool_config, component)
        loaded_python_tools.extend(dynamic_tools)

    # --- Lifecycle Hook Execution for all Python Tools ---
    cleanup_hooks = await _create_python_tool_lifecycle_hooks(
        component, tool_config_model, loaded_python_tools
    )

    return loaded_python_tools, [], cleanup_hooks

async def _load_builtin_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    """Loads a single built-in tool from the SAM or ADK tool registry."""
    from pydantic import TypeAdapter

    builtin_tool_adapter = TypeAdapter(BuiltinToolConfig)
    tool_config_model = builtin_tool_adapter.validate_python(tool_config)

    tool_name = tool_config_model.tool_name
    if not tool_name:
        raise ValueError("'tool_name' required for builtin tool.")

    # Check SAM registry first
    sam_tool_def = tool_registry.get_tool_by_name(tool_name)
    if sam_tool_def:
        tool_callable = ADKToolWrapper(
            sam_tool_def.implementation,
            tool_config_model.tool_config,
            sam_tool_def.name,
            origin="builtin",
            raw_string_args=sam_tool_def.raw_string_args,
        )
        log.info(
            "%s Loaded SAM built-in tool: %s",
            component.log_identifier,
            sam_tool_def.name,
        )
        return [tool_callable], [sam_tool_def], []

    # Fallback to ADK built-in tools module
    adk_tool = getattr(adk_tools_module, tool_name, None)
    if adk_tool and isinstance(adk_tool, (BaseTool, Callable)):
        adk_tool.origin = "adk_builtin"
        log.info(
            "%s Loaded ADK built-in tool: %s",
            component.log_identifier,
            tool_name,
        )
        return [adk_tool], [], []

    raise ValueError(
        f"Built-in tool '{tool_name}' not found in SAM or ADK registry."
    )

async def _load_builtin_group_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    """Loads a group of built-in tools by category from the SAM tool registry."""
    from pydantic import TypeAdapter

    group_tool_adapter = TypeAdapter(BuiltinGroupToolConfig)
    tool_config_model = group_tool_adapter.validate_python(tool_config)

    group_name = tool_config_model.group_name
    if not group_name:
        raise ValueError("'group_name' required for builtin-group.")

    tools_in_group = tool_registry.get_tools_by_category(group_name)
    if not tools_in_group:
        log.warning("No tools found for built-in group: %s", group_name)
        return [], [], []

    # Run initializers for the group
    initializers_to_run: Dict[Callable, Dict] = {}
    for tool_def in tools_in_group:
        if (
            tool_def.initializer
            and tool_def.initializer not in initializers_to_run
        ):
            initializers_to_run[tool_def.initializer] = tool_config_model.tool_config

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

    loaded_tools: List[Union[BaseTool, Callable]] = []
    enabled_builtin_tools: List[BuiltinTool] = []
    for tool_def in tools_in_group:
        specific_tool_config = tool_config_model.tool_config.get(tool_def.name)
        tool_callable = ADKToolWrapper(
            tool_def.implementation,
            specific_tool_config,
            tool_def.name,
            origin="builtin",
            raw_string_args=tool_def.raw_string_args,
        )
        loaded_tools.append(tool_callable)
        enabled_builtin_tools.append(tool_def)

    log.info(
        "Loaded %d tools from built-in group: %s",
        len(loaded_tools),
        group_name,
    )
    return loaded_tools, enabled_builtin_tools, []

def validate_filesystem_path(path, log_identifier=""):
    """
    Validates that a filesystem path exists and is accessible.
    
    Args:
        path: The filesystem path to validate
        log_identifier: Optional identifier for logging
        
    Returns:
        bool: True if the path exists and is accessible, False otherwise
        
    Raises:
        ValueError: If the path doesn't exist or isn't accessible
    """
    if not path:
        raise ValueError(f"{log_identifier} Filesystem path is empty or None")
        
    if not os.path.exists(path):
        raise ValueError(f"{log_identifier} Filesystem path does not exist: {path}")
        
    if not os.path.isdir(path):
        raise ValueError(f"{log_identifier} Filesystem path is not a directory: {path}")
        
    # Check if the directory is readable and writable
    if not os.access(path, os.R_OK | os.W_OK):
        raise ValueError(f"{log_identifier} Filesystem path is not readable and writable: {path}")
        
    return True

async def _load_mcp_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    """Loads an MCP toolset based on connection parameters."""
    from pydantic import TypeAdapter

    mcp_tool_adapter = TypeAdapter(McpToolConfig)
    tool_config_model = mcp_tool_adapter.validate_python(tool_config)

    connection_params_config = tool_config_model.connection_params
    if not connection_params_config:
        raise ValueError("'connection_params' required for mcp tool.")

    connection_type = connection_params_config.get("type", "").lower()
    connection_args = {
        k: v for k, v in connection_params_config.items() if k != "type"
    }
    connection_args["timeout"] = connection_args.get("timeout", 30)

    # Extract SSL configuration if provided
    ssl_config_dict = connection_args.pop("ssl_config", None)
    ssl_config = None
    if ssl_config_dict and isinstance(ssl_config_dict, dict):
        ssl_verify = ssl_config_dict.get("verify", True)
        ssl_ca_bundle = ssl_config_dict.get("ca_bundle")

        # Log warning when SSL verification is disabled
        if ssl_verify is False:
            log.warning(
                "%s SSL verification is disabled for MCP connection. "
                "This should only be used in development environments.",
                component.log_identifier,
            )

        ssl_config = SslConfig(verify=ssl_verify, ca_bundle=ssl_ca_bundle)
        log.debug(
            "%s SSL configuration for MCP tool: verify=%s, ca_bundle=%s",
            component.log_identifier,
            ssl_verify,
            ssl_ca_bundle,
        )

    environment_variables = tool_config_model.environment_variables
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
            
        # Check if this is the filesystem MCP server
        if args_list and any("@modelcontextprotocol/server-filesystem" in arg for arg in args_list):
            # Find the index of the server-filesystem argument
            server_fs_index = -1
            for i, arg in enumerate(args_list):
                if "@modelcontextprotocol/server-filesystem" in arg:
                    server_fs_index = i
                    break
            
            # All arguments after server-filesystem are directory paths
            if server_fs_index >= 0 and server_fs_index + 1 < len(args_list):
                directory_paths = args_list[server_fs_index + 1:]
                
                for path in directory_paths:
                    try:
                        validate_filesystem_path(path, log_identifier=component.log_identifier)
                        log.info(
                            "%s Validated filesystem path for MCP server: %s",
                            component.log_identifier,
                            path
                        )
                    except ValueError as e:
                        log.error("%s", str(e))
                        raise ValueError(f"MCP filesystem server path validation failed: {e}")
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
            timeout=connection_args.get("timeout"),
        )

    elif connection_type == "sse":
        connection_params = SseServerParams(**connection_args)
    elif connection_type == "streamable-http":
        connection_params = StreamableHTTPServerParams(**connection_args)
    else:
        raise ValueError(f"Unsupported MCP connection type: {connection_type}")

    tool_filter_list = (
        [tool_config_model.tool_name] if tool_config_model.tool_name else None
    )
    if tool_filter_list:
        log.info(
            "%s MCP tool config specifies tool_name: '%s'. Applying as tool_filter.",
            component.log_identifier,
            tool_config_model.tool_name,
        )

    additional_params = {}
    try:
        from solace_agent_mesh_enterprise.auth.tool_configurator import (
            configure_mcp_tool,
        )

        try:
            # Call the tool configurator with MCP-specific context
            additional_params = configure_mcp_tool(
                tool_type="mcp",
                tool_config=tool_config,
                connection_params=connection_params,
                tool_filter=tool_filter_list,
            )
        except Exception as e:
            log.error(
                "%s Tool configurator failed for %s: %s",
                component.log_identifier,
                tool_config.get("name", "unknown"),
                e,
            )
            # Continue with normal tool creation if configurator fails
            additional_params = {}
    except ImportError:
        pass

    # Create the EmbedResolvingMCPToolset with base parameters
    toolset_params = {
        "connection_params": connection_params,
        "tool_filter": tool_filter_list,
        "tool_config": tool_config,
        "ssl_config": ssl_config,
    }

    # Merge additional parameters from configurator
    toolset_params.update(additional_params)

    mcp_toolset_instance = EmbedResolvingMCPToolset(**toolset_params)
    mcp_toolset_instance.origin = "mcp"

    log.info(
        "%s Initialized MCPToolset (filter: %s) for server: %s",
        component.log_identifier,
        (tool_filter_list if tool_filter_list else "none (all tools)"),
        connection_params,
    )

    return [mcp_toolset_instance], [], []


async def _load_openapi_tool(component: "SamAgentComponent", tool_config: Dict) -> ToolLoadingResult:
    """
    Loads an OpenAPI toolset by delegating to the enterprise configurator.

    This function validates the tool configuration and attempts to load the OpenAPI tool
    using the enterprise package. If the enterprise package is not available, it logs a
    warning and returns empty results.

    Args:
        component: The SamAgentComponent instance
        tool_config: Dictionary containing the tool's configuration

    Returns:
        ToolLoadingResult: Tuple of (tools, builtins, cleanup_hooks)
                          Returns ([], [], []) if enterprise package not available
    """
    from pydantic import TypeAdapter

    from ..tools.tool_config_types import OpenApiToolConfig

    # Validate basic tool configuration structure
    openapi_tool_adapter = TypeAdapter(OpenApiToolConfig)
    try:
        tool_config_model = openapi_tool_adapter.validate_python(tool_config)
    except Exception as e:
        log.error(
            "%s Invalid OpenAPI tool configuration: %s",
            component.log_identifier,
            e,
        )
        raise

    # Try to load the tool using the enterprise configurator
    try:
        from solace_agent_mesh_enterprise.auth.tool_configurator import (
            configure_openapi_tool,
        )

        try:
            openapi_toolset = configure_openapi_tool(
                tool_type="openapi",
                tool_config=tool_config,
            )
            openapi_toolset.origin = "openapi"

            log.info(
                "%s Loaded OpenAPI toolset via enterprise configurator",
                component.log_identifier,
            )

            return [openapi_toolset], [], []

        except Exception as e:
            log.error(
                "%s Failed to create OpenAPI tool %s: %s",
                component.log_identifier,
                tool_config.get("name", "unknown"),
                e,
            )
            raise

    except ImportError:
        log.warning(
            "%s OpenAPI tools require the solace-agent-mesh-enterprise package. "
            "Skipping tool configuration: %s",
            component.log_identifier,
            tool_config.get("name", "unknown"),
        )
        return [], [], []


def _load_internal_tools(component: "SamAgentComponent", loaded_tool_names: Set[str]) -> ToolLoadingResult:
    """Loads internal framework tools that are not explicitly configured by the user."""
    loaded_tools: List[Union[BaseTool, Callable]] = []
    enabled_builtin_tools: List[BuiltinTool] = []

    internal_tool_names = ["_notify_artifact_save"]
    if component.get_config("enable_auto_continuation", True):
        internal_tool_names.append("_continue_generation")

    for tool_name in internal_tool_names:
        try:
            _check_and_register_tool_name(tool_name, "internal", loaded_tool_names)
        except ValueError:
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
                origin="internal",
            )

            tool_callable.__doc__ = tool_def.description

            loaded_tools.append(tool_callable)
            enabled_builtin_tools.append(tool_def)
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

    return loaded_tools, enabled_builtin_tools, []


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
                elif tool_type == "openapi":
                    (
                        new_tools,
                        new_builtins,
                        new_cleanups,
                    ) = await _load_openapi_tool(component, tool_config)
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
        log.debug(
            "%s Added repair_history_callback to before_model chain.",
            component.log_identifier,
        )

        if hasattr(component, "_inject_peer_tools_callback"):
            callbacks_in_order_for_before_model.append(
                component._inject_peer_tools_callback
            )
            log.debug(
                "%s Added _inject_peer_tools_callback to before_model chain.",
                component.log_identifier,
            )

        if hasattr(component, "_filter_tools_by_capability_callback"):
            callbacks_in_order_for_before_model.append(
                component._filter_tools_by_capability_callback
            )
            log.debug(
                "%s Added _filter_tools_by_capability_callback to before_model chain.",
                component.log_identifier,
            )
        if hasattr(component, "_inject_gateway_instructions_callback"):
            callbacks_in_order_for_before_model.append(
                component._inject_gateway_instructions_callback
            )
            log.debug(
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
        log.debug(
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
        log.debug(
            "%s Final before_model_callback chain (Solace logging now occurs last) assigned to agent.",
            component.log_identifier,
        )

        tool_invocation_start_cb_with_component = functools.partial(
            adk_callbacks.notify_tool_invocation_start_callback,
            host_component=component,
        )
        agent.before_tool_callback = tool_invocation_start_cb_with_component
        log.debug(
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
        log.debug(
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
        log.debug(
            "%s Added process_artifact_blocks_callback to after_model chain.",
            component.log_identifier,
        )

        # 2. Auto-Continuation (may short-circuit the chain)
        auto_continue_cb = functools.partial(
            adk_callbacks.auto_continue_on_max_tokens_callback, host_component=component
        )
        callbacks_in_order_for_after_model.append(auto_continue_cb)
        log.debug(
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
        log.debug(
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
            credential_service=component.credential_service,
        )
        log.info("%s ADK Runner created successfully.", component.log_identifier)
        return runner
    except Exception as e:
        log.error("%s Failed to create ADK Runner: %s", component.log_identifier, e)
        raise