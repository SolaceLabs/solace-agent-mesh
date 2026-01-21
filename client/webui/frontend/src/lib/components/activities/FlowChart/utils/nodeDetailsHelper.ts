import type { VisualizerStep } from "@/lib/types";
import type { LayoutNode } from "./types";

/**
 * Represents an artifact created by a tool
 */
export interface CreatedArtifact {
    filename: string;
    version?: number;
    mimeType?: string;
    description?: string;
}

/**
 * Represents the request and result information for a node
 */
export interface NodeDetails {
    nodeType: LayoutNode['type'];
    label: string;
    description?: string; // NP-4: Node description to display under the name
    requestStep?: VisualizerStep;
    resultStep?: VisualizerStep;
    outputArtifactStep?: VisualizerStep; // For workflow nodes - the WORKFLOW_NODE_EXECUTION_RESULT with output artifact
    relatedSteps?: VisualizerStep[]; // For additional context
    createdArtifacts?: CreatedArtifact[]; // For tool nodes - artifacts created by this tool
}

/**
 * Find all steps related to a given node and organize them into request/result pairs
 */
export function findNodeDetails(
    node: LayoutNode,
    allSteps: VisualizerStep[]
): NodeDetails {
    const visualizerStepId = node.data.visualizerStepId;

    if (!visualizerStepId) {
        return {
            nodeType: node.type,
            label: node.data.label,
            description: node.data.description,
        };
    }

    // Find the primary step for this node
    const primaryStep = allSteps.find(s => s.id === visualizerStepId);

    if (!primaryStep) {
        return {
            nodeType: node.type,
            label: node.data.label,
            description: node.data.description,
        };
    }

    switch (node.type) {
        case 'user':
            return findUserNodeDetails(node, primaryStep, allSteps);
        case 'agent':
            return findAgentNodeDetails(node, primaryStep, allSteps);
        case 'llm':
            return findLLMNodeDetails(node, primaryStep, allSteps);
        case 'tool':
            return findToolNodeDetails(node, primaryStep, allSteps);
        case 'switch':
            return findSwitchNodeDetails(node, primaryStep, allSteps);
        case 'loop':
            return findLoopNodeDetails(node, primaryStep, allSteps);
        case 'group':
            return findWorkflowGroupDetails(node, primaryStep, allSteps);
        default:
            return {
                nodeType: node.type,
                label: node.data.label,
                description: node.data.description,
                requestStep: primaryStep,
            };
    }
}

/**
 * Find details for User nodes
 */
function findUserNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Top user node: show initial request
    if (node.data.isTopNode) {
        return {
            nodeType: 'user',
            label: 'User Input',
            requestStep: primaryStep,
        };
    }

    // Bottom user node: show final response
    if (node.data.isBottomNode) {
        // Find the last AGENT_RESPONSE_TEXT at nesting level 0
        const finalResponse = [...allSteps]
            .reverse()
            .find(s => s.type === 'AGENT_RESPONSE_TEXT' && s.nestingLevel === 0);

        return {
            nodeType: 'user',
            label: 'Final Output',
            resultStep: finalResponse,
        };
    }

    return {
        nodeType: 'user',
        label: node.data.label,
        requestStep: primaryStep,
    };
}

/**
 * Find details for Agent nodes
 */
function findAgentNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    const isWorkflowAgent = primaryStep.type === 'WORKFLOW_NODE_EXECUTION_START';
    const workflowNodeData = isWorkflowAgent ? primaryStep.data.workflowNodeExecutionStart : undefined;
    const subTaskId = workflowNodeData?.subTaskId;

    // For workflow agents, we need to search in the subTaskId's events
    // For regular agents, use the node's owningTaskId
    const agentTaskId = subTaskId || node.owningTaskId;

    // Find the request step
    let requestStep: VisualizerStep | undefined;

    // First try to find a USER_REQUEST step (exists for root-level agents)
    const userRequest = allSteps.find(
        s => s.owningTaskId === agentTaskId && s.type === 'USER_REQUEST'
    );

    if (userRequest) {
        requestStep = userRequest;
    } else if (isWorkflowAgent) {
        // For workflow agents, look for the WORKFLOW_AGENT_REQUEST step which contains the actual input
        const workflowAgentRequest = allSteps.find(
            s => s.owningTaskId === agentTaskId && s.type === 'WORKFLOW_AGENT_REQUEST'
        );
        // Fall back to WORKFLOW_NODE_EXECUTION_START if no WORKFLOW_AGENT_REQUEST found
        requestStep = workflowAgentRequest || primaryStep;
    } else {
        // Check if this is a sub-agent created via tool invocation
        const toolInvocation = allSteps.find(
            s => s.owningTaskId === agentTaskId && s.type === 'AGENT_TOOL_INVOCATION_START'
        );

        if (toolInvocation && toolInvocation.parentTaskId) {
            // Try to find the USER_REQUEST from the parent task
            const parentUserRequest = allSteps.find(
                s => s.owningTaskId === toolInvocation.parentTaskId && s.type === 'USER_REQUEST'
            );
            requestStep = parentUserRequest || toolInvocation;
        } else {
            // Fallback to primaryStep
            requestStep = primaryStep;
        }
    }

    // Find the response (AGENT_RESPONSE_TEXT for this agent's task)
    const responseStep = allSteps.find(
        s => s.owningTaskId === agentTaskId && s.type === 'AGENT_RESPONSE_TEXT'
    );

    // For workflow agents, find the WORKFLOW_NODE_EXECUTION_RESULT which contains output artifact
    let outputArtifactStep: VisualizerStep | undefined;
    if (isWorkflowAgent && workflowNodeData?.nodeId) {
        // The result step is at the workflow level, not the agent's task level
        // Find by matching BOTH nodeId AND owningTaskId to handle parallel workflow executions
        const workflowExecutionId = primaryStep.owningTaskId;
        outputArtifactStep = allSteps.find(
            s => s.type === 'WORKFLOW_NODE_EXECUTION_RESULT' &&
                 s.owningTaskId === workflowExecutionId &&
                 s.data.workflowNodeExecutionResult?.nodeId === workflowNodeData.nodeId
        );
    }

    // Find all steps for this agent's task for additional context
    const relatedSteps = allSteps.filter(s => s.owningTaskId === agentTaskId);

    return {
        nodeType: 'agent' as const,
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep: responseStep,
        outputArtifactStep,
        relatedSteps,
    };
}

/**
 * Find details for LLM nodes
 */
function findLLMNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Primary step could be AGENT_LLM_CALL or AGENT_LLM_RESPONSE_TOOL_DECISION (for synthetic LLM nodes)
    let requestStep: VisualizerStep | undefined;
    let resultStep: VisualizerStep | undefined;

    if (primaryStep.type === 'AGENT_LLM_CALL') {
        // Normal case: we have the LLM call step
        requestStep = primaryStep;

        const owningTaskId = requestStep.owningTaskId;
        const requestIndex = allSteps.indexOf(requestStep);

        // Look for the next LLM response in the same task (either type)
        resultStep = allSteps
            .slice(requestIndex + 1)
            .find(s =>
                s.owningTaskId === owningTaskId &&
                (s.type === 'AGENT_LLM_RESPONSE_TO_AGENT' || s.type === 'AGENT_LLM_RESPONSE_TOOL_DECISION')
            );
    } else if (primaryStep.type === 'AGENT_LLM_RESPONSE_TOOL_DECISION' || primaryStep.type === 'AGENT_LLM_RESPONSE_TO_AGENT') {
        // Synthetic LLM node case: we only have the response step
        // Try to find the preceding AGENT_LLM_CALL for this task
        const owningTaskId = primaryStep.owningTaskId;
        const responseIndex = allSteps.indexOf(primaryStep);

        // Look backwards for the most recent AGENT_LLM_CALL in the same task
        for (let i = responseIndex - 1; i >= 0; i--) {
            const s = allSteps[i];
            if (s.owningTaskId === owningTaskId && s.type === 'AGENT_LLM_CALL') {
                requestStep = s;
                break;
            }
        }

        // The result step is the primary step itself
        resultStep = primaryStep;
    }

    return {
        nodeType: 'llm',
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep,
    };
}

/**
 * Find details for Tool nodes
 */
function findToolNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Primary step should be AGENT_TOOL_INVOCATION_START
    const requestStep = primaryStep.type === 'AGENT_TOOL_INVOCATION_START' ? primaryStep : undefined;

    // Find the result by matching functionCallId
    // Check both the step's functionCallId and the data's functionCallId
    let resultStep: VisualizerStep | undefined;

    const functionCallId = requestStep?.functionCallId || requestStep?.data.toolInvocationStart?.functionCallId;

    if (functionCallId) {
        resultStep = allSteps.find(
            s => s.type === 'AGENT_TOOL_EXECUTION_RESULT' &&
            s.data.toolResult?.functionCallId === functionCallId
        );
    }

    // Get created artifacts from node data (populated by layoutEngine)
    const createdArtifacts = node.data.createdArtifacts;

    return {
        nodeType: 'tool',
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep,
        createdArtifacts,
    };
}

/**
 * Find details for Switch nodes
 */
function findSwitchNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Primary step should be WORKFLOW_NODE_EXECUTION_START with nodeType: switch
    const requestStep = primaryStep.type === 'WORKFLOW_NODE_EXECUTION_START' ? primaryStep : undefined;

    // Find the result by matching nodeId
    let resultStep: VisualizerStep | undefined;

    if (requestStep?.data.workflowNodeExecutionStart) {
        const nodeId = requestStep.data.workflowNodeExecutionStart.nodeId;
        const owningTaskId = requestStep.owningTaskId;

        resultStep = allSteps.find(
            s => s.type === 'WORKFLOW_NODE_EXECUTION_RESULT' &&
            s.owningTaskId === owningTaskId &&
            s.data.workflowNodeExecutionResult?.nodeId === nodeId
        );
    }

    return {
        nodeType: 'switch',
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep,
    };
}

/**
 * Find details for Loop nodes
 */
function findLoopNodeDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Primary step should be WORKFLOW_NODE_EXECUTION_START with nodeType: loop
    const requestStep = primaryStep.type === 'WORKFLOW_NODE_EXECUTION_START' ? primaryStep : undefined;

    // Find the result by matching nodeId
    let resultStep: VisualizerStep | undefined;

    if (requestStep?.data.workflowNodeExecutionStart) {
        const nodeId = requestStep.data.workflowNodeExecutionStart.nodeId;
        const owningTaskId = requestStep.owningTaskId;

        resultStep = allSteps.find(
            s => s.type === 'WORKFLOW_NODE_EXECUTION_RESULT' &&
            s.owningTaskId === owningTaskId &&
            s.data.workflowNodeExecutionResult?.nodeId === nodeId
        );
    }

    // Find related steps for loop iterations
    const relatedSteps = requestStep ? allSteps.filter(
        s => s.owningTaskId === requestStep.owningTaskId &&
        s.type === 'WORKFLOW_NODE_EXECUTION_START' &&
        s.data.workflowNodeExecutionStart?.parentNodeId === requestStep.data.workflowNodeExecutionStart?.nodeId
    ) : undefined;

    return {
        nodeType: 'loop',
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep,
        relatedSteps,
    };
}

/**
 * Find details for Workflow Group nodes
 */
function findWorkflowGroupDetails(
    node: LayoutNode,
    primaryStep: VisualizerStep,
    allSteps: VisualizerStep[]
): NodeDetails {
    // Primary step should be WORKFLOW_EXECUTION_START
    const requestStep = primaryStep.type === 'WORKFLOW_EXECUTION_START' ? primaryStep : undefined;

    // Find the result by matching executionId
    let resultStep: VisualizerStep | undefined;

    if (requestStep?.data.workflowExecutionStart) {
        const executionId = requestStep.data.workflowExecutionStart.executionId;

        resultStep = allSteps.find(
            s => s.type === 'WORKFLOW_EXECUTION_RESULT' &&
            s.owningTaskId === executionId
        );
    }

    // Find all workflow node steps for context
    const relatedSteps = allSteps.filter(
        s => s.owningTaskId === requestStep?.data.workflowExecutionStart?.executionId &&
        (s.type.startsWith('WORKFLOW_NODE_') || s.type === 'WORKFLOW_MAP_PROGRESS')
    );

    return {
        nodeType: 'group',
        label: node.data.label,
        description: node.data.description,
        requestStep,
        resultStep,
        relatedSteps,
    };
}
