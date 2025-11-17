"""
Pydantic models for the structured data payloads used in A2A DataPart objects.
These models correspond to the JSON schemas defined in a2a_spec/schemas/
and are used for validating non-visible status update messages.
"""

from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field


class ToolInvocationStartData(BaseModel):
    """
    Data model for a tool invocation start signal.
    Corresponds to tool_invocation_start.json schema.
    """

    type: Literal["tool_invocation_start"] = Field(
        "tool_invocation_start", description="The constant type for this data part."
    )
    tool_name: str = Field(..., description="The name of the tool being called.")
    tool_args: Dict[str, Any] = Field(
        ..., description="The arguments passed to the tool."
    )
    function_call_id: str = Field(
        ..., description="The ID from the LLM's function call."
    )


class LlmInvocationData(BaseModel):
    """
    Data model for an LLM invocation signal.
    Corresponds to llm_invocation.json schema.
    """

    type: Literal["llm_invocation"] = Field(
        "llm_invocation", description="The constant type for this data part."
    )
    request: Dict[str, Any] = Field(
        ...,
        description="A sanitized representation of the LlmRequest object sent to the model.",
    )
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage information for this LLM call (input_tokens, output_tokens, cached_input_tokens, model)",
    )


class AgentProgressUpdateData(BaseModel):
    """
    Data model for an agent progress update signal.
    Corresponds to agent_progress_update.json schema.
    """

    type: Literal["agent_progress_update"] = Field(
        "agent_progress_update", description="The constant type for this data part."
    )
    status_text: str = Field(
        ...,
        description="A human-readable progress message (e.g., 'Analyzing the report...').",
    )


class ArtifactCreationProgressData(BaseModel):
    """
    Data model for an artifact creation progress signal.
    Corresponds to artifact_creation_progress.json schema.
    """

    type: Literal["artifact_creation_progress"] = Field(
        "artifact_creation_progress",
        description="The constant type for this data part.",
    )
    filename: str = Field(..., description="The name of the artifact being created.")
    status: Literal["in-progress", "completed", "failed"] = Field(
        ..., description="The status of the artifact creation."
    )
    bytes_transferred: int = Field(
        ..., description="The number of bytes transferred so far."
    )
    description: Optional[str] = Field(
        None, description="An optional description of the artifact being created."
    )
    artifact_chunk: Optional[str] = Field(
        None,
        description="The chunk of artifact data that was transferred in this progress update. Only present for 'in-progress' status.",
    )
    mime_type: Optional[str] = Field(
        None,
        description="The MIME type of the artifact. Only present for 'completed' status.",
    )
    version: Optional[int] = Field(
        None,
        description="The version number of the artifact being created or updated.",
    )


class ToolResultData(BaseModel):
    """
    Data model for a tool execution result signal.
    Corresponds to tool_result.json schema.
    """

    type: Literal["tool_result"] = Field(
        "tool_result", description="The constant type for this data part."
    )
    tool_name: str = Field(..., description="The name of the tool that was called.")
    result_data: Any = Field(..., description="The data returned by the tool.")
    function_call_id: str = Field(
        ..., description="The ID from the LLM's function call."
    )
    llm_usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage if this tool made LLM calls (input_tokens, output_tokens, cached_input_tokens, model)",
    )


class TemplateBlockData(BaseModel):
    """
    Data model for a buffered inline template block ready for resolution.
    Corresponds to template_block.json schema.
    """

    type: Literal["template_block"] = Field(
        "template_block", description="The constant type for this data part."
    )
    template_id: str = Field(
        ..., description="UUID for tracking this specific template instance."
    )
    data_artifact: str = Field(
        ..., description="Data artifact filename or filename:version."
    )
    jsonpath: Optional[str] = Field(
        None, description="Optional JSONPath expression to filter data."
    )
    limit: Optional[int] = Field(
        None, description="Optional limit on number of items/rows to pass to template."
    )
    template_content: str = Field(
        ..., description="The full Liquid template content."
    )


SignalData = Union[
    ToolInvocationStartData,
    LlmInvocationData,
    AgentProgressUpdateData,
    ArtifactCreationProgressData,
    ToolResultData,
    TemplateBlockData,
]
