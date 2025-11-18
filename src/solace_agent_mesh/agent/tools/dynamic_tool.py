"""
Defines the base classes and helpers for "dynamic" tools.
Dynamic tools allow for programmatic definition of tool names, descriptions,
and parameter schemas, offering more flexibility than standard Python tools.
"""

import logging
from abc import ABC, abstractmethod
from typing import (
    Optional,
    List,
    Callable,
    Dict,
    Any,
    get_origin,
    get_args,
    Union,
    Literal,
    TYPE_CHECKING,
    Type,
)
import inspect

from pydantic import BaseModel
from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types

from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

from ...common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)
from ...common.utils.embeds.types import ResolutionMode

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent
    from .tool_config_types import AnyToolConfig


# --- Base Class for Programmatic Tools ---


class DynamicTool(BaseTool, ABC):
    """
    Base class for dynamic tools that can define their own function names,
    descriptions, and parameter schemas programmatically.
    """

    config_model: Optional[Type[BaseModel]] = None

    def __init__(self, tool_config: Optional[Union[dict, BaseModel]] = None):
        # Initialize with placeholder values, will be overridden by properties
        super().__init__(
            name="dynamic_tool_placeholder", description="dynamic_tool_placeholder"
        )
        self.tool_config = tool_config or {}

    async def init(
        self, component: "SamAgentComponent", tool_config: "AnyToolConfig"
    ) -> None:
        """
        (Optional) Asynchronously initializes resources for the tool.
        This method is called once when the agent starts up.
        The `component` provides access to agent-wide state, and `tool_config`
        is the validated Pydantic model instance if `config_model` is defined.
        """
        pass

    async def cleanup(
        self, component: "SamAgentComponent", tool_config: "AnyToolConfig"
    ) -> None:
        """
        (Optional) Asynchronously cleans up resources used by the tool.
        This method is called once when the agent is shutting down.
        """
        pass

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Return the function name that the LLM will call."""
        pass

    @property
    @abstractmethod
    def tool_description(self) -> str:
        """Return the description of what this tool does."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> adk_types.Schema:
        """Return the ADK Schema defining the tool's parameters."""
        pass

    @property
    def raw_string_args(self) -> List[str]:
        """
        Return a list of argument names that should not have embeds resolved.
        Subclasses can override this property.
        """
        return []

    @property
    def resolution_type(self) -> Literal["early", "all"]:
        """
        Determines which embeds to resolve. 'early' resolves simple embeds like
        math and uuid. 'all' also resolves 'artifact_content'.
        Defaults to 'early'.
        """
        return "early"

    def _get_declaration(self) -> Optional[Any]:
        """
        Generate the FunctionDeclaration for this dynamic tool.
        This follows the same pattern as PeerAgentTool and MCP tools.
        """
        # Update the tool name to match what the module defines
        self.name = self.tool_name

        return adk_types.FunctionDeclaration(
            name=self.tool_name,
            description=self.tool_description,
            parameters=self.parameters_schema,
        )

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Dict[str, Any]:
        """
        Asynchronously runs the tool with the given arguments.
        This method resolves embeds in arguments and then delegates the call
        to the abstract _run_async_impl.
        """
        log_identifier = f"[DynamicTool:{self.tool_name}]"
        resolved_kwargs = args.copy()

        types_to_resolve = EARLY_EMBED_TYPES
        if self.resolution_type == "all":
            types_to_resolve = EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES)

        # Unlike ADKToolWrapper, DynamicTools receive all args in a single dict.
        # We iterate through this dict to resolve embeds.
        for key, value in args.items():
            if key in self.raw_string_args and isinstance(value, str):
                log.debug(
                    "%s Skipping embed resolution for raw string kwarg '%s'",
                    log_identifier,
                    key,
                )
            elif isinstance(value, str) and EMBED_DELIMITER_OPEN in value:
                log.debug("%s Resolving embeds for kwarg '%s'", log_identifier, key)
                # Create the resolution context
                if hasattr(tool_context, "_invocation_context"):
                    # Use the invocation context if available
                    invocation_context = tool_context._invocation_context
                else:
                    # Error if no invocation context is found
                    raise RuntimeError(
                        f"{log_identifier} No invocation context found in ToolContext. Cannot resolve embeds."
                    )
                session_context = invocation_context.session
                if not session_context:
                    raise RuntimeError(
                        f"{log_identifier} No session context found in invocation context. Cannot resolve embeds."
                    )
                resolution_context = {
                    "artifact_service": invocation_context.artifact_service,
                    "session_context": {
                        "session_id": get_original_session_id(invocation_context),
                        "user_id": session_context.user_id,
                        "app_name": session_context.app_name,
                    },
                }
                resolved_value, _, _ = await resolve_embeds_in_string(
                    text=value,
                    context=resolution_context,
                    resolver_func=evaluate_embed,
                    types_to_resolve=types_to_resolve,
                    resolution_mode=ResolutionMode.TOOL_PARAMETER,
                    log_identifier=log_identifier,
                    config=self.tool_config,
                )
                resolved_kwargs[key] = resolved_value

        return await self._run_async_impl(
            args=resolved_kwargs, tool_context=tool_context, credential=None
        )

    @abstractmethod
    async def _run_async_impl(
        self, args: dict, tool_context: ToolContext, credential: Optional[str] = None
    ) -> dict:
        """
        Implement the actual tool logic.
        Must return a dictionary response.
        """
        pass


# --- Internal Adapter for Function-Based Tools ---


def _get_schema_from_signature(func: Callable) -> adk_types.Schema:
    """
    Introspects a function's signature and generates an ADK Schema for its parameters.
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    type_map = {
        str: adk_types.Type.STRING,
        int: adk_types.Type.INTEGER,
        float: adk_types.Type.NUMBER,
        bool: adk_types.Type.BOOLEAN,
        list: adk_types.Type.ARRAY,
        dict: adk_types.Type.OBJECT,
    }

    for param in sig.parameters.values():
        if param.name in ("tool_context", "tool_config", "kwargs", "self", "cls"):
            continue

        param_type = param.annotation
        is_optional = False

        # Handle Optional[T] which is Union[T, None]
        origin = get_origin(param_type)
        args = get_args(param_type)
        if origin is Union and type(None) in args:
            is_optional = True
            # Get the actual type from Union[T, None]
            param_type = next((t for t in args if t is not type(None)), Any)

        adk_type = type_map.get(param_type)
        if not adk_type:
            # Default to string if type is not supported or specified (e.g., Any)
            adk_type = adk_types.Type.STRING

        properties[param.name] = adk_types.Schema(type=adk_type, nullable=is_optional)

        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(param.name)

    return adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties=properties,
        required=required,
    )


class _FunctionAsDynamicTool(DynamicTool):
    """
    Internal adapter to wrap a standard Python function as a DynamicTool.
    """

    def __init__(
        self,
        func: Callable,
        tool_config: Optional[Union[dict, BaseModel]] = None,
        provider_instance: Optional[Any] = None,
    ):
        super().__init__(tool_config=tool_config)
        self._func = func
        self._provider_instance = provider_instance
        self._schema = _get_schema_from_signature(func)

        # Check if the function is an instance method that needs `self`
        self._is_instance_method = False
        sig = inspect.signature(self._func)
        if sig.parameters:
            first_param = next(iter(sig.parameters.values()))
            if first_param.name == "self":
                self._is_instance_method = True

    @property
    def tool_name(self) -> str:
        return self._func.__name__

    @property
    def tool_description(self) -> str:
        return inspect.getdoc(self._func) or ""

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return self._schema

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None,
    ) -> dict:
        # Inject tool_context and tool_config if the function expects them
        sig = inspect.signature(self._func)
        if "tool_context" in sig.parameters:
            args["tool_context"] = tool_context
        if "tool_config" in sig.parameters:
            args["tool_config"] = self.tool_config

        if self._provider_instance and self._is_instance_method:
            # It's an instance method, call it on the provider instance
            return await self._func(self._provider_instance, **args)
        else:
            # It's a static method or a standalone function
            return await self._func(**args)


# --- Base Class for Tool Providers ---


class DynamicToolProvider(ABC):
    """
    Base class for dynamic tool providers that can generate a list of tools
    programmatically from a single configuration block.
    """

    config_model: Optional[Type[BaseModel]] = None
    _decorated_tools: List[Callable] = []

    @classmethod
    def register_tool(cls, func: Callable) -> Callable:
        """
        A decorator to register a standard async function as a tool.
        The decorated function's signature and docstring will be used to
        create the tool definition.
        """
        # This check is crucial. It runs for each decorated method.
        # If the current class `cls` is using the list from the base class
        # `DynamicToolProvider`, it creates a new, empty list just for `cls`.
        # On subsequent decorator calls for the same `cls`, this condition will
        # be false, and it will append to the existing list.
        if (
            not hasattr(cls, "_decorated_tools")
            or cls._decorated_tools is DynamicToolProvider._decorated_tools
        ):
            cls._decorated_tools = []

        cls._decorated_tools.append(func)
        return func

    def _create_tools_from_decorators(
        self, tool_config: Optional[Union[dict, BaseModel]] = None
    ) -> List[DynamicTool]:
        """
        Internal helper to convert decorated functions into DynamicTool instances.
        """
        tools = []
        for func in self._decorated_tools:
            adapter = _FunctionAsDynamicTool(func, tool_config, provider_instance=self)
            tools.append(adapter)
        return tools

    def get_all_tools_for_framework(
        self, tool_config: Optional[Union[dict, BaseModel]] = None
    ) -> List[DynamicTool]:
        """
        Framework-internal method that automatically combines decorated tools with custom tools.
        This is called by the ADK setup code, not by users.

        Args:
            tool_config: The configuration dictionary from the agent's YAML file.

        Returns:
            A list of all DynamicTool objects (decorated + custom).
        """
        # Get tools from decorators automatically
        decorated_tools = self._create_tools_from_decorators(tool_config)

        # Get custom tools from the user's implementation
        custom_tools = self.create_tools(tool_config)

        return decorated_tools + custom_tools

    @abstractmethod
    def create_tools(self, tool_config: Optional[Union[dict, BaseModel]] = None) -> List[DynamicTool]:
        """
        Generate and return a list of custom DynamicTool instances.

        Note: Tools registered with the @register_tool decorator are automatically
        included by the framework - you don't need to handle them here.

        Args:
            tool_config: The configuration dictionary from the agent's YAML file.

        Returns:
            A list of custom DynamicTool objects (decorated tools are added automatically).
        """
        pass
