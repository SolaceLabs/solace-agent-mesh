"""
Unified Python executor for handling all Python tool patterns.

This executor provides a unified interface for loading Python tools:
- Simple functions (module + function_name)
- DynamicTool classes (module + class_name)
- DynamicToolProvider classes (auto-discovery or explicit)

It consolidates the various Python tool loading patterns into one place,
using the executor abstraction as the internal implementation.
"""

import importlib
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Type, Union, TYPE_CHECKING

from google.adk.tools import BaseTool, ToolContext
from pydantic import BaseModel

from .base import ToolExecutor, ToolExecutionResult, register_executor
from .executor_tool import ExecutorBasedTool
from ..dynamic_tool import (
    DynamicTool,
    DynamicToolProvider,
    _get_schema_from_signature,
    _SchemaDetectionResult,
)
from ..artifact_types import ArtifactTypeInfo

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


def _is_subclass_by_name(cls: type, base_name: str) -> bool:
    """Check if cls is a subclass of a class with the given name."""
    for base in cls.__mro__:
        if base.__name__ == base_name:
            return True
    return False


def _find_dynamic_tool_class(module: Any) -> Optional[Type[DynamicTool]]:
    """Find a DynamicTool subclass in a module (excluding providers)."""
    candidates = []
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and _is_subclass_by_name(obj, "DynamicTool")
            and not _is_subclass_by_name(obj, "DynamicToolProvider")
            and obj.__module__ == module.__name__
        ):
            candidates.append(obj)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise TypeError(
            f"Module '{module.__name__}' contains multiple DynamicTool subclasses: "
            f"{[c.__name__ for c in candidates]}. Specify 'class_name' explicitly."
        )
    return None


def _find_dynamic_tool_provider_class(module: Any) -> Optional[Type[DynamicToolProvider]]:
    """Find a DynamicToolProvider subclass in a module."""
    candidates = []
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and _is_subclass_by_name(obj, "DynamicToolProvider")
            and obj.__module__ == module.__name__
        ):
            candidates.append(obj)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise TypeError(
            f"Module '{module.__name__}' contains multiple DynamicToolProvider subclasses: "
            f"{[c.__name__ for c in candidates]}. Specify 'class_name' explicitly."
        )
    return None


class _FunctionExecutor(ToolExecutor):
    """
    Internal executor for simple function execution.

    This is similar to LocalPythonExecutor but created from an already-loaded
    function rather than module/function names.
    """

    def __init__(
        self,
        func: Callable,
        pass_tool_context: bool = True,
        pass_tool_config: bool = True,
    ):
        self._func = func
        self._pass_tool_context = pass_tool_context
        self._pass_tool_config = pass_tool_config
        self._is_async = inspect.iscoroutinefunction(func)

        # Check signature for accepted parameters
        try:
            sig = inspect.signature(func)
            self._accepts_tool_context = "tool_context" in sig.parameters
            self._accepts_tool_config = "tool_config" in sig.parameters
        except (ValueError, TypeError):
            self._accepts_tool_context = False
            self._accepts_tool_config = False

    @property
    def executor_type(self) -> str:
        return "function"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Nothing to initialize - function already loaded."""
        pass

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute the function."""
        import asyncio
        import functools

        kwargs = dict(args)

        if self._pass_tool_context and self._accepts_tool_context:
            kwargs["tool_context"] = tool_context
        if self._pass_tool_config and self._accepts_tool_config:
            kwargs["tool_config"] = tool_config

        try:
            if self._is_async:
                result = await self._func(**kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, functools.partial(self._func, **kwargs)
                )

            if isinstance(result, ToolExecutionResult):
                return result
            elif isinstance(result, dict) and result.get("status") == "error":
                return ToolExecutionResult.fail(
                    error=result.get("message", "Unknown error"),
                    error_code=result.get("error_code"),
                )
            return ToolExecutionResult.ok(data=result)

        except Exception as e:
            log.exception("Function execution failed: %s", e)
            return ToolExecutionResult.fail(
                error=f"Execution failed: {str(e)}",
                error_code="EXECUTION_ERROR",
            )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Nothing to clean up."""
        pass


@register_executor("unified_python")
class UnifiedPythonExecutor(ToolExecutor):
    """
    Unified executor that handles all Python tool loading patterns.

    Unlike other executors that handle single tool execution, this executor
    is responsible for LOADING Python tools from modules. It supports:

    1. Simple functions: module + function_name
       - Creates ExecutorBasedTool with internal function executor
       - Auto-detects parameter schema from function signature
       - Auto-detects Artifact and ToolContextFacade parameters

    2. DynamicTool classes: module + class_name
       - Instantiates the DynamicTool class directly
       - Returns the DynamicTool (no additional wrapping needed)

    3. DynamicToolProvider classes: module (auto-discover) or module + class_name
       - Instantiates the provider
       - Calls get_all_tools_for_framework() to get all tools
       - Returns list of DynamicTool instances

    Configuration:
        module: Python module path (required)
        function_name: Function to load (for simple function pattern)
        class_name: Class to load (for explicit class loading)
        tool_config: Configuration to pass to tools
        tool_name: Override the tool name (for functions)
        tool_description: Override the description (for functions)
        raw_string_args: List of args that should not have embeds resolved
        pass_tool_context: Whether to inject tool_context (default: True)
        pass_tool_config: Whether to inject tool_config (default: True)
    """

    def __init__(
        self,
        module: str,
        function_name: Optional[str] = None,
        class_name: Optional[str] = None,
        tool_config: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        tool_description: Optional[str] = None,
        raw_string_args: Optional[List[str]] = None,
        pass_tool_context: bool = True,
        pass_tool_config: bool = True,
        base_path: Optional[str] = None,
    ):
        self._module_path = module
        self._function_name = function_name
        self._class_name = class_name
        self._tool_config = tool_config
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._raw_string_args = raw_string_args or []
        self._pass_tool_context = pass_tool_context
        self._pass_tool_config = pass_tool_config
        self._base_path = base_path

        # Loaded state
        self._module: Any = None
        self._loaded_tools: List[BaseTool] = []

    @property
    def executor_type(self) -> str:
        return "unified_python"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Load the module and create tools."""
        log_id = f"[UnifiedPythonExecutor:{self._module_path}]"

        # Import module
        try:
            if self._base_path:
                import sys
                if self._base_path not in sys.path:
                    sys.path.insert(0, self._base_path)
            self._module = importlib.import_module(self._module_path)
            log.debug("%s Imported module", log_id)
        except Exception as e:
            log.error("%s Failed to import module: %s", log_id, e)
            raise

        # Load tools based on configuration pattern
        if self._function_name:
            # Pattern 1: Simple function
            tools = self._load_function_tool()
        else:
            # Pattern 2/3: Class-based (DynamicTool or DynamicToolProvider)
            tools = self._load_class_based_tools(component)

        self._loaded_tools = tools
        log.info(
            "%s Loaded %d tool(s): %s",
            log_id,
            len(tools),
            [getattr(t, "name", getattr(t, "__name__", "unknown")) for t in tools],
        )

    def _load_function_tool(self) -> List[BaseTool]:
        """Load a simple function as an ExecutorBasedTool."""
        log_id = f"[UnifiedPythonExecutor:{self._module_path}.{self._function_name}]"

        func = getattr(self._module, self._function_name, None)
        if func is None:
            raise AttributeError(
                f"Module '{self._module_path}' has no attribute '{self._function_name}'"
            )
        if not callable(func):
            raise TypeError(
                f"'{self._function_name}' in module '{self._module_path}' is not callable"
            )

        # Detect schema from function signature
        detection_result = _SchemaDetectionResult()
        schema = _get_schema_from_signature(
            func, detection_result=detection_result
        )

        # Build artifact params
        artifact_params: Dict[str, ArtifactTypeInfo] = dict(detection_result.artifact_params)

        # Determine tool name and description
        tool_name = self._tool_name or self._function_name
        tool_description = self._tool_description or (func.__doc__ or f"Execute {tool_name}")

        # Create internal executor for this function
        func_executor = _FunctionExecutor(
            func,
            pass_tool_context=self._pass_tool_context,
            pass_tool_config=self._pass_tool_config,
        )

        # Create ExecutorBasedTool
        tool = ExecutorBasedTool(
            name=tool_name,
            description=tool_description,
            parameters_schema=schema,
            executor=func_executor,
            tool_config=self._tool_config,
            artifact_params=artifact_params,
            raw_string_args=self._raw_string_args,
            ctx_facade_param_name=detection_result.ctx_facade_param_name,
        )

        log.debug(
            "%s Created ExecutorBasedTool (artifacts=%s, ctx_facade=%s)",
            log_id,
            list(artifact_params.keys()),
            detection_result.ctx_facade_param_name,
        )

        return [tool]

    def _load_class_based_tools(
        self, component: "SamAgentComponent"
    ) -> List[DynamicTool]:
        """Load DynamicTool or DynamicToolProvider class."""
        log_id = f"[UnifiedPythonExecutor:{self._module_path}]"

        # Determine the class to load
        tool_class = None
        if self._class_name:
            tool_class = getattr(self._module, self._class_name, None)
            if tool_class is None:
                raise AttributeError(
                    f"Module '{self._module_path}' has no class '{self._class_name}'"
                )
        else:
            # Auto-discover: try provider first, then single tool
            tool_class = _find_dynamic_tool_provider_class(self._module)
            if not tool_class:
                tool_class = _find_dynamic_tool_class(self._module)

        if not tool_class:
            raise TypeError(
                f"Module '{self._module_path}' has no DynamicTool or DynamicToolProvider "
                f"to auto-discover. Specify 'function_name' or 'class_name'."
            )

        # Validate and get config
        validated_config = self._validate_tool_config(tool_class, component)

        # Instantiate based on type
        if _is_subclass_by_name(tool_class, "DynamicToolProvider"):
            provider_instance = tool_class()
            tools = provider_instance.get_all_tools_for_framework(
                tool_config=validated_config
            )
            log.info(
                "%s Loaded %d tools from DynamicToolProvider '%s'",
                log_id,
                len(tools),
                tool_class.__name__,
            )
        elif _is_subclass_by_name(tool_class, "DynamicTool"):
            tool_instance = tool_class(tool_config=validated_config)
            tools = [tool_instance]
            log.info(
                "%s Loaded DynamicTool '%s'",
                log_id,
                tool_class.__name__,
            )
        else:
            raise TypeError(
                f"Class '{tool_class.__name__}' is not a DynamicTool or DynamicToolProvider"
            )

        return tools

    def _validate_tool_config(
        self, tool_class: type, component: "SamAgentComponent"
    ) -> Union[dict, BaseModel, None]:
        """Validate tool_config against class's config_model if defined."""
        from pydantic import ValidationError

        config_model: Optional[Type[BaseModel]] = getattr(
            tool_class, "config_model", None
        )

        if not config_model:
            return self._tool_config

        log.debug(
            "Validating tool_config against %s.config_model (%s)",
            tool_class.__name__,
            config_model.__name__,
        )

        try:
            return config_model.model_validate(self._tool_config or {})
        except ValidationError as e:
            error_msg = (
                f"Configuration error for tool '{tool_class.__name__}'. "
                f"The provided 'tool_config' is invalid:\n{e}"
            )
            log.error("%s %s", component.log_identifier, error_msg)
            raise ValueError(error_msg) from e

    def get_loaded_tools(self) -> List[BaseTool]:
        """
        Get the tools that were loaded during initialization.

        This is the primary interface for retrieving loaded tools.
        Call this after initialize() has completed.
        """
        return self._loaded_tools

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """
        Not used directly - tools are executed via their own interfaces.

        This executor's job is to LOAD tools, not execute them directly.
        The loaded tools (ExecutorBasedTool or DynamicTool) handle their
        own execution.
        """
        return ToolExecutionResult.fail(
            error="UnifiedPythonExecutor does not execute directly. "
                  "Use get_loaded_tools() to get tools and call them.",
            error_code="NOT_EXECUTABLE",
        )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Clean up loaded tools."""
        for tool in self._loaded_tools:
            if hasattr(tool, "cleanup") and callable(tool.cleanup):
                try:
                    await tool.cleanup(component, executor_config)
                except Exception as e:
                    log.warning(
                        "Error cleaning up tool %s: %s",
                        getattr(tool, "name", "unknown"),
                        e,
                    )
        self._loaded_tools = []
        self._module = None
