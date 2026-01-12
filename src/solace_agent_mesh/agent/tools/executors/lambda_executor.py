"""
AWS Lambda executor for running tool functions as serverless functions.

This executor invokes AWS Lambda functions and handles the serialization
of arguments and deserialization of results. It supports two invocation modes
to accommodate different deployment complexity and feature requirements.

=============================================================================
WHY TWO MODES?
=============================================================================

We support both standard and streaming modes because they have different
deployment requirements and trade-offs:

STANDARD MODE (function_arn via boto3):
  - Deployment: Simple .zip upload or container image
  - Handler: Regular Python function (def handler(event, context))
  - Auth: IAM-based authentication
  - Features: No real-time status updates
  - Use when: Quick tools that don't need progress feedback, simpler deployment

STREAMING MODE (function_url via HTTP):
  - Deployment: Requires Lambda Web Adapter (LWA) - either as Layer (.zip) or
    in container image. Container images are recommended for easier packaging.
  - Handler: FastAPI app running via uvicorn (using sam-lambda-tools package)
  - Auth: Function URL authentication (IAM or NONE)
  - Features: Real-time NDJSON status updates, unified experience with local tools
  - Use when: Long-running tools that benefit from progress feedback

For streaming mode deployment, see the sam-lambda-tools package documentation.
Lambda Web Adapter layer ARN: arn:aws:lambda:<region>:753240598075:layer:LambdaAdapterLayerX86:24

TODO: Add comprehensive deployment guide to documentation covering both modes.
=============================================================================

Mode Details:

1. Standard Invocation (via boto3):
   - Uses function_arn to invoke via AWS SDK
   - Synchronous request-response pattern
   - No streaming support

2. Streaming Invocation (via Function URL):
   - Uses function_url to invoke via HTTP POST
   - Streams NDJSON status updates in real-time
   - Requires Lambda Web Adapter (LWA) on the Lambda side
   - Status updates are forwarded to ToolContextFacade
"""

import asyncio
import base64
import functools
import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext

from .base import ToolExecutor, ToolExecutionResult, register_executor
from ..artifact_types import Artifact
from ..tool_result import ToolResult

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent
    from ...utils.tool_context_facade import ToolContextFacade

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


import boto3
from botocore.exceptions import ClientError, BotoCoreError


@register_executor("lambda")
class LambdaExecutor(ToolExecutor):
    """
    Executor that invokes AWS Lambda functions.

    This executor serializes tool arguments to JSON, invokes a Lambda function,
    and deserializes the response. It supports two invocation modes:

    1. **Standard Mode** (function_arn): Uses boto3 to invoke Lambda directly.
       Synchronous request-response, no streaming.

    2. **Streaming Mode** (function_url): Uses HTTP POST to Lambda Function URL.
       Supports real-time status updates via NDJSON streaming. Requires Lambda
       Web Adapter (LWA) on the Lambda side with sam-lambda-tools package.

    Configuration:
        function_arn: The ARN of the Lambda function (for standard mode)
        function_url: Lambda Function URL (for streaming mode, takes precedence)
        region: AWS region (optional, uses default if not specified)
        invocation_type: "RequestResponse" (sync) or "Event" (async) - standard mode only
        include_context: Whether to include session context in the payload
        timeout_seconds: Client-side timeout for the invocation
        stream_status: Whether to forward status updates (streaming mode only, default True)

    Lambda Payload Format:
        {
            "args": { ... tool arguments ... },
            "context": {
                "session_id": "...",
                "user_id": "...",
            },
            "tool_config": { ... }
        }

    Streaming Response Format (NDJSON):
        {"type":"status","payload":{"message":"Processing..."},"timestamp":1704067200.0}
        {"type":"result","payload":{"tool_result":{...}},"timestamp":1704067201.0}

    Standard Response Format:
        {
            "success": true/false,
            "data": { ... result data ... },
            "error": "error message if failed",
            "error_code": "ERROR_CODE"
        }
    """

    def __init__(
        self,
        function_arn: Optional[str] = None,
        function_url: Optional[str] = None,
        region: Optional[str] = None,
        invocation_type: str = "RequestResponse",
        include_context: bool = True,
        timeout_seconds: int = 60,
        stream_status: bool = True,
    ):
        """
        Initialize the Lambda executor.

        Args:
            function_arn: ARN of the Lambda function (standard mode)
            function_url: Lambda Function URL (streaming mode, takes precedence)
            region: AWS region (optional)
            invocation_type: Lambda invocation type (standard mode only)
            include_context: Whether to include context in payload
            timeout_seconds: Client-side timeout
            stream_status: Whether to forward status updates (streaming mode)
        """
        if not function_arn and not function_url:
            raise ValueError("Either function_arn or function_url must be provided")

        self._function_arn = function_arn
        self._function_url = function_url
        self._region = region
        self._invocation_type = invocation_type
        self._include_context = include_context
        self._timeout_seconds = timeout_seconds
        self._stream_status = stream_status
        self._client = None  # boto3 client for standard mode
        self._http_client = None  # httpx client for streaming mode

    @property
    def executor_type(self) -> str:
        return "lambda"

    @property
    def _is_streaming_mode(self) -> bool:
        """Check if executor is configured for streaming mode."""
        return self._function_url is not None

    @property
    def _log_identifier(self) -> str:
        """Get a log identifier for this executor."""
        if self._function_url:
            return f"[LambdaExecutor:streaming:{self._function_url[:50]}]"
        return f"[LambdaExecutor:{self._function_arn}]"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Initialize the Lambda client (boto3 or httpx depending on mode)."""
        log_id = self._log_identifier

        try:
            if self._is_streaming_mode:
                # Streaming mode: use httpx for HTTP streaming
                import httpx

                self._http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=10.0,
                        read=self._timeout_seconds,
                        write=30.0,
                        pool=5.0,
                    )
                )
                log.info(
                    "%s Initialized in streaming mode (timeout=%ds)",
                    log_id,
                    self._timeout_seconds,
                )
            else:
                # Standard mode: use boto3
                client_kwargs = {}
                if self._region:
                    client_kwargs["region_name"] = self._region

                self._client = boto3.client("lambda", **client_kwargs)
                log.info(
                    "%s Initialized in standard mode (region=%s, invocation_type=%s)",
                    log_id,
                    self._region or "default",
                    self._invocation_type,
                )

        except Exception as e:
            log.error("%s Failed to initialize Lambda client: %s", log_id, e)
            raise

    def _build_payload(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the payload for Lambda invocation."""
        log_id = self._log_identifier

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
                }
            except Exception as ctx_err:
                log.warning(
                    "%s Could not extract context: %s. Proceeding without context.",
                    log_id,
                    ctx_err,
                )

        return payload

    def _get_tool_context_facade(
        self,
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> Optional["ToolContextFacade"]:
        """Get a ToolContextFacade for forwarding status updates."""
        try:
            from ...utils.tool_context_facade import ToolContextFacade

            return ToolContextFacade(tool_context, tool_config)
        except Exception as e:
            log.debug(
                "%s Could not create ToolContextFacade: %s",
                self._log_identifier,
                e,
            )
            return None

    def _get_sigv4_auth(self) -> Optional[Any]:
        """
        Get SigV4 authentication for Lambda Function URL requests.

        Returns an auth object for httpx requests, or None if credentials
        are not available.
        """
        log_id = self._log_identifier
        try:
            from httpx_auth_awssigv4 import SigV4Auth
            log.debug("%s httpx_auth_awssigv4 module loaded successfully", log_id)

            session = boto3.Session()
            credentials = session.get_credentials()

            if credentials is None:
                log.warning(
                    "%s No AWS credentials available for SigV4 signing",
                    log_id,
                )
                return None

            # Determine region - use configured region, extract from URL, session region, or default
            region = self._region
            if not region and self._function_url:
                # Extract region from Function URL (e.g., xxx.lambda-url.us-east-1.on.aws)
                import re
                match = re.search(r'lambda-url\.([a-z0-9-]+)\.on\.aws', self._function_url)
                if match:
                    region = match.group(1)
                    log.debug("%s Extracted region from Function URL: %s", log_id, region)
            if not region:
                region = session.region_name or "us-east-1"

            log.info(
                "%s Creating SigV4Auth with access_key=%s..., region=%s, has_token=%s, profile=%s",
                log_id,
                credentials.access_key[:10] if credentials.access_key else "None",
                region,
                bool(credentials.token),
                session.profile_name,
            )

            return SigV4Auth(
                access_key=credentials.access_key,
                secret_key=credentials.secret_key,
                service="lambda",
                region=region,
                token=credentials.token,
            )
        except ImportError as e:
            log.warning(
                "%s httpx-auth-awssigv4 not installed, SigV4 signing disabled. "
                "Install with: pip install httpx-auth-awssigv4. Error: %s",
                log_id,
                e,
            )
            return None
        except Exception as e:
            log.warning(
                "%s Failed to create SigV4 auth: %s",
                log_id,
                e,
            )
            return None

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Invoke the Lambda function (streaming or standard mode)."""
        if self._is_streaming_mode:
            return await self._execute_streaming(args, tool_context, tool_config)
        else:
            return await self._execute_standard(args, tool_context, tool_config)

    async def _execute_streaming(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute via Lambda Function URL with NDJSON streaming."""
        import httpx

        log_id = self._log_identifier

        if self._http_client is None:
            return ToolExecutionResult.fail(
                error="HTTP client not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Get ToolContextFacade for status forwarding
        ctx_facade = self._get_tool_context_facade(tool_context, tool_config)

        # Build payload
        payload = self._build_payload(args, tool_context, tool_config)

        # Construct URL (append /invoke if not present)
        url = self._function_url
        if not url.endswith("/invoke"):
            url = url.rstrip("/") + "/invoke"

        log.debug("%s Invoking Lambda via Function URL: %s", log_id, url)

        # Get SigV4 auth for IAM-authenticated Function URLs
        auth = self._get_sigv4_auth()
        if auth:
            log.info("%s Using SigV4 authentication for Function URL", log_id)
        else:
            log.warning(
                "%s No SigV4 auth available - request may fail with 403 if Function URL requires IAM auth",
                log_id,
            )

        try:
            async with self._http_client.stream(
                "POST",
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                auth=auth,
            ) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    log.error(
                        "%s HTTP error %d: %s",
                        log_id,
                        response.status_code,
                        error_body.decode("utf-8", errors="replace")[:500],
                    )
                    return ToolExecutionResult.fail(
                        error=f"Lambda returned HTTP {response.status_code}",
                        error_code=f"HTTP_{response.status_code}",
                    )

                # Process NDJSON stream
                final_result = None
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError as e:
                        log.warning("%s Invalid JSON in stream: %s", log_id, e)
                        continue

                    msg_type = msg.get("type")
                    msg_payload = msg.get("payload", {})

                    if msg_type == "status":
                        # Forward status to ToolContextFacade
                        status_msg = msg_payload.get("message", "")
                        if status_msg and self._stream_status and ctx_facade:
                            ctx_facade.send_status(status_msg)
                        log.debug("%s Status: %s", log_id, status_msg)

                    elif msg_type == "heartbeat":
                        # Heartbeat - just log at debug level
                        log.debug("%s Heartbeat received", log_id)

                    elif msg_type == "result":
                        # Final result
                        tool_result = msg_payload.get("tool_result", {})
                        log.debug("%s Result received", log_id)

                        # Deserialize ToolResult
                        if ToolResult.is_serialized_tool_result(tool_result):
                            try:
                                final_result = ToolResult.from_serialized(tool_result)
                            except Exception as e:
                                log.warning(
                                    "%s Failed to deserialize ToolResult: %s",
                                    log_id,
                                    e,
                                )
                                final_result = ToolExecutionResult.ok(data=tool_result)
                        else:
                            # Wrap raw result
                            final_result = ToolExecutionResult.ok(data=tool_result)

                    elif msg_type == "error":
                        # Error from Lambda
                        error_msg = msg_payload.get("error", "Unknown error")
                        error_code = msg_payload.get("error_code", "LAMBDA_ERROR")
                        log.error("%s Stream error: %s", log_id, error_msg)
                        return ToolExecutionResult.fail(
                            error=error_msg,
                            error_code=error_code,
                        )

                # Return final result or error if none received
                if final_result is None:
                    log.error("%s No result message received in stream", log_id)
                    return ToolExecutionResult.fail(
                        error="No result received from Lambda stream",
                        error_code="NO_RESULT",
                    )

                return final_result

        except httpx.TimeoutException as e:
            log.error("%s Request timeout: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Lambda request timed out after {self._timeout_seconds}s",
                error_code="TIMEOUT",
            )
        except httpx.HTTPError as e:
            log.error("%s HTTP error: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"HTTP error: {str(e)}",
                error_code="HTTP_ERROR",
            )
        except Exception as e:
            log.exception("%s Unexpected error: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )

    async def _execute_standard(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute via boto3 Lambda invoke (standard mode)."""
        log_id = self._log_identifier

        if self._client is None:
            return ToolExecutionResult.fail(
                error="Lambda client not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Build payload
        payload = self._build_payload(args, tool_context, tool_config)

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
                            error=response_payload.get(
                                "error", "Lambda returned failure"
                            ),
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
        """Clean up Lambda client(s)."""
        log_id = self._log_identifier

        # Clean up boto3 client
        self._client = None

        # Clean up httpx client
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

        log.debug("%s Cleaned up", log_id)
