"""
OpenAPI Tool Audit Logging Callback

Provides metadata-only audit logging for OpenAPI tool executions.

"""

import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from google.adk.tools import BaseTool, ToolContext

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)


class OpenAPIAuditLogger:

    def __init__(self, component: "SamAgentComponent"):
        """
        Initialize the audit logger.

        Args:
            component: The SamAgentComponent host
        """
        self.component = component
        self.log_identifier = "[OpenAPIConnectorAudit]"

    def log_audit_event(
        self,
        event_type: str,
        tool_name: str,
        operation_id: Optional[str],
        tool_uri: Optional[str],
        http_method: Optional[str],
        actor: Optional[str],
        correlation_id: Optional[str],
        auth_method: Optional[str] = None,
        status_code: Optional[int] = None,
        latency_ms: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        # Build audit entry with standardized field names
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "correlation_id": correlation_id,
            "actor": actor,
            "tool_uri": tool_uri,
            "tool_name": tool_name,
            "agent_name": self.component.agent_name,
            "namespace": self.component.namespace,
        }

        # Build action field: "HTTP_METHOD: operation_id"
        if http_method and operation_id:
            audit_entry["action"] = f"{http_method}: {operation_id}"
        elif operation_id:
            audit_entry["action"] = operation_id
        else:
            audit_entry["action"] = None

        # Add optional fields
        if auth_method:
            audit_entry["auth_method"] = auth_method

        if status_code is not None:
            audit_entry["status_code"] = status_code

        if latency_ms is not None:
            audit_entry["latency_ms"] = latency_ms

        if error_type:
            audit_entry["error_type"] = error_type

        if error_message:
            audit_entry["error_message"] = error_message

        # Determine request status
        if error_type:
            audit_entry["request_status"] = "failure"
        elif status_code and status_code >= 400:
            audit_entry["request_status"] = "error"
        elif status_code and 200 <= status_code < 300:
            audit_entry["request_status"] = "success"
        else:
            audit_entry["request_status"] = "unknown"

        # Log to structured logging system
        log.info(
            "%s %s | tool=%s | action=%s | status=%s | actor=%s",
            self.log_identifier,
            event_type,
            tool_name,
            audit_entry.get("action", "N/A"),
            audit_entry["request_status"],
            actor or "N/A",
            extra={"audit_data": audit_entry},
        )


def _extract_auth_method(tool: BaseTool) -> Optional[str]:
    try:
        if hasattr(tool, "_auth") and tool._auth:
            auth = tool._auth
            if hasattr(auth, "type"):
                return str(auth.type)
            elif hasattr(auth, "__class__"):
                # Infer from class name
                class_name = auth.__class__.__name__.lower()
                if "apikey" in class_name:
                    return "apikey"
                elif "bearer" in class_name or "http" in class_name:
                    return "bearer"
                elif "basic" in class_name:
                    return "basic"
                elif "serviceaccount" in class_name or "oauth" in class_name:
                    return "serviceaccount"

        # Fallback: check tool config
        if hasattr(tool, "_config") and isinstance(tool._config, dict):
            auth_config = tool._config.get("auth", {})
            if isinstance(auth_config, dict):
                return auth_config.get("type")

    except Exception as e:
        log.debug("Could not extract auth method: %s", e)

    return None


def _extract_base_url(tool: BaseTool) -> Optional[str]:
    try:
        # Check for base_url attribute
        if hasattr(tool, "base_url") and tool.base_url:
            return str(tool.base_url)

        # Check for _base_url
        if hasattr(tool, "_base_url") and tool._base_url:
            return str(tool._base_url)

        # Check tool config
        if hasattr(tool, "_config") and isinstance(tool._config, dict):
            return tool._config.get("base_url")

    except Exception as e:
        log.debug("Could not extract base URL: %s", e)

    return None


def _extract_http_method(args: Dict[str, Any]) -> Optional[str]:
    if not args:
        return None

    # Try common patterns for HTTP method
    return (
        args.get("http_method")
        or args.get("method")
        or args.get("request_method")
        or args.get("verb")
    )


def audit_log_openapi_tool_invocation_start(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    host_component: "SamAgentComponent",
) -> None:
    """
    ADK before_tool_callback for OpenAPI tools - logs invocation start.

    Args:
        tool: The tool being invoked
        args: Tool arguments (NOT logged)
        tool_context: ADK tool context
        host_component: The SamAgentComponent host
    """
    # Only process OpenAPI tools
    tool_class_name = tool.__class__.__name__
    if "OpenAPI" not in tool_class_name and not hasattr(tool, "specification_url"):
        return

    # Extract context
    invocation_context = tool_context._invocation_context
    session_id = None
    user_id = None

    if invocation_context and invocation_context.session:
        session_id = invocation_context.session.id
        user_id = invocation_context.session.user_id

    # Extract operation ID from args
    operation_id = None
    if args:
        operation_id = (
            args.get("operation_id")
            or args.get("operationId")
            or args.get("operation")
            or str(args.get("function_name", ""))
        )

    # Extract auth method type (not credentials)
    auth_method = _extract_auth_method(tool)

    # Extract base URL (not including query params)
    tool_uri = _extract_base_url(tool)

    # Extract HTTP method
    http_method = _extract_http_method(args)

    # Build action field
    action = f"{http_method}: {operation_id}" if http_method and operation_id else (operation_id or "unknown")
    correlation_tag = f"corr:{session_id}" if session_id else "corr:unknown"

    # Store start time for latency calculation
    tool_context.state["audit_start_time_ms"] = int(time.time() * 1000)

    # Log in MCP-style format: [openapi-connector] [corr:xxx] message
    log.info(
        "[openapi-connector] [%s] Tool call: %s - User: %s, Agent: %s, URI: %s, Auth: %s",
        correlation_tag,
        action,
        user_id,
        host_component.agent_name,
        tool_uri,
        auth_method,
        extra={
            "user_id": user_id,
            "agent_id": host_component.agent_name,
            "tool_name": tool.name,
            "session_id": session_id,
            "operation_id": operation_id,
            "action": action,
            "tool_uri": tool_uri,
            "http_method": http_method,
            "auth_method": auth_method,
        },
    )


async def audit_log_openapi_tool_execution_result(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
    host_component: "SamAgentComponent",
) -> Optional[Dict[str, Any]]:
    """
    ADK after_tool_callback for OpenAPI tools - logs execution result.

    Args:
        tool: The tool that was executed
        args: Tool arguments (NOT logged)
        tool_context: ADK tool context
        tool_response: Tool response (NOT logged)
        host_component: The SamAgentComponent host

    Returns:
        None (does not modify the response)
    """
    # Only process OpenAPI tools
    tool_class_name = tool.__class__.__name__
    if "OpenAPI" not in tool_class_name and not hasattr(tool, "specification_url"):
        return None

    # Extract context
    invocation_context = tool_context._invocation_context
    session_id = None
    user_id = None

    if invocation_context and invocation_context.session:
        session_id = invocation_context.session.id
        user_id = invocation_context.session.user_id

    # Extract operation ID
    operation_id = None
    if args:
        operation_id = (
            args.get("operation_id")
            or args.get("operationId")
            or args.get("operation")
            or str(args.get("function_name", ""))
        )

    # Extract metadata from response (status code, error type)
    status_code = None
    error_type = None
    error_message = None

    if isinstance(tool_response, dict):
        # Get HTTP status code
        status_code = tool_response.get("status_code")

        # Check for errors
        if "error" in tool_response:
            error_type = "api_error"
            error_msg = tool_response.get("error")
            if isinstance(error_msg, str):
                # Truncate error message to avoid logging sensitive data
                error_message = error_msg[:100] if len(error_msg) > 100 else error_msg
            else:
                error_message = "API error occurred"

    # Calculate latency
    latency_ms = None
    start_time = tool_context.state.get("audit_start_time_ms")
    if start_time:
        latency_ms = int(time.time() * 1000) - start_time

    # Extract auth method and base URL
    auth_method = _extract_auth_method(tool)
    tool_uri = _extract_base_url(tool)
    http_method = _extract_http_method(args)

    # Build action and correlation tag
    action = f"{http_method}: {operation_id}" if http_method and operation_id else (operation_id or "unknown")
    correlation_tag = f"corr:{session_id}" if session_id else "corr:unknown"

    # Log in MCP-style format: [openapi-connector] [corr:xxx] message
    if error_type:
        # ERROR format: similar to MCP error log
        log.error(
            "[openapi-connector] [%s] %s failed: %s - %s",
            correlation_tag,
            action,
            error_type,
            error_message or "No error details",
            extra={
                "user_id": user_id,
                "agent_id": host_component.agent_name,
                "tool_name": tool.name,
                "session_id": session_id,
                "operation_id": operation_id,
                "action": action,
                "tool_uri": tool_uri,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
    else:
        # INFO format: success with metrics
        log.info(
            "[openapi-connector] [%s] %s completed - Status: %s, Latency: %sms, User: %s",
            correlation_tag,
            action,
            status_code,
            latency_ms,
            user_id,
            extra={
                "user_id": user_id,
                "agent_id": host_component.agent_name,
                "tool_name": tool.name,
                "session_id": session_id,
                "operation_id": operation_id,
                "action": action,
                "tool_uri": tool_uri,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "auth_method": auth_method,
            },
        )

    return None