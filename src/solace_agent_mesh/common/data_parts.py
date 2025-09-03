"""
Pydantic models for the structured data payloads used in A2A DataPart objects.
These models correspond to the JSON schemas defined in a2a_spec/schemas/
and are used for validating non-visible status update messages.
"""

from typing import Any, Dict, Literal, Union
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
    bytes_saved: int = Field(..., description="The number of bytes saved so far.")
    artifact_chunk: str = Field(
        ...,
        description="The chunk of artifact data that was saved in this progress update.",
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


SignalData = Union[
    ToolInvocationStartData,
    LlmInvocationData,
    AgentProgressUpdateData,
    ArtifactCreationProgressData,
    ToolResultData,
]
