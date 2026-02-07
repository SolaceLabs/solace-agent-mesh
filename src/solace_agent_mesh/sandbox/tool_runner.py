"""
Tool Runner - Executes tools inside the nsjail sandbox.

This module is invoked by nsjail to run a Python tool function within
the sandboxed environment. It:
1. Reads invocation parameters from a JSON file
2. Sets up the SandboxToolContextFacade
3. Imports and calls the tool function
4. Writes the result to a JSON file

Usage:
    python -m solace_agent_mesh.sandbox.tool_runner /path/to/runner_args.json
"""

import asyncio
import importlib
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

from .context_facade import SandboxToolContextFacade

# Configure logging for sandbox environment
logging.basicConfig(
    level=logging.INFO,
    format="[sandbox] %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


def load_tool_function(module_path: str, function_name: str):
    """
    Dynamically import and return a tool function.

    Args:
        module_path: Dot-separated module path (e.g., "mytools.data")
        function_name: Name of the function to call

    Returns:
        The callable function

    Raises:
        ImportError: If module cannot be imported
        AttributeError: If function not found in module
    """
    log.info("Loading tool: %s.%s", module_path, function_name)
    module = importlib.import_module(module_path)
    func = getattr(module, function_name)

    if not callable(func):
        raise TypeError(f"{module_path}.{function_name} is not callable")

    return func


def serialize_result(result: Any) -> Dict[str, Any]:
    """
    Serialize a tool result to a JSON-compatible format.

    Handles ToolResult objects and converts them to dictionaries.

    Args:
        result: The tool function's return value

    Returns:
        JSON-serializable dictionary
    """
    # Handle None
    if result is None:
        return {"text": None, "data_objects": []}

    # Handle ToolResult from the tool interface
    if hasattr(result, "text") and hasattr(result, "data_objects"):
        # It's a ToolResult-like object
        data_objects = []
        for obj in result.data_objects or []:
            if hasattr(obj, "model_dump"):
                data_objects.append(obj.model_dump())
            elif hasattr(obj, "__dict__"):
                data_objects.append(obj.__dict__)
            else:
                data_objects.append(str(obj))

        return {
            "text": result.text,
            "data_objects": data_objects,
        }

    # Handle dict directly
    if isinstance(result, dict):
        return result

    # Handle string
    if isinstance(result, str):
        return {"text": result, "data_objects": []}

    # Handle other types - try to convert to string
    try:
        return {"text": str(result), "data_objects": []}
    except Exception:
        return {"text": repr(result), "data_objects": []}


async def run_tool_async(
    module_path: str,
    function_name: str,
    args: Dict[str, Any],
    context: SandboxToolContextFacade,
) -> Dict[str, Any]:
    """
    Run a tool function (sync or async).

    Args:
        module_path: Module path to import
        function_name: Function name to call
        args: Arguments to pass to the function
        context: The sandbox context facade

    Returns:
        Serialized result dictionary
    """
    func = load_tool_function(module_path, function_name)

    # Call the function with context as first arg and args as kwargs
    # Tools expect (ctx, **kwargs) signature, e.g. echo_tool(ctx, message="hello")
    if asyncio.iscoroutinefunction(func):
        result = await func(context, **args)
    else:
        result = func(context, **args)

    return serialize_result(result)


def run_tool(runner_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool with the given arguments.

    Args:
        runner_args: Dictionary containing:
            - module: Module path
            - function: Function name
            - args: Tool arguments
            - tool_config: Tool configuration
            - artifact_paths: Mapping of param names to file paths
            - status_pipe: Path to status named pipe
            - result_file: Path to write result
            - output_dir: Directory for output artifacts
            - user_id: User ID
            - session_id: Session ID

    Returns:
        Result dictionary with either 'result' or 'error' key
    """
    module_path = runner_args["module"]
    function_name = runner_args["function"]
    args = runner_args.get("args", {})
    tool_config = runner_args.get("tool_config", {})
    artifact_paths = runner_args.get("artifact_paths", {})
    status_pipe = runner_args.get("status_pipe", "")
    output_dir = runner_args.get("output_dir", "/sandbox/output")
    user_id = runner_args.get("user_id", "unknown")
    session_id = runner_args.get("session_id", "unknown")

    log.info(
        "Running tool: %s.%s (user=%s, session=%s)",
        module_path,
        function_name,
        user_id,
        session_id,
    )

    # Create context facade
    context = SandboxToolContextFacade(
        status_pipe_path=status_pipe,
        tool_config=tool_config,
        artifact_paths=artifact_paths,
        output_dir=output_dir,
        user_id=user_id,
        session_id=session_id,
    )

    try:
        # Run the tool
        result = asyncio.run(
            run_tool_async(module_path, function_name, args, context)
        )
        return {"result": result}

    except ImportError as e:
        log.error("Failed to import tool module: %s", e)
        return {"error": f"Import error: {e}"}

    except AttributeError as e:
        log.error("Tool function not found: %s", e)
        return {"error": f"Function not found: {e}"}

    except TypeError as e:
        log.error("Tool function call error: %s", e)
        return {"error": f"Call error: {e}"}

    except Exception as e:
        log.exception("Tool execution failed: %s", e)
        tb = traceback.format_exc()
        return {"error": f"Execution error: {e}\n{tb}"}


def main():
    """
    Main entry point for the tool runner.

    Reads runner arguments from a JSON file and writes result to another JSON file.
    """
    if len(sys.argv) < 2:
        print("Usage: python -m solace_agent_mesh.sandbox.tool_runner <args_file>", file=sys.stderr)
        sys.exit(1)

    args_file = Path(sys.argv[1])

    if not args_file.exists():
        print(f"Error: Arguments file not found: {args_file}", file=sys.stderr)
        sys.exit(1)

    try:
        runner_args = json.loads(args_file.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in arguments file: {e}", file=sys.stderr)
        sys.exit(1)

    # Run the tool
    result = run_tool(runner_args)

    # Write result to file
    result_file = runner_args.get("result_file")
    if result_file:
        Path(result_file).write_text(json.dumps(result, default=str))
        log.info("Result written to: %s", result_file)
    else:
        # Fall back to stdout
        print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
