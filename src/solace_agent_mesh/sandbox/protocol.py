"""
Protocol definitions for sandbox tool execution.

This module defines the message schemas for communication between
SAM agents and the sandbox worker. Messages follow JSON-RPC 2.0
patterns, consistent with SAM's A2A protocol.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PreloadedArtifact(BaseModel):
    """
    Artifact content pre-loaded by the requesting agent.

    Used when artifacts need to be passed into the sandbox for tool execution.
    Content is base64-encoded to safely transmit binary data.
    """

    filename: str = Field(..., description="Original artifact filename")
    content: str = Field(..., description="Base64-encoded artifact content")
    mime_type: str = Field(default="application/octet-stream", description="MIME type")
    version: int = Field(..., description="Artifact version number")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional artifact metadata"
    )


class ArtifactReference(BaseModel):
    """
    Reference to an artifact to be loaded by the sandbox worker.

    The worker will load the artifact from the shared artifact service.
    """

    filename: str = Field(..., description="Artifact filename to load")
    version: Optional[int] = Field(
        default=None, description="Specific version, or None for latest"
    )


class SandboxInvokeParams(BaseModel):
    """
    Parameters for a sandbox tool invocation request.
    """

    task_id: str = Field(..., description="Unique task identifier")
    tool_name: str = Field(..., description="Name of the tool being invoked")
    args: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool"
    )
    tool_config: Dict[str, Any] = Field(
        default_factory=dict, description="Tool configuration including secrets"
    )

    # Context for artifact access
    app_name: str = Field(..., description="Application/agent name for artifact scoping")
    user_id: str = Field(..., description="User ID for artifact scoping")
    session_id: str = Field(..., description="Session ID for artifact scoping")

    # Artifacts - can be pre-loaded content or references to load
    preloaded_artifacts: Dict[str, PreloadedArtifact] = Field(
        default_factory=dict,
        description="Artifacts with content pre-loaded (keyed by parameter name)",
    )
    artifact_references: Dict[str, ArtifactReference] = Field(
        default_factory=dict,
        description="Artifacts to load from artifact service (keyed by parameter name)",
    )

    # Execution settings
    timeout_seconds: int = Field(
        default=300, description="Maximum execution time in seconds"
    )
    sandbox_profile: str = Field(
        default="standard",
        description="Sandbox profile to use (restrictive, standard, permissive)",
    )


class SandboxToolInvocationRequest(BaseModel):
    """
    JSON-RPC 2.0 style request for sandbox tool execution.

    Published to: {namespace}/a2a/v1/sam_remote_tool/invoke/{tool_name}
    User properties carry replyTo and statusTo for response routing.
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(..., description="Correlation ID (matches replyTo topic suffix)")
    method: Literal["sam_remote_tool/invoke"] = "sam_remote_tool/invoke"
    params: SandboxInvokeParams


class CreatedArtifact(BaseModel):
    """
    Metadata for an artifact created by the sandboxed tool.

    The actual artifact content is saved to the shared artifact service by the
    worker. This metadata is returned to the agent so it can reference the
    artifact by filename and version.
    """

    filename: str = Field(..., description="Artifact filename")
    version: int = Field(..., description="Version number assigned by artifact service")
    mime_type: str = Field(..., description="MIME type of the content")
    size_bytes: int = Field(..., description="Size in bytes")
    description: Optional[str] = Field(default=None, description="Artifact description")


class SandboxInvokeResult(BaseModel):
    """
    Successful result from sandbox tool execution.
    """

    tool_result: Dict[str, Any] = Field(
        ..., description="Serialized ToolResult from the tool"
    )
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    timed_out: bool = Field(default=False, description="Whether execution timed out")
    created_artifacts: List[CreatedArtifact] = Field(
        default_factory=list,
        description="Artifacts created and saved by the worker",
    )


class SandboxError(BaseModel):
    """
    Error details for failed sandbox execution.
    """

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error data"
    )


class SandboxToolInvocationResponse(BaseModel):
    """
    JSON-RPC 2.0 style response from sandbox tool execution.

    Published to: replyTo topic from request user properties.
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(..., description="Matches request id for correlation")
    result: Optional[SandboxInvokeResult] = Field(
        default=None, description="Success result (mutually exclusive with error)"
    )
    error: Optional[SandboxError] = Field(
        default=None, description="Error details (mutually exclusive with result)"
    )

    @classmethod
    def success(
        cls,
        request_id: str,
        tool_result: Dict[str, Any],
        execution_time_ms: int,
        created_artifacts: Optional[List[CreatedArtifact]] = None,
        timed_out: bool = False,
    ) -> "SandboxToolInvocationResponse":
        """Create a success response."""
        return cls(
            id=request_id,
            result=SandboxInvokeResult(
                tool_result=tool_result,
                execution_time_ms=execution_time_ms,
                timed_out=timed_out,
                created_artifacts=created_artifacts or [],
            ),
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        code: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "SandboxToolInvocationResponse":
        """Create a failure response."""
        return cls(
            id=request_id,
            error=SandboxError(code=code, message=message, data=data),
        )


class SandboxStatusUpdateParams(BaseModel):
    """Parameters for a status update notification."""

    task_id: str = Field(..., description="Task ID this status belongs to")
    status_text: str = Field(..., description="Status message from the tool")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO format timestamp",
    )


class SandboxStatusUpdate(BaseModel):
    """
    JSON-RPC 2.0 notification for status updates during tool execution.

    Published to: statusTo from request user properties.
    Notifications have no 'id' field (no response expected).
    """

    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["sam_remote_tool/status"] = "sam_remote_tool/status"
    params: SandboxStatusUpdateParams


# Error codes for sandbox execution
class SandboxErrorCodes:
    """Standard error codes for sandbox execution failures."""

    TIMEOUT = "SANDBOX_TIMEOUT"
    SANDBOX_FAILED = "SANDBOX_FAILED"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_NOT_AVAILABLE = "TOOL_NOT_AVAILABLE"
    IMPORT_ERROR = "IMPORT_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    ARTIFACT_ERROR = "ARTIFACT_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INIT_ERROR = "INIT_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"


# ---------------------------------------------------------------------------
# Tool Init Protocol
# ---------------------------------------------------------------------------


class SandboxInitParams(BaseModel):
    """Parameters for a tool init request."""

    tool_name: str = Field(..., description="Name of the tool to initialize")
    tool_config: Dict[str, Any] = Field(
        default_factory=dict, description="Tool configuration including secrets"
    )


class SandboxToolInitRequest(BaseModel):
    """
    JSON-RPC 2.0 request for tool initialization.

    Sent by the agent to the worker to request enriched tool metadata.
    The worker runs the DynamicTool's init() inside bwrap, reads the
    enriched tool_description and parameters_schema, then responds.

    Published to: {namespace}/a2a/v1/sam_remote_tool/init/{tool_name}
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(..., description="Correlation ID")
    method: Literal["sam_remote_tool/init"] = "sam_remote_tool/init"
    params: SandboxInitParams


class SandboxToolInitResult(BaseModel):
    """
    Successful result from tool initialization.

    Contains enriched metadata computed by the DynamicTool's init() method
    running inside the sandbox. No persistent state is retained — connection
    pools, caches, and singletons are discarded when the subprocess exits.
    """

    tool_name: str = Field(..., description="Name of the initialized tool")
    tool_description: Optional[str] = Field(
        default=None, description="Enriched tool description from init()"
    )
    parameters_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Enriched parameters schema as dict"
    )
    ctx_facade_param_name: Optional[str] = Field(
        default=None,
        description="Parameter name for ToolContextFacade injection",
    )


class SandboxToolInitResponse(BaseModel):
    """
    JSON-RPC 2.0 response from tool initialization.

    Published to: replyTo topic from request user properties.
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(..., description="Matches request id for correlation")
    result: Optional[SandboxToolInitResult] = Field(
        default=None, description="Success result (mutually exclusive with error)"
    )
    error: Optional[SandboxError] = Field(
        default=None, description="Error details (mutually exclusive with result)"
    )

    @classmethod
    def success(
        cls,
        request_id: str,
        tool_name: str,
        tool_description: Optional[str] = None,
        parameters_schema: Optional[Dict[str, Any]] = None,
        ctx_facade_param_name: Optional[str] = None,
    ) -> "SandboxToolInitResponse":
        """Create a success response."""
        return cls(
            id=request_id,
            result=SandboxToolInitResult(
                tool_name=tool_name,
                tool_description=tool_description,
                parameters_schema=parameters_schema,
                ctx_facade_param_name=ctx_facade_param_name,
            ),
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        code: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "SandboxToolInitResponse":
        """Create a failure response."""
        return cls(
            id=request_id,
            error=SandboxError(code=code, message=message, data=data),
        )
