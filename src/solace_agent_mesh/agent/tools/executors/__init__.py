"""
Tool executors for running tools on different backends.

This package provides an abstraction layer that allows tools to run on:
- Local Python: Execute functions in the same process

The UnifiedPythonExecutor handles all Python tool loading patterns:
- Simple functions (module + function_name)
- DynamicTool classes (module + class_name)
- DynamicToolProvider classes (auto-discovery)

Usage:
    from solace_agent_mesh.agent.tools.executors import (
        UnifiedPythonExecutor,
        ExecutorBasedTool,
        create_executor,
    )

    # Load Python tools using the unified executor
    executor = UnifiedPythonExecutor(
        module="my_tools",
        function_name="process_data"  # or class_name for DynamicTool
    )
    await executor.initialize(component, {})
    tools = executor.get_loaded_tools()
"""

from .base import (
    ToolExecutor,
    ToolExecutionResult,
    register_executor,
    get_executor_class,
    create_executor,
    list_executor_types,
)

from .python_executor import LocalPythonExecutor
from .unified_python_executor import UnifiedPythonExecutor

from .executor_tool import (
    ExecutorBasedTool,
    create_executor_tool_from_config,
)

__all__ = [
    # Base classes
    "ToolExecutor",
    "ToolExecutionResult",
    # Registry functions
    "register_executor",
    "get_executor_class",
    "create_executor",
    "list_executor_types",
    # Executor implementations
    "LocalPythonExecutor",
    "UnifiedPythonExecutor",
    # Tool class
    "ExecutorBasedTool",
    "create_executor_tool_from_config",
]
