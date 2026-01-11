"""
Lambda handler wrapper for SAM tools.

This module provides LambdaToolHandler, which wraps tool functions for
Lambda execution with streaming support. It handles:
- Artifact deserialization from Lambda payload
- Context injection
- Result serialization
- FastAPI app creation for Lambda Web Adapter

Example usage:
    # my_tool.py
    from agent_tools import ToolResult, Artifact, ToolContextBase

    async def process_document(
        document: Artifact,
        output_format: str,
        ctx: ToolContextBase,
    ) -> ToolResult:
        ctx.send_status("Processing document...")
        content = document.as_text()
        result = analyze(content)
        return ToolResult.ok("Done", data={"summary": result})

    # lambda_handler.py
    from sam_lambda_tools import LambdaToolHandler
    from my_tool import process_document

    handler = LambdaToolHandler(process_document)
    app = handler.create_fastapi_app()
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from agent_tools import ToolResult, Artifact

from .context import LambdaToolContext

log = logging.getLogger(__name__)


def deserialize_artifact(data: Dict[str, Any]) -> Artifact:
    """
    Deserialize an artifact from Lambda payload format.

    The artifact is expected to have been serialized by SAM's Lambda executor
    using Artifact.to_serializable() or _serialize_artifact().

    Args:
        data: Dictionary with artifact data (filename, content, is_binary, etc.)

    Returns:
        Artifact object with deserialized content
    """
    return Artifact.from_serialized(data)


def _looks_like_artifact(value: Any) -> bool:
    """
    Check if a value looks like a serialized artifact.

    Args:
        value: Value to check

    Returns:
        True if value appears to be a serialized artifact
    """
    if not isinstance(value, dict):
        return False
    # Check for required artifact fields
    return "filename" in value and "content" in value


def deserialize_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize tool arguments, converting artifact dicts to Artifact objects.

    This function recursively processes the args dictionary, converting any
    dictionaries that look like serialized artifacts into Artifact objects.

    Args:
        args: Tool arguments dictionary from Lambda payload

    Returns:
        Dictionary with Artifact objects replacing serialized artifact dicts
    """
    result = {}
    for key, value in args.items():
        if _looks_like_artifact(value):
            # Single artifact
            result[key] = deserialize_artifact(value)
        elif isinstance(value, list):
            # Check for list of artifacts
            result[key] = [
                deserialize_artifact(item) if _looks_like_artifact(item) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


class LambdaToolHandler:
    """
    Wraps a tool function for Lambda execution with streaming support.

    This handler:
    1. Deserializes artifacts from the Lambda payload
    2. Creates a LambdaToolContext for status updates
    3. Injects the context into the tool function
    4. Executes the tool (sync or async)
    5. Ensures the result is a ToolResult

    Usage:
        from sam_lambda_tools import LambdaToolHandler
        from my_tools import process_document

        # Create handler
        handler = LambdaToolHandler(process_document)

        # Create FastAPI app for Lambda Web Adapter
        app = handler.create_fastapi_app()

    The FastAPI app provides:
        POST /invoke - Tool invocation endpoint with streaming response
        GET /health - Health check endpoint
    """

    def __init__(
        self,
        tool_func: Callable,
        ctx_param_name: Optional[str] = None,
    ):
        """
        Initialize the Lambda tool handler.

        Args:
            tool_func: The tool function to wrap
            ctx_param_name: Name of the context parameter (auto-detected if None)
        """
        self.tool_func = tool_func
        self._is_async = inspect.iscoroutinefunction(tool_func)
        self._ctx_param_name = ctx_param_name or self._detect_ctx_param()

        log.info(
            "[LambdaToolHandler] Initialized for %s (async=%s, ctx_param=%s)",
            tool_func.__name__,
            self._is_async,
            self._ctx_param_name,
        )

    def _detect_ctx_param(self) -> Optional[str]:
        """
        Detect the context parameter name from the function signature.

        Looks for parameters named 'ctx', 'context', or with type hints
        containing 'Context'.

        Returns:
            Parameter name if found, None otherwise
        """
        try:
            sig = inspect.signature(self.tool_func)
            for name, param in sig.parameters.items():
                # Check common names
                if name in ("ctx", "context"):
                    return name
                # Check type annotation
                annotation = param.annotation
                if annotation != inspect.Parameter.empty:
                    ann_str = str(annotation)
                    if "Context" in ann_str or "ToolContextBase" in ann_str:
                        return name
        except Exception as e:
            log.warning(
                "[LambdaToolHandler] Could not inspect signature: %s", e
            )
        return None

    async def execute(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
        tool_config: Dict[str, Any],
        stream_queue: asyncio.Queue,
    ) -> ToolResult:
        """
        Execute the tool function with the given arguments.

        This method:
        1. Deserializes artifacts in the args
        2. Creates a LambdaToolContext
        3. Injects the context if the function expects it
        4. Executes the function
        5. Wraps the result in a ToolResult if needed

        Args:
            args: Tool arguments (may contain serialized artifacts)
            context: Context from SAM (session_id, user_id, etc.)
            tool_config: Tool-specific configuration
            stream_queue: Queue for streaming status updates

        Returns:
            ToolResult from the tool execution
        """
        log_id = f"[LambdaToolHandler:{self.tool_func.__name__}]"

        # Deserialize artifacts
        deserialized_args = deserialize_args(args)
        log.debug("%s Deserialized args: %s", log_id, list(deserialized_args.keys()))

        # Create Lambda context
        lambda_ctx = LambdaToolContext(
            session_id=context.get("session_id", ""),
            user_id=context.get("user_id", ""),
            app_name=context.get("app_name", ""),
            tool_config=tool_config,
            stream_queue=stream_queue,
        )

        # Inject context if function expects it
        if self._ctx_param_name:
            deserialized_args[self._ctx_param_name] = lambda_ctx
            log.debug("%s Injected context as '%s'", log_id, self._ctx_param_name)

        # Execute the tool
        try:
            if self._is_async:
                result = await self.tool_func(**deserialized_args)
            else:
                # Run sync function in executor to not block event loop
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.tool_func(**deserialized_args)
                )

            log.debug("%s Execution complete", log_id)

            # Ensure result is ToolResult
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, dict):
                # Try to parse as ToolResult fields
                if "status" in result:
                    return ToolResult(**result)
                else:
                    return ToolResult.ok("Success", data=result)
            else:
                # Wrap raw value
                return ToolResult.ok("Success", data={"result": result})

        except Exception as e:
            log.exception("%s Execution failed: %s", log_id, e)
            return ToolResult.error(
                message=str(e),
                code="EXECUTION_ERROR",
            )

    def create_fastapi_app(self):
        """
        Create a FastAPI application for Lambda Web Adapter.

        Returns:
            FastAPI app with /invoke and /health endpoints
        """
        from .fastapi_app import create_app
        return create_app(self)
