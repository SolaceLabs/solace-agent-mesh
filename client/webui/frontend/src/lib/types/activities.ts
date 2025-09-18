/* eslint-disable @typescript-eslint/no-explicit-any */
import type { TaskState } from "./be";

/**
 * Defines the structure for performance metrics of a single LLM call.
 */
export interface LlmCallPerformance {
    modelName: string;
    durationMs: number;
    timestamp: string; // ISO 8601 timestamp of when the LLM call started
}

/**
 * Defines the structure for performance metrics of a single tool call.
 * This includes both internal tool executions and peer agent delegations.
 */
export interface ToolCallPerformance {
    toolName: string;
    durationMs: number;
    isPeer: boolean; // True if this was a delegation to a peer agent
    peerAgentName?: string; // Name of the peer agent, if isPeer is true
    subTaskId?: string; // Sub-task ID, if isPeer is true and a sub-task was created
    timestamp: string; // ISO 8601 timestamp of when the tool call/delegation started
    parallelBlockId?: string; // ID for grouping parallel calls, corresponds to a tool_decision step ID
}

/**
 * Defines the structure for aggregated performance metrics for a single agent.
 */
export interface AgentPerformanceMetrics {
    agentName: string;
    instanceId: string; // A unique identifier for this agent instance, e.g., "AgentName:owningTaskId"
    displayName: string; // A user-facing name, potentially with a number to differentiate parallel instances
    llmCalls: LlmCallPerformance[];
    toolCalls: ToolCallPerformance[];
    totalLlmTimeMs: number; // Sum of durations of all LLM calls made by this agent
    totalToolTimeMs: number; // Sum of durations of all tool calls (internal + peer delegations) initiated by this agent
}

/**
 * Defines the overall structure for the performance report of a task.
 */
export interface PerformanceReport {
    overall: {
        totalTaskDurationMs: number;
    };
    agents: Record<string, AgentPerformanceMetrics>; // Keyed by agent name
}

/**
 * Defines the different types of steps that can appear in the task visualizer.
 */
export type VisualizerStepType =
    | "USER_REQUEST" // User's initial input to the agent/system
    | "AGENT_LLM_CALL" // An agent making a call to an LLM
    | "AGENT_LLM_RESPONSE_TOOL_DECISION" // LLM response includes a decision to call a tool
    | "AGENT_LLM_RESPONSE_TO_AGENT" // LLM response back to the calling agent
    | "AGENT_TOOL_INVOCATION_START" // Agent starts executing a tool
    | "AGENT_TOOL_EXECUTION_RESULT" // Result of an agent executing a tool (internal or peer)
    | "AGENT_ARTIFACT_NOTIFICATION" // Agent signals an update related to an artifact
    | "AGENT_RESPONSE_TEXT" // Agent provides textual output (intermediate or final for a turn)
    | "AGENT_STATUS_UPDATE" // A simple status update from the agent (e.g., "Thinking...")
    | "TASK_COMPLETED" // Task has successfully completed
    | "TASK_FAILED"; // Task has failed

/**
 * Represents specific data associated with an 'AGENT_LLM_CALL' step.
 */
export interface LLMCallData {
    modelName: string;
    promptPreview: string; // Could be a snippet or summary
    // Potentially add request/response token counts if available
}

/**
 * Represents specific data associated with an 'AGENT_LLM_RESPONSE_TO_AGENT' step.
 */
export interface LLMResponseToAgentData {
    modelName?: string; // Optional, as it might be part of the preceding LLMCallData
    responsePreview: string; // Snippet or summary of the LLM's response to the agent
    isFinalResponse?: boolean; // Indicates if this is the complete final response from the LLM to agent for that turn
    // Potentially add response token counts if available
}

/**
 * Represents a single tool call decision made by the LLM.
 */
export interface ToolDecision {
    functionCallId: string;
    toolName: string;
    toolArguments: Record<string, any>;
    isPeerDelegation: boolean;
}

/**
 * Represents specific data associated with an 'AGENT_LLM_RESPONSE_TOOL_DECISION' step.
 * This can contain one or more tool call decisions.
 */
export interface ToolDecisionData {
    decisions: ToolDecision[];
    isParallel: boolean; // True if decisions.length > 1
    isPeerDelegation?: boolean;
}

/**
 * Represents specific data associated with an 'AGENT_TOOL_INVOCATION_START' step.
 */
export interface ToolInvocationStartData {
    functionCallId: string;
    toolName: string;
    toolArguments: Record<string, any>;
    isPeerInvocation?: boolean; // True if this tool invocation is targeting a peer agent
}

/**
 * Represents specific data associated with an 'AGENT_TOOL_EXECUTION_RESULT' step.
 */
export interface ToolResultData {
    functionCallId?: string; // The ID of the function call this result corresponds to
    toolName: string;
    resultData: any; // The data returned by the tool
    isPeerResponse?: boolean; // True if this is a response from a peer agent tool call
}

/**
 * Represents specific data associated with an 'AGENT_ARTIFACT_NOTIFICATION' step.
 */
export interface ArtifactNotificationData {
    artifactName: string;
    version?: number;
    description?: string;
    mimeType?: string;
}

/**
 * Represents specific data associated with a 'TASK_FAILED' step.
 */
export interface ErrorDetailsData {
    message: string;
    code?: number | string;
    details?: any; // Additional error information
}

/**
 * Information about a peer delegation, linking a function call to a sub-task.
 */
export interface DelegationInfo {
    functionCallId: string;
    peerAgentName: string;
    subTaskId?: string; // Optional: The ID of the sub-task created for this delegation
}

/**
 * Represents a single logical step in the visualized task flow.
 */
export interface VisualizerStep {
    id: string; // Unique identifier for this visualizer step
    type: VisualizerStepType;
    timestamp: string; // ISO 8601 timestamp of the primary event forming this step
    durationMs?: number; // Optional: Calculated duration of this step in milliseconds
    title: string; // Concise, human-readable title for the step (e.g., "User Input", "OrchestratorAgent: LLM Call")
    source?: string; // Entity initiating the step (e.g., "User", "OrchestratorAgent")
    target?: string; // Entity receiving or targeted by the step (e.g., "OrchestratorAgent", "LLM", "ImageGeneratorAgent")
    data: {
        text?: string; // For USER_REQUEST, AGENT_RESPONSE_TEXT
        llmCall?: LLMCallData; // For AGENT_LLM_CALL
        llmResponseToAgent?: LLMResponseToAgentData; // For AGENT_LLM_RESPONSE_TO_AGENT
        toolDecision?: ToolDecisionData; // For AGENT_LLM_RESPONSE_TOOL_DECISION
        toolInvocationStart?: ToolInvocationStartData; // For AGENT_TOOL_INVOCATION_START
        toolResult?: ToolResultData; // For AGENT_TOOL_EXECUTION_RESULT
        artifactNotification?: ArtifactNotificationData; // For AGENT_ARTIFACT_NOTIFICATION
        errorDetails?: ErrorDetailsData; // For TASK_FAILED
        statusText?: string; // For AGENT_STATUS_UPDATE
        finalMessage?: string; // For TASK_COMPLETED (if there's a final summary message)
    };
    rawEventIds: string[]; // Array of IDs/indices referencing the raw A2AEventSSEPayload(s) that constitute this logical step
    functionCallId?: string; // The function call ID this step is related to, especially for sub-task steps.
    delegationInfo?: DelegationInfo[]; // Information about peer delegations, can be multiple for parallel calls
    isSubTaskStep?: boolean; // True if this step is part of a sub-task's execution flow
    nestingLevel: number; // ADDED: 0 for root, 1 for first sub-task, 2 for sub-task of sub-task, etc.
    owningTaskId: string; // ADDED: The ID of the task this step is part of
}

/**
 * Represents a task that has been processed for visualization,
 * including its overall details and a sequence of logical steps.
 */
export interface VisualizedTask {
    taskId: string;
    initialRequestText: string; // The initial text part of the user's request
    status: TaskState; // Overall status of the task (e.g., 'working', 'completed', 'failed')
    currentStatusText?: string; // Optional: The latest status text from the agent
    startTime: string; // ISO 8601 timestamp of when the task started
    endTime?: string; // ISO 8601 timestamp of when the task ended (if applicable)
    durationMs?: number; // Optional: Total duration of the task in milliseconds
    steps: VisualizerStep[]; // Chronological sequence of logical steps for this task
    performanceReport?: PerformanceReport | null;
}
