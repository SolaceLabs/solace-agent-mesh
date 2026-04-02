"""
Tool executors for running tools on different backends.

This package provides an abstraction layer that allows tools to run on:
- Local Python: Execute functions in the same process
- Remote sandbox worker: Execute via Solace broker (SamRemoteExecutor)

The PythonToolLoader handles all Python tool loading patterns:
- Simple functions (module + function_name)
- DynamicTool classes (module + class_name)
- DynamicToolProvider classes (auto-discovery)

Usage:
    from solace_agent_mesh.agent.tools.executors import (
        PythonToolLoader,
        SamRemoteExecutor,
        ExecutorBasedTool,
    )

    # Load Python tools using the loader
    loader = PythonToolLoader(
        module="my_tools",
        function_name="process_data"  # or class_name for DynamicTool
    )
    await loader.initialize(component, {})
    tools = loader.get_loaded_tools()
"""

from .base import (
    ToolExecutor,
    ToolExecutionResult,
    register_executor,
    get_executor_class,
    create_executor,
    list_executor_types,
)

from .unified_python_executor import PythonToolLoader
from .sandboxed_executor import SamRemoteExecutor

from .executor_tool import (
    ExecutorBasedTool,
)

# Deprecated alias — use PythonToolLoader instead
UnifiedPythonExecutor = PythonToolLoader

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
    "SamRemoteExecutor",
    # Tool loader
    "PythonToolLoader",
    # Tool class
    "ExecutorBasedTool",
    # Deprecated aliases
    "UnifiedPythonExecutor",
]
