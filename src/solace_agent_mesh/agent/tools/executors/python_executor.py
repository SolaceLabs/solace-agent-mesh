"""
Local Python executor for running tool functions in the same process.

This executor dynamically loads and executes Python functions, similar to
how the existing python tool type works but through the executor abstraction.
"""

import asyncio
import functools
import importlib
import inspect
import logging
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext

from .base import ToolExecutor, ToolExecutionResult, register_executor

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


@register_executor("python")
class LocalPythonExecutor(ToolExecutor):
    """
    Executor that runs Python functions locally.

    This executor dynamically imports a module and calls a function within it.
    It supports both sync and async functions.

    Configuration:
        module: The Python module path (e.g., "mypackage.tools.data_tools")
        function: The function name within the module
        pass_tool_context: Whether to pass tool_context to the function (default: True)
        pass_tool_config: Whether to pass tool_config to the function (default: True)
    """

    def __init__(
        self,
        module: str,
        function: str,
        pass_tool_context: bool = True,
        pass_tool_config: bool = True,
    ):
        """
        Initialize the Python executor.

        Args:
            module: Python module path containing the function
            function: Name of the function to call
            pass_tool_context: Whether to inject tool_context parameter
            pass_tool_config: Whether to inject tool_config parameter
        """
        self._module_path = module
        self._function_name = function
        self._pass_tool_context = pass_tool_context
        self._pass_tool_config = pass_tool_config
        self._func: Optional[Callable] = None
        self._is_async: bool = False
        self._accepts_tool_context: bool = False
        self._accepts_tool_config: bool = False

    @property
    def executor_type(self) -> str:
        return "python"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Load and validate the Python function."""
        log_id = f"[PythonExecutor:{self._module_path}.{self._function_name}]"

        try:
            # Import the module
            module = importlib.import_module(self._module_path)
            log.debug("%s Imported module '%s'", log_id, self._module_path)

            # Get the function
            if not hasattr(module, self._function_name):
                raise AttributeError(
                    f"Module '{self._module_path}' has no function '{self._function_name}'"
                )

            self._func = getattr(module, self._function_name)

            if not callable(self._func):
                raise TypeError(
                    f"'{self._function_name}' in module '{self._module_path}' is not callable"
                )

            # Check if async
            self._is_async = inspect.iscoroutinefunction(self._func)

            # Check signature for tool_context and tool_config
            try:
                sig = inspect.signature(self._func)
                self._accepts_tool_context = "tool_context" in sig.parameters
                self._accepts_tool_config = "tool_config" in sig.parameters
            except (ValueError, TypeError):
                log.warning("%s Could not inspect function signature", log_id)

            log.info(
                "%s Initialized (async=%s, accepts_context=%s, accepts_config=%s)",
                log_id,
                self._is_async,
                self._accepts_tool_context,
                self._accepts_tool_config,
            )

        except Exception as e:
            log.error("%s Failed to initialize: %s", log_id, e)
            raise

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute the Python function."""
        log_id = f"[PythonExecutor:{self._module_path}.{self._function_name}]"

        if self._func is None:
            return ToolExecutionResult.fail(
                error="Executor not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Build kwargs
        kwargs = dict(args)

        # Inject tool_context if function accepts it and config allows
        if self._pass_tool_context and self._accepts_tool_context:
            kwargs["tool_context"] = tool_context

        # Inject tool_config if function accepts it and config allows
        if self._pass_tool_config and self._accepts_tool_config:
            kwargs["tool_config"] = tool_config

        try:
            log.debug("%s Executing with args: %s", log_id, list(kwargs.keys()))

            if self._is_async:
                result = await self._func(**kwargs)
            else:
                # Run sync function in executor to not block
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    functools.partial(self._func, **kwargs),
                )

            log.debug("%s Execution completed successfully", log_id)

            # Convert result to ToolExecutionResult
            if isinstance(result, ToolExecutionResult):
                return result
            elif isinstance(result, dict):
                # Check for error status
                if result.get("status") == "error":
                    return ToolExecutionResult.fail(
                        error=result.get("message", "Unknown error"),
                        error_code=result.get("error_code"),
                        metadata={"raw_result": result},
                    )
                return ToolExecutionResult.ok(data=result)
            else:
                return ToolExecutionResult.ok(data=result)

        except Exception as e:
            log.exception("%s Execution failed: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Execution failed: {str(e)}",
                error_code="EXECUTION_ERROR",
            )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Clean up resources."""
        self._func = None
        log.debug(
            "[PythonExecutor:%s.%s] Cleaned up",
            self._module_path,
            self._function_name,
        )
