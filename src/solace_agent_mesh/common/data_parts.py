"""
Pydantic models for the structured data payloads used in A2A DataPart objects.
These models correspond to the JSON schemas defined in a2a_spec/schemas/
and are used for validating non-visible status update messages.
"""

from typing import Any, Dict, List, Literal, Optional, Union
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
    parallel_group_id: Optional[str] = Field(
        None,
        description="ID grouping tool calls that execute in parallel. Tools with the same ID should be rendered side-by-side.",
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


class LlmResponseData(BaseModel):
    """
    Data model for an LLM response signal.
    Corresponds to llm_response.json schema.
    """

    type: Literal["llm_response"] = Field(
        "llm_response", description="The constant type for this data part."
    )
    data: Dict[str, Any] = Field(
        ..., description="The raw response data from the LLM."
    )
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage information.",
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
    status: Literal["in-progress", "completed", "failed", "cancelled"] = Field(
        ...,
        description="The status of the artifact creation. 'cancelled' is used when an artifact block was started but never completed (e.g., LLM mentioned artifact syntax in text).",
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
    function_call_id: Optional[str] = Field(
        None, description="The function call ID if artifact was created by a tool."
    )
    rolled_back_text: Optional[str] = Field(
        None,
        description="The original text that was incorrectly parsed as an artifact block. Only present for 'cancelled' status. The frontend should display this text to the user.",
    )


class ArtifactSavedData(BaseModel):
    """
    Data model for an artifact saved notification signal.
    This is sent when an artifact has been successfully saved to storage.
    Unlike ArtifactCreationProgressData, this is a single notification event
    and does not follow the start->updates->end protocol.
    """

    type: Literal["artifact_saved"] = Field(
        "artifact_saved",
        description="The constant type for this data part.",
    )
    filename: str = Field(..., description="The name of the saved artifact.")
    version: int = Field(..., description="The version number of the saved artifact.")
    mime_type: str = Field(..., description="The MIME type of the artifact.")
    size_bytes: int = Field(..., description="The size of the artifact in bytes.")
    description: Optional[str] = Field(
        None, description="An optional description of the artifact."
    )
    function_call_id: Optional[str] = Field(
        None, description="The function call ID if artifact was created by a tool."
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
    template_content: str = Field(..., description="The full Liquid template content.")


class StructuredInvocationRequest(BaseModel):
    """
    Data part for structured agent invocation with schema-validated input/output.

    Used by workflows and other programmatic callers to invoke an agent in
    "function mode" where input is validated against a schema, and output
    is validated (with retry) against an output schema.

    The agent responds with a StructuredInvocationResult.
    """

    type: Literal["structured_invocation_request"] = Field(
        "structured_invocation_request", description="The constant type for this data part."
    )
    workflow_name: str = Field(..., description="Name of the workflow (or caller context)")
    node_id: str = Field(..., description="ID of the invocation (workflow node ID or caller-defined)")
    input_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for input validation (overrides agent card)"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for output validation (overrides agent card)"
    )
    suggested_output_filename: Optional[str] = Field(
        None, description="Suggested unique filename for the output artifact"
    )


class ArtifactRef(BaseModel):
    """Reference to an artifact."""

    name: str
    version: Optional[int] = None


class StructuredInvocationResult(BaseModel):
    """
    Data part returned by agent after a structured invocation.

    Contains the result of a schema-validated agent execution, including
    artifact reference, validation status, and any error information.
    """

    type: Literal["structured_invocation_result"] = Field(
        "structured_invocation_result", description="The constant type for this data part."
    )
    status: Literal["success", "error"] = Field(
        ..., description="Execution result status"
    )
    output_artifact_ref: Optional[ArtifactRef] = Field(
        None, description="Reference to the result artifact if success"
    )
    error_message: Optional[str] = Field(None, description="Error message if error")
    validation_errors: Optional[List[str]] = Field(
        None, description="Schema validation errors if any"
    )
    retry_count: int = Field(0, description="Number of retries attempted")


class WorkflowExecutionStartData(BaseModel):
    """
    Data part signaling the start of a workflow execution.
    Corresponds to workflow_execution_start.json schema.
    """

    type: Literal["workflow_execution_start"] = Field(
        "workflow_execution_start", description="The constant type for this data part."
    )
    workflow_name: str = Field(..., description="Name of the workflow")
    execution_id: str = Field(..., description="Unique execution ID")
    input_artifact_ref: Optional[ArtifactRef] = Field(
        None, description="Reference to the input artifact"
    )
    workflow_input: Optional[Dict[str, Any]] = Field(
        None, description="Input data for the workflow"
    )


class SwitchCaseInfo(BaseModel):
    """Information about a single case in a switch node."""

    condition: str = Field(..., description="Condition expression for this case")
    node: str = Field(..., description="Target node ID if this case matches")


class WorkflowNodeExecutionStartData(BaseModel):
    """
    Data part signaling the start of a workflow node execution.
    Corresponds to workflow_node_execution_start.json schema.
    """

    type: Literal["workflow_node_execution_start"] = Field(
        "workflow_node_execution_start",
        description="The constant type for this data part.",
    )
    node_id: str = Field(..., description="ID of the node")
    node_type: str = Field(..., description="Type of the node (agent, switch, map, loop, workflow, etc.)")
    agent_name: Optional[str] = Field(
        None, description="Name of the agent persona if applicable"
    )
    input_artifact_ref: Optional[ArtifactRef] = Field(
        None, description="Reference to the input artifact for this node"
    )
    iteration_index: Optional[int] = Field(
        None, description="Index if inside a map/loop"
    )
    condition: Optional[str] = Field(
        None, description="Condition expression for switch/loop nodes"
    )
    true_branch: Optional[str] = Field(
        None, description="Node ID for true branch"
    )
    false_branch: Optional[str] = Field(
        None, description="Node ID for false branch"
    )
    true_branch_label: Optional[str] = Field(
        None, description="Label/Persona for true branch"
    )
    false_branch_label: Optional[str] = Field(
        None, description="Label/Persona for false branch"
    )
    sub_task_id: Optional[str] = Field(
        None, description="The sub-task ID associated with this node execution"
    )
    parent_node_id: Optional[str] = Field(
        None, description="ID of the parent node (e.g. for map iterations)"
    )
    # Switch node fields
    cases: Optional[List[SwitchCaseInfo]] = Field(
        None, description="Cases for switch nodes"
    )
    default_branch: Optional[str] = Field(
        None, description="Default branch for switch nodes"
    )
    # Join node fields
    wait_for: Optional[List[str]] = Field(
        None, description="Node IDs to wait for in join nodes"
    )
    join_strategy: Optional[str] = Field(
        None, description="Join strategy: all, any, or n_of_m"
    )
    join_n: Optional[int] = Field(
        None, description="N value for n_of_m join strategy"
    )
    # Loop node fields
    max_iterations: Optional[int] = Field(
        None, description="Maximum iterations for loop nodes"
    )
    loop_delay: Optional[str] = Field(
        None, description="Delay between loop iterations"
    )
    # Parallel execution grouping
    parallel_group_id: Optional[str] = Field(
        None,
        description="ID grouping nodes that execute in parallel. Nodes with the same ID should be rendered side-by-side.",
    )


class WorkflowNodeExecutionResultData(BaseModel):
    """
    Data part signaling the completion of a workflow node execution.
    Corresponds to workflow_node_execution_result.json schema.
    """

    type: Literal["workflow_node_execution_result"] = Field(
        "workflow_node_execution_result",
        description="The constant type for this data part.",
    )
    node_id: str = Field(..., description="ID of the node")
    status: Literal["success", "error", "skipped"] = Field(
        ..., description="Execution status"
    )
    output_artifact_ref: Optional[ArtifactRef] = Field(
        None, description="Reference to the output artifact"
    )
    error_message: Optional[str] = Field(None, description="Error message if error")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata (e.g., condition result)"
    )


class WorkflowMapProgressData(BaseModel):
    """
    Data part signaling progress of a map node.
    Corresponds to workflow_map_progress.json schema.
    """

    type: Literal["workflow_map_progress"] = Field(
        "workflow_map_progress", description="The constant type for this data part."
    )
    node_id: str = Field(..., description="ID of the map node")
    total_items: int = Field(..., description="Total items to process")
    completed_items: int = Field(..., description="Items processed so far")
    status: Literal["in-progress", "completed", "failed"] = Field(
        ..., description="Status of the map operation"
    )


class WorkflowExecutionResultData(BaseModel):
    """
    Data part signaling the completion of a workflow execution.
    Corresponds to workflow_execution_result.json schema.
    """

    type: Literal["workflow_execution_result"] = Field(
        "workflow_execution_result", description="The constant type for this data part."
    )
    status: Literal["success", "error", "cancelled"] = Field(
        ..., description="Final status"
    )
    output_artifact_ref: Optional[ArtifactRef] = Field(
        None, description="Reference to the final output artifact"
    )
    error_message: Optional[str] = Field(None, description="Error message if error")
    workflow_output: Optional[Dict[str, Any]] = Field(
        None, description="Final output data of the workflow"
    )


class DeepResearchProgressData(BaseModel):
    """
    Data model for deep research progress updates with structured information.
    Provides detailed progress for UI visualization during iterative research.
    """

    type: Literal["deep_research_progress"] = Field(
        "deep_research_progress", description="The constant type for this data part."
    )
    phase: str = Field(..., description="Current phase: planning, searching, analyzing, writing")
    status_text: str = Field(..., description="Human-readable status message")
    progress_percentage: int = Field(..., description="Overall progress percentage (0-100)")
    current_iteration: int = Field(..., description="Current iteration number")
    total_iterations: int = Field(..., description="Total planned iterations")
    sources_found: int = Field(..., description="Total sources found so far")
    current_query: str = Field(default="", description="Current search query being executed")
    fetching_urls: list[Dict[str, str]] = Field(
        default_factory=list,
        description="List of sources being analyzed (with title, favicon/icon, and source_type)"
    )
    elapsed_seconds: int = Field(..., description="Elapsed time in seconds")
    max_runtime_seconds: int = Field(default=0, description="Maximum runtime limit (0 = no limit)")


class RAGInfoUpdateData(BaseModel):
    """
    Data model for RAG info panel updates during deep research.
    Sends title and sources to the UI early so the RAG info panel can display them
    while research is still in progress.
    """

    type: Literal["rag_info_update"] = Field(
        "rag_info_update", description="The constant type for this data part."
    )
    title: str = Field(..., description="Human-readable title for the research (generated by LLM)")
    query: str = Field(..., description="The original research question/query")
    search_type: str = Field(default="deep_research", description="Type of search (deep_research, web_search, etc.)")
    sources: list[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of sources found so far (in camelCase format for frontend)"
    )
    is_complete: bool = Field(default=False, description="Whether the research is complete")
    timestamp: str = Field(..., description="ISO timestamp of this update")


class DeepResearchReportData(BaseModel):
    """
    Data model for a deep research report completion signal.
    This is sent when a deep research report artifact has been created and saved.
    The frontend will use this to render the DeepResearchReportBubble component
    instead of displaying the report content inline.
    
    This signal bypasses the LLM response entirely, ensuring the report is displayed
    via the artifact viewer without duplication.
    """

    type: Literal["deep_research_report"] = Field(
        "deep_research_report", description="The constant type for this data part."
    )
    filename: str = Field(..., description="The filename of the research report artifact.")
    version: int = Field(..., description="The version number of the artifact.")
    uri: str = Field(..., description="The artifact URI for fetching the report content.")
    title: Optional[str] = Field(None, description="Human-readable title for the research.")
    sources_count: int = Field(default=0, description="Number of sources analyzed.")


SignalData = Union[
    ToolInvocationStartData,
    LlmInvocationData,
    LlmResponseData,
    AgentProgressUpdateData,
    ArtifactCreationProgressData,
    ArtifactSavedData,
    ToolResultData,
    TemplateBlockData,
    StructuredInvocationRequest,
    StructuredInvocationResult,
    WorkflowExecutionStartData,
    WorkflowNodeExecutionStartData,
    WorkflowNodeExecutionResultData,
    WorkflowMapProgressData,
    WorkflowExecutionResultData,
    DeepResearchProgressData,
    RAGInfoUpdateData,
    DeepResearchReportData,
]
