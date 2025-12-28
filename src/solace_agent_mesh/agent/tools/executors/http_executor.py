"""
HTTP executor for calling external HTTP/REST APIs as tools.

This executor makes HTTP requests to external services and handles
various authentication methods and response formats.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from google.adk.tools import ToolContext

from .base import ToolExecutor, ToolExecutionResult, register_executor
from ..tool_result import ToolResult

if TYPE_CHECKING:
    from ...sac.component import SamAgentComponent

log = logging.getLogger(__name__)

# Try to import aiohttp, but don't fail if not available
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


AuthType = Literal["bearer", "basic", "api_key", "none"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


@register_executor("http")
class HTTPExecutor(ToolExecutor):
    """
    Executor that makes HTTP requests to external APIs.

    This executor supports various HTTP methods, authentication types,
    and response formats. It can be configured to pass tool arguments
    as query parameters, JSON body, or form data.

    Configuration:
        endpoint: Base URL of the API endpoint
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        auth_type: Authentication type (bearer, basic, api_key, none)
        auth_token: Authentication token/credentials
        api_key_header: Header name for API key auth (default: X-API-Key)
        content_type: Request content type (default: application/json)
        timeout_seconds: Request timeout
        include_context: Whether to include context in request
        args_location: Where to put args ("body", "query", "path")
        headers: Additional headers to include

    Request Format (for POST with args_location="body"):
        {
            "args": { ... tool arguments ... },
            "context": { ... session context ... }
        }

    Expected Response Format:
        JSON response is parsed and returned. If response contains
        "success" field, it's treated as ToolExecutionResult format.
    """

    def __init__(
        self,
        endpoint: str,
        method: HttpMethod = "POST",
        auth_type: AuthType = "none",
        auth_token: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        content_type: str = "application/json",
        timeout_seconds: int = 60,
        include_context: bool = False,
        args_location: Literal["body", "query"] = "body",
        headers: Optional[Dict[str, str]] = None,
        success_status_codes: Optional[List[int]] = None,
    ):
        """
        Initialize the HTTP executor.

        Args:
            endpoint: Base URL of the API
            method: HTTP method to use
            auth_type: Type of authentication
            auth_token: Token for authentication
            api_key_header: Header name for API key
            content_type: Content-Type header value
            timeout_seconds: Request timeout
            include_context: Include session context in request
            args_location: Where to place arguments (body or query)
            headers: Additional headers
            success_status_codes: Status codes to treat as success (default: 200-299)
        """
        self._endpoint = endpoint
        self._method = method.upper()
        self._auth_type = auth_type
        self._auth_token = auth_token
        self._api_key_header = api_key_header
        self._content_type = content_type
        self._timeout_seconds = timeout_seconds
        self._include_context = include_context
        self._args_location = args_location
        self._extra_headers = headers or {}
        self._success_codes = success_status_codes or list(range(200, 300))
        self._session: Optional["aiohttp.ClientSession"] = None

    @property
    def executor_type(self) -> str:
        return "http"

    async def initialize(
        self,
        component: "SamAgentComponent",
        executor_config: Dict[str, Any],
    ) -> None:
        """Initialize the HTTP session."""
        log_id = f"[HTTPExecutor:{self._endpoint}]"

        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp is required for HTTP executor. Install with: pip install aiohttp"
            )

        try:
            # Create session with timeout
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

            log.info(
                "%s Initialized (method=%s, auth=%s)",
                log_id,
                self._method,
                self._auth_type,
            )

        except Exception as e:
            log.error("%s Failed to initialize: %s", log_id, e)
            raise

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers including authentication."""
        headers = {
            "Content-Type": self._content_type,
            "Accept": "application/json",
            **self._extra_headers,
        }

        if self._auth_type == "bearer" and self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        elif self._auth_type == "api_key" and self._auth_token:
            headers[self._api_key_header] = self._auth_token
        # Note: basic auth is handled separately in aiohttp

        return headers

    def _get_basic_auth(self) -> Optional["aiohttp.BasicAuth"]:
        """Get basic auth credentials if configured."""
        if self._auth_type == "basic" and self._auth_token:
            # Expect token in format "username:password"
            if ":" in self._auth_token:
                username, password = self._auth_token.split(":", 1)
                return aiohttp.BasicAuth(username, password)
            else:
                log.warning(
                    "[HTTPExecutor] Basic auth token should be in 'username:password' format"
                )
        return None

    async def execute(
        self,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_config: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Make the HTTP request."""
        log_id = f"[HTTPExecutor:{self._endpoint}]"

        if self._session is None:
            return ToolExecutionResult.fail(
                error="HTTP session not initialized. Call initialize() first.",
                error_code="NOT_INITIALIZED",
            )

        # Build request
        headers = self._build_headers()
        basic_auth = self._get_basic_auth()

        # Prepare request data
        url = self._endpoint
        params = None
        json_data = None

        if self._args_location == "query":
            # Pass args as query parameters
            params = {k: str(v) for k, v in args.items() if v is not None}
        else:
            # Pass args in body
            body_data = {"args": args}

            # Include context if configured
            if self._include_context:
                try:
                    from ...utils.context_helpers import get_original_session_id
                    inv_context = tool_context._invocation_context
                    body_data["context"] = {
                        "session_id": get_original_session_id(inv_context),
                        "user_id": inv_context.user_id,
                        "app_name": inv_context.app_name,
                    }
                except Exception as ctx_err:
                    log.warning(
                        "%s Could not extract context: %s",
                        log_id,
                        ctx_err,
                    )

            json_data = body_data

        try:
            log.debug(
                "%s Making %s request with args: %s",
                log_id,
                self._method,
                list(args.keys()),
            )

            async with self._session.request(
                method=self._method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                auth=basic_auth,
            ) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")

                # Read response body
                if "application/json" in content_type:
                    try:
                        response_data = await response.json()
                    except json.JSONDecodeError:
                        response_data = await response.text()
                else:
                    response_data = await response.text()

                log.debug("%s Response status: %d", log_id, status)

                # Check if request was successful
                if status not in self._success_codes:
                    error_msg = f"HTTP {status}"
                    if isinstance(response_data, dict):
                        error_msg = response_data.get("error", response_data.get("message", error_msg))
                    elif isinstance(response_data, str) and len(response_data) < 200:
                        error_msg = response_data

                    return ToolExecutionResult.fail(
                        error=error_msg,
                        error_code=f"HTTP_{status}",
                        metadata={"status_code": status, "response": response_data},
                    )

                # Parse successful response
                if isinstance(response_data, dict):
                    # Check for serialized ToolResult first (has _schema marker)
                    if ToolResult.is_serialized_tool_result(response_data):
                        log.debug("%s Detected serialized ToolResult response", log_id)
                        try:
                            return ToolResult.from_serialized(response_data)
                        except Exception as e:
                            log.warning(
                                "%s Failed to deserialize ToolResult: %s. Falling back to dict.",
                                log_id,
                                e,
                            )
                            # Fall through to dict handling

                    if "success" in response_data:
                        # Standard ToolExecutionResult format
                        if response_data.get("success"):
                            return ToolExecutionResult.ok(
                                data=response_data.get("data"),
                                metadata=response_data.get("metadata", {}),
                            )
                        else:
                            return ToolExecutionResult.fail(
                                error=response_data.get("error", "Request failed"),
                                error_code=response_data.get("error_code"),
                                metadata=response_data.get("metadata", {}),
                            )
                    else:
                        return ToolExecutionResult.ok(data=response_data)
                else:
                    return ToolExecutionResult.ok(data=response_data)

        except aiohttp.ClientError as e:
            log.error("%s Client error: %s", log_id, e)
            return ToolExecutionResult.fail(
                error=f"HTTP request failed: {str(e)}",
                error_code="CLIENT_ERROR",
            )
        except asyncio.TimeoutError:
            log.error("%s Request timed out after %ds", log_id, self._timeout_seconds)
            return ToolExecutionResult.fail(
                error=f"Request timed out after {self._timeout_seconds} seconds",
                error_code="TIMEOUT",
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
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        log.debug("[HTTPExecutor:%s] Cleaned up", self._endpoint)
