"""
Tool executors for running tools on different backends.

This package provides an abstraction layer that allows tools to run on:
- Local Python: Execute functions in the same process
- AWS Lambda: Invoke serverless functions

Usage:
    from solace_agent_mesh.agent.tools.executors import (
        ExecutorBasedTool,
        LocalPythonExecutor,
        LambdaExecutor,
        create_executor,
    )

    # Create an executor
    executor = LocalPythonExecutor(
        module="my_tools",
        function="process_data"
    )

    # Create a tool using the executor
    tool = ExecutorBasedTool(
        name="process_data",
        description="Process data",
        parameters_schema=schema,
        executor=executor,
    )
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
from .lambda_executor import LambdaExecutor

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
    "LambdaExecutor",
    # Tool class
    "ExecutorBasedTool",
    "create_executor_tool_from_config",
]
