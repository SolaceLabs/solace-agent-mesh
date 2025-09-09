"""
Defines the base classes and helpers for "dynamic" tools.
Dynamic tools allow for programmatic definition of tool names, descriptions,
and parameter schemas, offering more flexibility than standard Python tools.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Dict, Any, get_origin, get_args, Union
import inspect

from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types


# --- Base Class for Programmatic Tools ---

class DynamicTool(BaseTool, ABC):
    """
    Base class for dynamic tools that can define their own function names,
    descriptions, and parameter schemas programmatically.
    """

    def __init__(self, tool_config: Optional[dict] = None):
        # Initialize with placeholder values, will be overridden by properties
        super().__init__(
            name="dynamic_tool_placeholder", description="dynamic_tool_placeholder"
        )
        self.tool_config = tool_config or {}

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

    def _get_declaration(self) -> Optional[adk_types.FunctionDeclaration]:
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
        This method delegates the call to the abstract _run_async_impl.
        """
        return await self._run_async_impl(
            args=args, tool_context=tool_context, credential=None
        )

    @abstractmethod
    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None
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
    def __init__(self, func: Callable, tool_config: Optional[dict] = None):
        super().__init__(tool_config=tool_config)
        self._func = func
        self._schema = _get_schema_from_signature(func)

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
        credential: Optional[str] = None
    ) -> dict:
        # Inject tool_context and tool_config if the function expects them
        sig = inspect.signature(self._func)
        if "tool_context" in sig.parameters:
            args["tool_context"] = tool_context
        if "tool_config" in sig.parameters:
            args["tool_config"] = self.tool_config

        return await self._func(**args)


# --- Base Class for Tool Providers ---

class DynamicToolProvider(ABC):
    """
    Base class for dynamic tool providers that can generate a list of tools
    programmatically from a single configuration block.
    """

    _decorated_tools: List[Callable] = []

    @classmethod
    def register_tool(cls, func: Callable) -> Callable:
        """
        A decorator to register a standard async function as a tool.
        The decorated function's signature and docstring will be used to
        create the tool definition.
        """
        # Ensure each subclass has its own list of decorated tools
        if not hasattr(cls, '_decorated_tools') or cls._decorated_tools is DynamicToolProvider._decorated_tools:
            cls._decorated_tools = []
        cls._decorated_tools.append(func)
        return func

    def _create_tools_from_decorators(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        """
        Internal helper to convert decorated functions into DynamicTool instances.
        This would be called inside the user's create_tools implementation.
        """
        tools = []
        for func in self._decorated_tools:
            adapter = _FunctionAsDynamicTool(func, tool_config)
            tools.append(adapter)
        return tools

    @abstractmethod
    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        """
        Generate and return a list of DynamicTool instances.

        Args:
            tool_config: The configuration dictionary from the agent's YAML file.

        Returns:
            A list of initialized DynamicTool objects.
        """
        pass
