"""
Shared types for SAM agent tools.

This package provides the core types used by tools in both SAM (local execution)
and Lambda (remote execution) environments. By using these shared types, tools
can be written once and run in either environment without modification.

Core Types:
    - ToolResult: Structured result from tool execution
    - DataObject: Data that may become an artifact
    - DataDisposition: How to handle DataObjects (AUTO, ARTIFACT, INLINE, etc.)
    - Artifact: Pre-loaded artifact with content and metadata
    - ToolContextBase: Abstract interface for tool context

Streaming Types (for Lambda communication):
    - StreamMessage: NDJSON message wrapper
    - StreamMessageType: Message type enum (STATUS, RESULT, ERROR, HEARTBEAT)
    - StatusPayload, ResultPayload, ErrorPayload: Typed payloads

Example - Writing a portable tool:
    from agent_tools import ToolResult, DataObject, Artifact, ToolContextBase

    async def analyze_data(
        input_file: Artifact,
        ctx: ToolContextBase,
    ) -> ToolResult:
        ctx.send_status("Loading data...")
        content = input_file.as_text()

        ctx.send_status("Processing...")
        result = process(content)

        return ToolResult.ok(
            message="Analysis complete",
            data_objects=[
                DataObject(
                    name="result.json",
                    content=result,
                    mime_type="application/json",
                )
            ]
        )
"""

# Result types
from .result import (
    ToolResult,
    DataObject,
    DataDisposition,
    TOOL_RESULT_SCHEMA_VERSION,
)

# Artifact types
from .artifact import (
    Artifact,
    ArtifactTypeInfo,
    is_artifact_type,
    get_artifact_info,
)

# Context types
from .context import ToolContextBase

# Streaming types
from .streaming import (
    StreamMessage,
    StreamMessageType,
    StatusPayload,
    ResultPayload,
    ErrorPayload,
    HeartbeatPayload,
)

__all__ = [
    # Result types
    "ToolResult",
    "DataObject",
    "DataDisposition",
    "TOOL_RESULT_SCHEMA_VERSION",
    # Artifact types
    "Artifact",
    "ArtifactTypeInfo",
    "is_artifact_type",
    "get_artifact_info",
    # Context types
    "ToolContextBase",
    # Streaming types
    "StreamMessage",
    "StreamMessageType",
    "StatusPayload",
    "ResultPayload",
    "ErrorPayload",
    "HeartbeatPayload",
]
