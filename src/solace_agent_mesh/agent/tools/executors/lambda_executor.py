"""
AWS Lambda executor for running tool functions as serverless functions.

This executor invokes AWS Lambda functions and handles the serialization
of arguments and deserialization of results.
"""

import asyncio
import base64
import functools
import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext

from .base import ToolExecutor, ToolExecutionResult, register_executor
from ..artifact_types import Artifact
from ..tool_result import ToolResult

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)


def _serialize_artifact(artifact: Artifact) -> Dict[str, Any]:
    """
    Serialize an Artifact object to a JSON-compatible dict.

    Binary content is base64-encoded with a marker.
    """
    content = artifact.content
    is_binary = False

    if isinstance(content, bytes):
        content = base64.b64encode(content).decode("utf-8")
        is_binary = True

    return {
        "filename": artifact.filename,
        "content": content,
        "is_binary": is_binary,
        "mime_type": artifact.mime_type,
        "version": artifact.version,
        "metadata": artifact.metadata,
    }


def _serialize_args_for_lambda(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize args dict for Lambda invocation.

    Converts Artifact objects to JSON-serializable dicts with base64-encoded
    binary content.
    """
    serialized = {}
    for key, value in args.items():
        if isinstance(value, Artifact):
            serialized[key] = _serialize_artifact(value)
        elif isinstance(value, list):
            # Handle List[Artifact]
            serialized[key] = [
                _serialize_artifact(item) if isinstance(item, Artifact) else item
                for item in value
            ]
        else:
            serialized[key] = value
    return serialized


# Try to import boto3, but don't fail if not available
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    BotoCoreError = Exception


@register_executor("lambda")
class LambdaExecutor(ToolExecutor):
    """
    Executor that invokes AWS Lambda functions.

    This executor serializes tool arguments to JSON, invokes a Lambda function,
    and deserializes the response. It supports passing context information
    to the Lambda function.

    Configuration:
        function_arn: The ARN of the Lambda function to invoke
        region: AWS region (optional, uses default if not specified)
        invocation_type: "RequestResponse" (sync) or "Event" (async)
        include_context: Whether to include session context in the payload
        timeout_seconds: Client-side timeout for the invocation

    Lambda Payload Format:
        {
            "args": { ... tool arguments ... },
            "context": {
                "session_id": "...",
                "user_id": "...",
                "app_name": "..."
            },
            "tool_config": { ... }
        }

    Expected Lambda Response Format:
        {
            "success": true/false,
            "data": { ... result data ... },
            "error": "error message if failed",
            "error_code": "ERROR_CODE"
        }
    """

    def __init__(
        self,
        function_arn: str,
        region: Optional[str] = None,
        invocation_type: str = "RequestResponse",
        include_context: bool = True,
        timeout_seconds: int = 60,
    ):
        """
        Initialize the Lambda executor.

        Args:
            function_arn: ARN of the Lambda function
            region: AWS region (optional)
            invocation_type: Lambda invocation type
            include_context: Whether to include context in payload
            timeout_seconds: Client-side timeout
        """
        self._function_arn = function_arn
        self._region = region
        self._invocation_type = invocation_type
        self._include_context = include_context
        self._timeout_seconds = timeout_seconds
        self._client = None

    @property
    def executor_type(self) -> str:
        return "lambda"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Initialize the Lambda client."""
        log_id = f"[LambdaExecutor:{self._function_arn}]"

        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for Lambda executor. Install with: pip install boto3"
            )

        try:
            # Create Lambda client
            client_kwargs = {}
            if self._region:
                client_kwargs["region_name"] = self._region

            self._client = boto3.client("lambda", **client_kwargs)

            log.info(
                "%s Initialized (region=%s, invocation_type=%s)",
                log_id,
                self._region or "default",
                self._invocation_type,
            )

        except Exception as e:
            log.error("%s Failed to initialize Lambda client: %s", log_id, e)
            raise

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Invoke the Lambda function."""
        log_id = f"[LambdaExecutor:{self._function_arn}]"

        if self._client is None:
            return ToolExecutionResult.fail(
                error="Lambda client not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Serialize args (handles Artifact objects with binary content)
        serialized_args = _serialize_args_for_lambda(args)

        # Build payload
        payload = {
            "args": serialized_args,
            "tool_config": tool_config,
        }

        # Include context if configured
        if self._include_context:
            try:
                from ...utils.context_helpers import get_original_session_id
                inv_context = tool_context._invocation_context
                payload["context"] = {
                    "session_id": get_original_session_id(inv_context),
                    "user_id": inv_context.user_id,
                    "app_name": inv_context.app_name,
                }
            except Exception as ctx_err:
                log.warning(
                    "%s Could not extract context: %s. Proceeding without context.",
                    log_id,
                    ctx_err,
                )

        try:
            log.debug("%s Invoking Lambda with args: %s", log_id, list(args.keys()))

            # Invoke Lambda in executor to not block the event loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                functools.partial(
                    self._client.invoke,
                    FunctionName=self._function_arn,
                    InvocationType=self._invocation_type,
                    Payload=json.dumps(payload).encode("utf-8"),
                ),
            )

            # Check for function error
            if "FunctionError" in response:
                error_payload = json.loads(response["Payload"].read().decode("utf-8"))
                error_msg = error_payload.get("errorMessage", "Lambda function error")
                log.error("%s Lambda function error: %s", log_id, error_msg)
                return ToolExecutionResult.fail(
                    error=error_msg,
                    error_code="LAMBDA_FUNCTION_ERROR",
                    metadata={"lambda_error": error_payload},
                )

            # Parse response payload
            response_payload = json.loads(response["Payload"].read().decode("utf-8"))

            log.debug("%s Lambda invocation completed", log_id)

            # Handle different response formats
            if isinstance(response_payload, dict):
                # Check for serialized ToolResult first (has _schema marker)
                if ToolResult.is_serialized_tool_result(response_payload):
                    log.debug("%s Detected serialized ToolResult response", log_id)
                    try:
                        return ToolResult.from_serialized(response_payload)
                    except Exception as e:
                        log.warning(
                            "%s Failed to deserialize ToolResult: %s. Falling back to dict.",
                            log_id,
                            e,
                        )
                        # Fall through to dict handling

                if "success" in response_payload:
                    # Standard ToolExecutionResult format
                    if response_payload.get("success"):
                        return ToolExecutionResult.ok(
                            data=response_payload.get("data"),
                            metadata=response_payload.get("metadata", {}),
                        )
                    else:
                        return ToolExecutionResult.fail(
                            error=response_payload.get("error", "Lambda returned failure"),
                            error_code=response_payload.get("error_code"),
                            metadata=response_payload.get("metadata", {}),
                        )
                elif "statusCode" in response_payload:
                    # API Gateway-style response
                    status_code = response_payload.get("statusCode", 200)
                    body = response_payload.get("body")
                    if isinstance(body, str):
                        try:
                            body = json.loads(body)
                        except json.JSONDecodeError:
                            pass
                    if status_code >= 400:
                        return ToolExecutionResult.fail(
                            error=f"Lambda returned status {status_code}",
                            error_code=f"HTTP_{status_code}",
                            metadata={"body": body},
                        )
                    return ToolExecutionResult.ok(data=body)
                else:
                    # Raw dict response
                    return ToolExecutionResult.ok(data=response_payload)
            else:
                # Non-dict response
                return ToolExecutionResult.ok(data=response_payload)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "UNKNOWN")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            log.error("%s Lambda client error: %s - %s", log_id, error_code, error_msg)
            return ToolExecutionResult.fail(
                error=f"Lambda invocation failed: {error_msg}",
                error_code=error_code,
            )
        except BotoCoreError as e:
            log.error("%s Boto core error: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"AWS error: {str(e)}",
                error_code="AWS_ERROR",
            )
        except json.JSONDecodeError as e:
            log.error("%s Failed to parse Lambda response: %s", log_id, e)
            return ToolExecutionResult.fail(
                error="Failed to parse Lambda response as JSON",
                error_code="PARSE_ERROR",
            )
        except Exception as e:
            log.exception("%s Unexpected error: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )

    async def cleanup(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Clean up Lambda client."""
        self._client = None
        log.debug("[LambdaExecutor:%s] Cleaned up", self._function_arn)
