import type { VisualizerStep } from "@/lib/types";
import type { LayoutNode, Edge, BuildContext, LayoutResult } from "./types";

// Layout constants
const NODE_WIDTHS = {
    AGENT: 220,
    TOOL: 180,
    LLM: 180,
    USER: 140,
    SWITCH: 120,
    LOOP: 120,
    MAP: 120,
    MIN_AGENT_CONTENT: 200,
};

const NODE_HEIGHTS = {
    AGENT_HEADER: 50,
    TOOL: 50,
    LLM: 50,
    USER: 50,
    SWITCH: 80,
    LOOP: 80,
    MAP: 80,
};

const SPACING = {
    VERTICAL: 16, // Space between children within agent
    HORIZONTAL: 20, // Space between parallel branches
    AGENT_VERTICAL: 60, // Space between top-level agents
    PADDING: 20, // Padding inside agent nodes
};

/**
 * Main entry point: Process VisualizerSteps into layout tree
 */
export function processSteps(steps: VisualizerStep[], agentNameMap: Record<string, string> = {}): LayoutResult {
    const context: BuildContext = {
        steps,
        stepIndex: 0,
        nodeCounter: 0,
        taskToNodeMap: new Map(),
        functionCallToNodeMap: new Map(),
        currentAgentNode: null,
        rootNodes: [],
        agentNameMap,
        parallelContainerMap: new Map(),
        currentBranchMap: new Map(),
        hasTopUserNode: false,
        hasBottomUserNode: false,
        parallelPeerGroupMap: new Map(),
        parallelBlockMap: new Map(),
        subWorkflowParentMap: new Map(),
    };

    // Process all steps to build tree structure
    for (let i = 0; i < steps.length; i++) {
        context.stepIndex = i;
        const step = steps[i];
        processStep(step, context);
    }

    // DEBUG: Print tree structure
    console.log("=== LAYOUT ENGINE DEBUG ===");
    console.log("Steps processed:", steps.length);
    console.log("Root nodes:", context.rootNodes.length);
    console.log("taskToNodeMap keys:", Array.from(context.taskToNodeMap.keys()));
    console.log("subWorkflowParentMap keys:", Array.from(context.subWorkflowParentMap.keys()));

    const printTree = (node: LayoutNode, indent: string = "") => {
        console.log(`${indent}[${node.type}] ${node.data.label} (id=${node.id}, owningTaskId=${node.owningTaskId || "none"})`);
        for (const child of node.children) {
            printTree(child, indent + "  ");
        }
    };

    console.log("Tree structure:");
    for (const node of context.rootNodes) {
        printTree(node);
    }
    console.log("=== END DEBUG ===");

    // Calculate layout (positions and dimensions)
    const nodes = calculateLayout(context.rootNodes);

    // Calculate edges between top-level nodes
    const edges = calculateEdges(nodes);

    // Calculate total canvas size
    const { totalWidth, totalHeight } = calculateCanvasSize(nodes);

    return {
        nodes,
        edges,
        totalWidth,
        totalHeight,
    };
}

/**
 * Process a single VisualizerStep
 */
function processStep(step: VisualizerStep, context: BuildContext): void {
    // Log workflow-related steps
    if (step.type.startsWith("WORKFLOW")) {
        console.log("[processStep]", step.type, "owningTaskId=", step.owningTaskId, "data=", step.data);
    }

    switch (step.type) {
        case "USER_REQUEST":
            handleUserRequest(step, context);
            break;
        case "AGENT_LLM_CALL":
            handleLLMCall(step, context);
            break;
        case "AGENT_TOOL_INVOCATION_START":
            handleToolInvocation(step, context);
            break;
        case "AGENT_TOOL_EXECUTION_RESULT":
            handleToolResult(step, context);
            break;
        case "AGENT_LLM_RESPONSE_TO_AGENT":
        case "AGENT_LLM_RESPONSE_TOOL_DECISION":
            handleLLMResponse(step, context);
            break;
        case "AGENT_RESPONSE_TEXT":
            handleAgentResponse(step, context);
            break;
        case "WORKFLOW_EXECUTION_START":
            handleWorkflowStart(step, context);
            break;
        case "WORKFLOW_NODE_EXECUTION_START":
            handleWorkflowNodeStart(step, context);
            break;
        case "WORKFLOW_EXECUTION_RESULT":
            handleWorkflowExecutionResult(step, context);
            break;
        case "WORKFLOW_NODE_EXECUTION_RESULT":
            handleWorkflowNodeResult(step, context);
            break;
        case "AGENT_ARTIFACT_NOTIFICATION":
            handleArtifactNotification(step, context);
            break;
        // Add other cases as needed
    }
}

/**
 * Handle USER_REQUEST step - creates User node + Agent node
 */
function handleUserRequest(step: VisualizerStep, context: BuildContext): void {
    // Only create top User node once, and only for top-level requests
    if (!context.hasTopUserNode && step.nestingLevel === 0) {
        const userNode = createNode(
            context,
            "user",
            {
                label: "User",
                visualizerStepId: step.id,
                isTopNode: true,
            },
            step.owningTaskId
        );
        context.rootNodes.push(userNode);
        context.hasTopUserNode = true;
    }

    // Create Agent node
    const agentName = step.target || "Agent";
    const displayName = context.agentNameMap[agentName] || agentName;

    const agentNode = createNode(
        context,
        "agent",
        {
            label: displayName,
            visualizerStepId: step.id,
        },
        step.owningTaskId
    );

    // Add agent to root nodes
    context.rootNodes.push(agentNode);

    // Set as current agent
    context.currentAgentNode = agentNode;

    // Map task ID to this agent
    if (step.owningTaskId) {
        context.taskToNodeMap.set(step.owningTaskId, agentNode);
    }
}

/**
 * Handle AGENT_LLM_CALL - adds LLM child to current agent
 */
function handleLLMCall(step: VisualizerStep, context: BuildContext): void {
    const agentNode = findAgentForStep(step, context);
    if (!agentNode) return;

    const llmNode = createNode(
        context,
        "llm",
        {
            label: "LLM",
            visualizerStepId: step.id,
            status: "in-progress",
        },
        step.owningTaskId
    );

    // Add as child
    agentNode.children.push(llmNode);

    // Track by functionCallId for result matching
    if (step.functionCallId) {
        context.functionCallToNodeMap.set(step.functionCallId, llmNode);
    }
}

/**
 * Handle AGENT_LLM_RESPONSE_TO_AGENT or AGENT_LLM_RESPONSE_TOOL_DECISION - marks LLM as completed
 */
function handleLLMResponse(step: VisualizerStep, context: BuildContext): void {
    const agentNode = findAgentForStep(step, context);
    if (!agentNode) {
        return;
    }

    // Find the most recent LLM node in this agent and mark it as completed
    let foundInProgressLLM = false;
    for (let i = agentNode.children.length - 1; i >= 0; i--) {
        const child = agentNode.children[i];
        if (child.type === "llm" && child.data.status === "in-progress") {
            child.data.status = "completed";
            foundInProgressLLM = true;
            break;
        }
    }

    // If no in-progress LLM was found, it means we received an LLM response without
    // a corresponding AGENT_LLM_CALL. This can happen if the llm_invocation signal
    // wasn't emitted. Create a synthetic LLM node to represent this call.
    if (!foundInProgressLLM) {
        const syntheticLlmNode = createNode(
            context,
            "llm",
            {
                label: "LLM",
                visualizerStepId: step.id, // Link to the response step since we don't have a call step
                status: "completed",
            },
            step.owningTaskId
        );

        // Insert the LLM node before any parallel blocks (which are created by TOOL_DECISION)
        // Find the position before the first parallelBlock child
        let insertIndex = agentNode.children.length;
        for (let i = 0; i < agentNode.children.length; i++) {
            if (agentNode.children[i].type === "parallelBlock") {
                insertIndex = i;
                break;
            }
        }
        agentNode.children.splice(insertIndex, 0, syntheticLlmNode);
    }

    // Check for parallel tool calls in TOOL_DECISION
    if (step.type === "AGENT_LLM_RESPONSE_TOOL_DECISION") {
        const toolDecision = step.data.toolDecision;
        if (toolDecision?.isParallel && toolDecision.decisions) {
            // Filter for peer delegations
            const peerDecisions = toolDecision.decisions.filter(d => d.isPeerDelegation);

            // Filter for workflow calls (non-peer, toolName contains 'workflow_')
            const workflowDecisions = toolDecision.decisions.filter(d => !d.isPeerDelegation && d.toolName.includes("workflow_"));

            // Handle parallel peer delegations
            if (peerDecisions.length > 1) {
                const groupKey = `${step.owningTaskId}:parallel-peer:${step.id}`;
                const functionCallIds = new Set(peerDecisions.map(d => d.functionCallId));

                context.parallelPeerGroupMap.set(groupKey, functionCallIds);

                const parallelBlockNode = createNode(
                    context,
                    "parallelBlock",
                    {
                        label: "Parallel",
                        visualizerStepId: step.id,
                    },
                    step.owningTaskId
                );

                agentNode.children.push(parallelBlockNode);
                context.parallelBlockMap.set(groupKey, parallelBlockNode);
            }

            // Handle parallel workflow calls
            if (workflowDecisions.length > 1) {
                const groupKey = `${step.owningTaskId}:parallel-workflow:${step.id}`;
                const functionCallIds = new Set(workflowDecisions.map(d => d.functionCallId));

                context.parallelPeerGroupMap.set(groupKey, functionCallIds);

                const parallelBlockNode = createNode(
                    context,
                    "parallelBlock",
                    {
                        label: "Parallel",
                        visualizerStepId: step.id,
                    },
                    step.owningTaskId
                );

                agentNode.children.push(parallelBlockNode);
                context.parallelBlockMap.set(groupKey, parallelBlockNode);
            }
        }
    }
}

/**
 * Handle AGENT_TOOL_INVOCATION_START
 */
function handleToolInvocation(step: VisualizerStep, context: BuildContext): void {
    const isPeer = step.data.toolInvocationStart?.isPeerInvocation || step.target?.startsWith("peer_");
    const target = step.target || "";
    const toolName = step.data.toolInvocationStart?.toolName || target;
    const parallelGroupId = step.data.toolInvocationStart?.parallelGroupId;

    // Skip workflow tools (handled separately)
    if (target.includes("workflow_") || toolName.includes("workflow_")) {
        return;
    }

    const agentNode = findAgentForStep(step, context);
    if (!agentNode) return;

    if (isPeer) {
        // Create nested agent node
        const peerName = target.startsWith("peer_") ? target.substring(5) : target;
        const displayName = context.agentNameMap[peerName] || peerName;

        const subAgentNode = createNode(
            context,
            "agent",
            {
                label: displayName,
                visualizerStepId: step.id,
            },
            step.delegationInfo?.[0]?.subTaskId || step.owningTaskId
        );

        // Check if this peer invocation is part of a parallel group
        // First check for backend-provided parallelGroupId, then fall back to legacy detection
        const functionCallId = step.data.toolInvocationStart?.functionCallId || step.functionCallId;
        let addedToParallelBlock = false;

        // Use parallelGroupId from backend if available
        if (parallelGroupId) {
            let parallelBlock = context.parallelBlockMap.get(parallelGroupId);
            if (!parallelBlock) {
                // Create a new parallel block for this group
                parallelBlock = createNode(
                    context,
                    "parallelBlock",
                    {
                        label: "Parallel",
                        visualizerStepId: step.id,
                    },
                    step.owningTaskId
                );
                context.parallelBlockMap.set(parallelGroupId, parallelBlock);
                agentNode.children.push(parallelBlock);
            }
            parallelBlock.children.push(subAgentNode);
            addedToParallelBlock = true;
        } else if (functionCallId) {
            // Fall back to legacy parallel peer group detection
            for (const [groupKey, functionCallIds] of context.parallelPeerGroupMap.entries()) {
                if (functionCallIds.has(functionCallId)) {
                    // This peer invocation is part of a parallel group
                    const parallelBlock = context.parallelBlockMap.get(groupKey);
                    if (parallelBlock) {
                        // Add the sub-agent as a child of the parallelBlock
                        parallelBlock.children.push(subAgentNode);
                        addedToParallelBlock = true;
                    }
                    break;
                }
            }
        }

        // If not part of a parallel group, add as regular child
        if (!addedToParallelBlock) {
            agentNode.children.push(subAgentNode);
        }

        // Map sub-task to this new agent
        const subTaskId = step.delegationInfo?.[0]?.subTaskId;
        if (subTaskId) {
            context.taskToNodeMap.set(subTaskId, subAgentNode);
        }

        // Track by functionCallId
        if (functionCallId) {
            context.functionCallToNodeMap.set(functionCallId, subAgentNode);
        }
    } else {
        // Regular tool
        const toolNode = createNode(
            context,
            "tool",
            {
                label: toolName,
                visualizerStepId: step.id,
                status: "in-progress",
            },
            step.owningTaskId
        );

        // Check if this tool is part of a parallel group
        if (parallelGroupId) {
            let parallelBlock = context.parallelBlockMap.get(parallelGroupId);
            if (!parallelBlock) {
                // Create a new parallel block for this group
                parallelBlock = createNode(
                    context,
                    "parallelBlock",
                    {
                        label: "Parallel Tools",
                        visualizerStepId: step.id,
                    },
                    step.owningTaskId
                );
                context.parallelBlockMap.set(parallelGroupId, parallelBlock);
                agentNode.children.push(parallelBlock);
            }
            parallelBlock.children.push(toolNode);
        } else {
            agentNode.children.push(toolNode);
        }

        // Use the tool's actual functionCallId from the data (preferred) for matching with tool_result
        // The step.functionCallId is the parent tracking ID for sub-task relationships
        const functionCallId = step.data.toolInvocationStart?.functionCallId || step.functionCallId;
        if (functionCallId) {
            context.functionCallToNodeMap.set(functionCallId, toolNode);
        }
    }
}

/**
 * Handle AGENT_TOOL_EXECUTION_RESULT - update status
 */
function handleToolResult(step: VisualizerStep, context: BuildContext): void {
    const functionCallId = step.data.toolResult?.functionCallId || step.functionCallId;
    if (!functionCallId) return;

    const node = context.functionCallToNodeMap.get(functionCallId);
    if (node) {
        node.data.status = "completed";
    }
}

/**
 * Handle AGENT_ARTIFACT_NOTIFICATION - associate artifact with the tool that created it
 */
function handleArtifactNotification(step: VisualizerStep, context: BuildContext): void {
    const functionCallId = step.functionCallId;
    if (!functionCallId) return;

    const node = context.functionCallToNodeMap.get(functionCallId);
    if (node && step.data.artifactNotification) {
        if (!node.data.createdArtifacts) {
            node.data.createdArtifacts = [];
        }
        node.data.createdArtifacts.push({
            filename: step.data.artifactNotification.artifactName,
            version: step.data.artifactNotification.version,
            mimeType: step.data.artifactNotification.mimeType,
            description: step.data.artifactNotification.description,
        });
    }
}

/**
 * Handle AGENT_RESPONSE_TEXT - create bottom User node (only once at the end)
 */
function handleAgentResponse(step: VisualizerStep, context: BuildContext): void {
    // Only for top-level tasks
    if (step.nestingLevel && step.nestingLevel > 0) return;

    // Only create bottom user node once, and only for the last response
    // We'll check if this is the last top-level AGENT_RESPONSE_TEXT
    const remainingSteps = context.steps.slice(context.stepIndex + 1);
    const hasMoreTopLevelResponses = remainingSteps.some(s => s.type === "AGENT_RESPONSE_TEXT" && s.nestingLevel === 0);

    if (!hasMoreTopLevelResponses && !context.hasBottomUserNode) {
        const userNode = createNode(
            context,
            "user",
            {
                label: "User",
                visualizerStepId: step.id,
                isBottomNode: true,
            },
            step.owningTaskId
        );

        context.rootNodes.push(userNode);
        context.hasBottomUserNode = true;
    }
}

/**
 * Handle WORKFLOW_EXECUTION_START
 */
function handleWorkflowStart(step: VisualizerStep, context: BuildContext): void {
    const workflowName = step.data.workflowExecutionStart?.workflowName || "Workflow";
    const displayName = context.agentNameMap[workflowName] || workflowName;
    const executionId = step.data.workflowExecutionStart?.executionId;

    console.log("[handleWorkflowStart] workflowName=", workflowName, "executionId=", executionId, "owningTaskId=", step.owningTaskId, "parentTaskId=", step.parentTaskId);

    // Check if this is a sub-workflow invoked by a parent workflow's 'workflow' node type
    // The parent relationship is recorded in subWorkflowParentMap by handleWorkflowNodeType
    const parentFromWorkflowNode = step.owningTaskId ? context.subWorkflowParentMap.get(step.owningTaskId) : null;

    console.log("[handleWorkflowStart] parentFromWorkflowNode=", parentFromWorkflowNode?.data.label, parentFromWorkflowNode?.id);

    // Find the calling agent - prefer the recorded parent from workflow node,
    // then try parentTaskId lookup, then fall back to current agent
    let callingAgent: LayoutNode | null = parentFromWorkflowNode || null;
    if (!callingAgent && step.parentTaskId) {
        callingAgent = context.taskToNodeMap.get(step.parentTaskId) || null;
        console.log("[handleWorkflowStart] callingAgent from parentTaskId lookup=", callingAgent?.data.label);
    }
    if (!callingAgent) {
        callingAgent = context.currentAgentNode;
        console.log("[handleWorkflowStart] callingAgent from currentAgentNode=", callingAgent?.data.label);
    }

    console.log("[handleWorkflowStart] Final callingAgent=", callingAgent?.data.label, callingAgent?.id);

    // Create group container
    const groupNode = createNode(
        context,
        "group",
        {
            label: displayName,
            visualizerStepId: step.id,
        },
        executionId || step.owningTaskId
    );

    // Create Start node inside group
    const startNode = createNode(
        context,
        "agent",
        {
            label: "Start",
            variant: "pill",
            visualizerStepId: step.id,
        },
        step.owningTaskId
    );

    groupNode.children.push(startNode);

    // Check if this workflow is part of a parallel group
    const functionCallId = step.functionCallId;
    let addedToParallelBlock = false;

    if (functionCallId) {
        // Search through all parallel groups to find if this functionCallId belongs to one
        for (const [groupKey, functionCallIds] of context.parallelPeerGroupMap.entries()) {
            if (functionCallIds.has(functionCallId)) {
                // This workflow is part of a parallel group
                const parallelBlock = context.parallelBlockMap.get(groupKey);
                if (parallelBlock) {
                    parallelBlock.children.push(groupNode);
                    addedToParallelBlock = true;
                }
                break;
            }
        }
    }

    // If not part of a parallel group, add to calling agent or root
    if (!addedToParallelBlock) {
        if (callingAgent) {
            callingAgent.children.push(groupNode);
        } else {
            context.rootNodes.push(groupNode);
        }
    }

    // Map execution ID to group for workflow nodes
    if (executionId) {
        context.taskToNodeMap.set(executionId, groupNode);
    }

    // Also map by owningTaskId so findAgentForStep can find the group
    // when workflow node steps use the event's task_id as their owningTaskId
    if (step.owningTaskId && step.owningTaskId !== executionId) {
        context.taskToNodeMap.set(step.owningTaskId, groupNode);
    }
}

/**
 * Handle WORKFLOW_NODE_EXECUTION_START
 */
function handleWorkflowNodeStart(step: VisualizerStep, context: BuildContext): void {
    const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
    const nodeId = step.data.workflowNodeExecutionStart?.nodeId || "unknown";
    const agentName = step.data.workflowNodeExecutionStart?.agentName;
    const parentNodeId = step.data.workflowNodeExecutionStart?.parentNodeId;
    const parallelGroupId = step.data.workflowNodeExecutionStart?.parallelGroupId;
    const taskId = step.owningTaskId;

    // Check if this node is a child of a Map/Loop (parallel execution with parentNodeId)
    // For Map/Loop children, use parallelGroupId if available, otherwise fall back to parentNodeId
    // NOTE: For implicit parallel agents (no parentNodeId), we don't look up in parallelContainerMap
    // because they find their container via parallelBlockMap using parallelGroupId directly.
    const isMapOrLoopChild = parentNodeId !== undefined && parentNodeId !== null;
    const parallelContainerKey = isMapOrLoopChild ? parallelGroupId || `${taskId}:${parentNodeId}` : null;
    const parallelContainer = parallelContainerKey ? context.parallelContainerMap.get(parallelContainerKey) : null;

    // Handle workflow nodes specially - they invoke sub-workflows and need group styling
    if (nodeType === "workflow") {
        handleWorkflowNodeType(step, context);
        return;
    }

    // Determine node type and variant
    let type: LayoutNode["type"] = "agent";
    const variant: "default" | "pill" = "default";
    let label: string;

    if (nodeType === "switch") {
        type = "switch";
        label = "Switch";
    } else if (nodeType === "loop") {
        type = "loop";
        label = "Loop";
    } else if (nodeType === "map") {
        type = "map";
        label = "Map";
    } else {
        // Agent nodes use their actual name
        label = agentName || nodeId;
    }

    const workflowNodeData = step.data.workflowNodeExecutionStart;
    const workflowNode = createNode(
        context,
        type,
        {
            label,
            variant,
            visualizerStepId: step.id,
            // Conditional node fields
            condition: workflowNodeData?.condition,
            trueBranch: workflowNodeData?.trueBranch,
            falseBranch: workflowNodeData?.falseBranch,
            // Switch node fields
            cases: workflowNodeData?.cases,
            defaultBranch: workflowNodeData?.defaultBranch,
            // Loop node fields
            maxIterations: workflowNodeData?.maxIterations,
            loopDelay: workflowNodeData?.loopDelay,
            // Store the original nodeId for reference when clicked
            nodeId,
        },
        step.owningTaskId
    );

    // For agent nodes within workflows, create a sub-task context
    if (nodeType === "agent") {
        const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
        if (subTaskId) {
            context.taskToNodeMap.set(subTaskId, workflowNode);
        }
    }

    // Handle Map nodes - these create parallel branches
    if (nodeType === "map") {
        // Find parent group
        const groupNode = findAgentForStep(step, context);
        if (!groupNode) return;

        // Store in parallel container map for child nodes to find
        // Use parallelGroupId from backend if available, otherwise use legacy key format
        const containerKey = parallelGroupId || `${taskId}:${nodeId}`;
        context.parallelContainerMap.set(containerKey, workflowNode);

        // Add to parent group
        groupNode.children.push(workflowNode);
    }
    // Handle Loop nodes - these contain sequential iterations
    else if (nodeType === "loop") {
        // Find parent group
        const groupNode = findAgentForStep(step, context);
        if (!groupNode) return;

        // Store in parallel container map so child nodes can find their parent
        // Loop children will be added sequentially to this node's children array
        const containerKey = `${taskId}:${nodeId}`;
        context.parallelContainerMap.set(containerKey, workflowNode);

        // Add to parent group
        groupNode.children.push(workflowNode);
    }
    // Handle nodes that are children of Map/Loop
    else if (parallelContainer) {
        // Check if parent is a loop (sequential children) or map (parallel branches)
        if (parallelContainer.type === "loop") {
            // Loop iterations are sequential - add as direct children
            parallelContainer.children.push(workflowNode);
        } else {
            // Map have parallel branches - store in children with iterationIndex metadata
            const iterationIndex = step.data.workflowNodeExecutionStart?.iterationIndex ?? 0;
            workflowNode.data.iterationIndex = iterationIndex;
            parallelContainer.children.push(workflowNode);
        }
    }
    // Handle implicit parallel agent nodes (from backend parallel_group_id)
    else if (nodeType === "agent" && parallelGroupId) {
        // Find parent group
        const groupNode = findAgentForStep(step, context);
        if (!groupNode) return;

        // Check if we already have a parallel block for this group
        let implicitParallelBlock = context.parallelBlockMap.get(parallelGroupId);
        if (!implicitParallelBlock) {
            // Create a new parallel block container for this implicit fork
            implicitParallelBlock = createNode(
                context,
                "parallelBlock",
                {
                    label: "Parallel",
                    visualizerStepId: step.id,
                },
                step.owningTaskId
            );
            context.parallelBlockMap.set(parallelGroupId, implicitParallelBlock);
            // NOTE: Do NOT store in parallelContainerMap - that's only for Map/Loop containers
            // where children have parentNodeId relationship. Implicit parallel agents find
            // their container via parallelBlockMap using parallelGroupId.
            groupNode.children.push(implicitParallelBlock);
        }

        // Add this agent node to the parallel block with its branch index
        const iterationIndex = step.data.workflowNodeExecutionStart?.iterationIndex ?? 0;
        workflowNode.data.iterationIndex = iterationIndex;
        implicitParallelBlock.children.push(workflowNode);
    }
    // Regular workflow node (not in parallel context)
    else {
        // Find parent group
        const groupNode = findAgentForStep(step, context);
        if (!groupNode) return;

        groupNode.children.push(workflowNode);
    }
}

/**
 * Handle workflow node type - records parent relationship for sub-workflow invocation
 * The actual group creation happens in handleWorkflowStart when the sub-workflow starts
 */
function handleWorkflowNodeType(step: VisualizerStep, context: BuildContext): void {
    const workflowNodeData = step.data.workflowNodeExecutionStart;
    const subTaskId = workflowNodeData?.subTaskId;

    console.log("[handleWorkflowNodeType] nodeType=workflow, subTaskId=", subTaskId, "owningTaskId=", step.owningTaskId);

    if (!subTaskId) {
        console.log("[handleWorkflowNodeType] No subTaskId, returning");
        return;
    }

    // Find the parent workflow group
    const parentGroup = findAgentForStep(step, context);
    console.log("[handleWorkflowNodeType] parentGroup=", parentGroup?.data.label, parentGroup?.id);
    if (!parentGroup) {
        console.log("[handleWorkflowNodeType] No parent group found, returning");
        return;
    }

    // Record the parent relationship so handleWorkflowStart can use it
    // This allows the sub-workflow's WORKFLOW_EXECUTION_START to find the correct parent
    context.subWorkflowParentMap.set(subTaskId, parentGroup);
    console.log("[handleWorkflowNodeType] Recorded mapping:", subTaskId, "->", parentGroup.data.label);
}

/**
 * Handle WORKFLOW_EXECUTION_RESULT - creates Finish node
 */
function handleWorkflowExecutionResult(step: VisualizerStep, context: BuildContext): void {
    // Find the workflow group node by owningTaskId (which should be the execution ID)
    const groupNode = findAgentForStep(step, context);
    if (!groupNode) return;

    // Get the execution result to determine status
    const resultData = step.data.workflowExecutionResult;
    // Backend may send 'error' or 'failure' for failures, 'success' for success
    const isError = resultData?.status === "error" || resultData?.status === "failure";
    const nodeStatus = isError ? "error" : "completed";

    // Create Finish node with status
    const finishNode = createNode(
        context,
        "agent",
        {
            label: "Finish",
            variant: "pill",
            visualizerStepId: step.id,
            status: nodeStatus,
        },
        step.owningTaskId
    );

    groupNode.children.push(finishNode);
}

/**
 * Handle WORKFLOW_NODE_EXECUTION_RESULT - cleanup, update node status, and add Join node
 */
function handleWorkflowNodeResult(step: VisualizerStep, context: BuildContext): void {
    const resultData = step.data.workflowNodeExecutionResult;
    const nodeId = resultData?.nodeId;
    const taskId = step.owningTaskId;

    if (!nodeId) return;

    const containerKey = `${taskId}:${nodeId}`;
    const parallelContainer = context.parallelContainerMap.get(containerKey);

    // Find the workflow node that matches this result and update its data
    const groupNode = findAgentForStep(step, context);
    if (groupNode) {
        const targetNode = findNodeById(groupNode, nodeId);
        if (targetNode) {
            // Update status
            targetNode.data.status = resultData?.status === "success" ? "completed" : resultData?.status === "failure" ? "error" : "completed";

            // Update switch node with selected branch
            if (targetNode.type === "switch") {
                const selectedBranch = resultData?.metadata?.selected_branch;
                const selectedCaseIndex = resultData?.metadata?.selected_case_index;
                if (selectedBranch !== undefined) {
                    targetNode.data.selectedBranch = selectedBranch;
                }
                if (selectedCaseIndex !== undefined) {
                    targetNode.data.selectedCaseIndex = selectedCaseIndex;
                }
            }
        }
    }

    // If this result is for a parallel container (Map/Fork/Loop), clean up tracking
    if (parallelContainer) {
        context.parallelContainerMap.delete(containerKey);
    }

    // For agent node results, mark any remaining in-progress LLM nodes as completed
    // This handles the case where the final LLM response doesn't emit a separate event
    const nodeType = resultData?.metadata?.node_type;
    if (nodeType === "agent" || !parallelContainer) {
        // Find the agent node for this workflow node by looking for it in the task map
        // The agent node was registered with its subTaskId
        for (const [subTaskId, agentNode] of context.taskToNodeMap.entries()) {
            // Check if this subTaskId matches the pattern for this nodeId
            if (subTaskId.includes(nodeId) || agentNode.data.nodeId === nodeId) {
                // Mark all in-progress LLM children as completed
                for (const child of agentNode.children) {
                    if (child.type === "llm" && child.data.status === "in-progress") {
                        child.data.status = "completed";
                    }
                }
                break;
            }
        }
    }
}

/**
 * Find a node by its nodeId within a tree
 */
function findNodeById(root: LayoutNode, nodeId: string): LayoutNode | null {
    // Check if this node matches
    if (root.data.nodeId === nodeId) {
        return root;
    }

    // Search children
    for (const child of root.children) {
        const found = findNodeById(child, nodeId);
        if (found) return found;
    }

    // Search parallel branches
    if (root.parallelBranches) {
        for (const branch of root.parallelBranches) {
            for (const branchNode of branch) {
                const found = findNodeById(branchNode, nodeId);
                if (found) return found;
            }
        }
    }

    return null;
}

/**
 * Find the appropriate agent node for a step
 */
function findAgentForStep(step: VisualizerStep, context: BuildContext): LayoutNode | null {
    // Try owningTaskId first
    if (step.owningTaskId) {
        const node = context.taskToNodeMap.get(step.owningTaskId);
        if (node) return node;
    }

    // Fallback to current agent
    return context.currentAgentNode;
}

/**
 * Create a new node
 */
function createNode(context: BuildContext, type: LayoutNode["type"], data: LayoutNode["data"], owningTaskId?: string): LayoutNode {
    const id = `${type}_${context.nodeCounter++}`;

    return {
        id,
        type,
        data,
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        children: [],
        owningTaskId,
    };
}

/**
 * Calculate layout (positions and dimensions) for all nodes
 */
function calculateLayout(rootNodes: LayoutNode[]): LayoutNode[] {
    // First pass: measure all nodes to find max width
    let maxWidth = 0;
    for (const node of rootNodes) {
        measureNode(node);
        maxWidth = Math.max(maxWidth, node.width);
    }

    // Calculate center X position based on max width
    const centerX = maxWidth / 2 + 100; // Add margin

    // Second pass: position nodes centered
    let currentY = 50; // Start with offset from top

    for (let i = 0; i < rootNodes.length; i++) {
        const node = rootNodes[i];
        const nextNode = rootNodes[i + 1];

        // Center each node horizontally
        node.x = centerX - node.width / 2;
        node.y = currentY;
        positionNode(node);

        // Use smaller spacing for User nodes (connector line spacing)
        // Use larger spacing between agents
        let spacing = SPACING.AGENT_VERTICAL;
        if (node.type === "user" || (nextNode && nextNode.type === "user")) {
            spacing = SPACING.VERTICAL;
        }

        currentY = node.y + node.height + spacing;
    }

    return rootNodes;
}

/**
 * Measure node dimensions (recursive, bottom-up)
 */
function measureNode(node: LayoutNode): void {
    // First, measure all children
    for (const child of node.children) {
        measureNode(child);
    }

    // Handle parallel branches
    if (node.parallelBranches) {
        for (const branch of node.parallelBranches) {
            for (const branchNode of branch) {
                measureNode(branchNode);
            }
        }
    }

    // Calculate this node's dimensions based on type
    switch (node.type) {
        case "agent":
            measureAgentNode(node);
            break;
        case "tool":
            node.width = NODE_WIDTHS.TOOL;
            node.height = NODE_HEIGHTS.TOOL;
            break;
        case "llm":
            node.width = NODE_WIDTHS.LLM;
            node.height = NODE_HEIGHTS.LLM;
            break;
        case "user":
            node.width = NODE_WIDTHS.USER;
            node.height = NODE_HEIGHTS.USER;
            break;
        case "switch":
            node.width = NODE_WIDTHS.SWITCH;
            node.height = NODE_HEIGHTS.SWITCH;
            break;
        case "loop":
            measureLoopNode(node);
            break;
        case "map":
            measureMapNode(node);
            break;
        case "group":
            measureGroupNode(node);
            break;
        case "parallelBlock":
            measureParallelBlockNode(node);
            break;
    }
}

/**
 * Measure agent node (container with children)
 */
function measureAgentNode(node: LayoutNode): void {
    let contentWidth = NODE_WIDTHS.MIN_AGENT_CONTENT;
    let contentHeight = 0;

    // If it's a pill variant (Start/Finish/Join), use smaller dimensions
    if (node.data.variant === "pill") {
        node.width = 100;
        node.height = 40;
        return;
    }

    // Measure sequential children
    if (node.children.length > 0) {
        for (const child of node.children) {
            contentWidth = Math.max(contentWidth, child.width);
            contentHeight += child.height + SPACING.VERTICAL;
        }
        // Remove last spacing
        contentHeight -= SPACING.VERTICAL;
    }

    // Measure parallel branches
    if (node.parallelBranches && node.parallelBranches.length > 0) {
        // Add spacing between children and parallel branches if both exist
        if (node.children.length > 0) {
            contentHeight += SPACING.VERTICAL;
        }

        let branchWidth = 0;
        let maxBranchHeight = 0;

        for (const branch of node.parallelBranches) {
            let branchHeight = 0;
            let branchMaxWidth = 0;

            for (const branchNode of branch) {
                branchHeight += branchNode.height + SPACING.VERTICAL;
                branchMaxWidth = Math.max(branchMaxWidth, branchNode.width);
            }

            // Remove last spacing from branch height
            if (branch.length > 0) {
                branchHeight -= SPACING.VERTICAL;
            }

            branchWidth += branchMaxWidth + SPACING.HORIZONTAL;
            maxBranchHeight = Math.max(maxBranchHeight, branchHeight);
        }

        // Remove last horizontal spacing
        if (node.parallelBranches.length > 0) {
            branchWidth -= SPACING.HORIZONTAL;
        }

        contentWidth = Math.max(contentWidth, branchWidth);
        contentHeight += maxBranchHeight;
    }

    // Add header height and padding
    node.width = contentWidth + SPACING.PADDING * 2;
    node.height = NODE_HEIGHTS.AGENT_HEADER + contentHeight + SPACING.PADDING;
}

/**
 * Measure loop node - can be a badge or a container with children
 */
function measureLoopNode(node: LayoutNode): void {
    // If no children, use badge dimensions
    if (node.children.length === 0) {
        node.width = NODE_WIDTHS.LOOP;
        node.height = NODE_HEIGHTS.LOOP;
        return;
    }

    // Has children - measure as a container
    let contentWidth = 200;
    let contentHeight = 0;

    // Account for iteration labels (about 16px per iteration for the label)
    const iterationLabelHeight = 16;

    for (const child of node.children) {
        contentWidth = Math.max(contentWidth, child.width);
        contentHeight += iterationLabelHeight + child.height + SPACING.VERTICAL;
    }

    if (node.children.length > 0) {
        contentHeight -= SPACING.VERTICAL;
    }

    // Loop uses p-4 pt-3 (16px padding, 12px top)
    const loopPadding = 16;
    const topLabelOffset = -4; // pt-3 is less than p-4, so negative offset
    node.width = contentWidth + loopPadding * 2;
    node.height = contentHeight + loopPadding + topLabelOffset + loopPadding;
}

/**
 * Measure map node - can be a badge or a container with parallel branches
 * Children are stored in node.children with iterationIndex in their data
 */
function measureMapNode(node: LayoutNode): void {
    // Group children by iterationIndex
    const branches = new Map<number, LayoutNode[]>();
    for (const child of node.children) {
        const iterationIndex = child.data.iterationIndex ?? 0;
        if (!branches.has(iterationIndex)) {
            branches.set(iterationIndex, []);
        }
        branches.get(iterationIndex)!.push(child);
    }

    // If no children, use badge dimensions
    if (branches.size === 0) {
        node.width = NODE_WIDTHS.MAP;
        node.height = NODE_HEIGHTS.MAP;
        return;
    }

    // Has children - measure as a container with side-by-side branches
    let totalWidth = 0;
    let maxBranchHeight = 0;

    // Account for iteration labels (about 20px per branch for the label)
    const iterationLabelHeight = 20;

    // Sort branches by iteration index for consistent ordering
    const sortedBranches = Array.from(branches.entries()).sort((a, b) => a[0] - b[0]);

    for (const [, branchChildren] of sortedBranches) {
        let branchWidth = 0;
        let branchHeight = iterationLabelHeight; // Start with label height

        for (const child of branchChildren) {
            branchWidth = Math.max(branchWidth, child.width);
            branchHeight += child.height + SPACING.VERTICAL;
        }

        // Remove last spacing from branch
        if (branchChildren.length > 0) {
            branchHeight -= SPACING.VERTICAL;
        }

        totalWidth += branchWidth + SPACING.HORIZONTAL;
        maxBranchHeight = Math.max(maxBranchHeight, branchHeight);
    }

    // Remove last horizontal spacing
    if (sortedBranches.length > 0) {
        totalWidth -= SPACING.HORIZONTAL;
    }

    // Map uses p-4 pt-3 (16px padding, 12px top)
    const containerPadding = 16;
    const topLabelOffset = -4; // pt-3 is less than p-4, so negative offset
    node.width = totalWidth + containerPadding * 2;
    node.height = maxBranchHeight + containerPadding + topLabelOffset + containerPadding;
}

/**
 * Measure group node
 */
function measureGroupNode(node: LayoutNode): void {
    let contentWidth = 200;
    let contentHeight = 0;

    for (const child of node.children) {
        contentWidth = Math.max(contentWidth, child.width);
        contentHeight += child.height + SPACING.VERTICAL;
    }

    if (node.children.length > 0) {
        contentHeight -= SPACING.VERTICAL;
    }

    // Group uses p-6 (24px) padding in WorkflowGroup
    const groupPadding = 24;
    node.width = contentWidth + groupPadding * 2;
    node.height = contentHeight + groupPadding * 2;
}

/**
 * Measure parallel block node - children are displayed side-by-side with bounding box
 * Children are grouped by iterationIndex (branch index) for proper chain visualization
 */
function measureParallelBlockNode(node: LayoutNode): void {
    // Group children by iterationIndex to form branch chains
    const branches = new Map<number, LayoutNode[]>();
    for (const child of node.children) {
        const branchIdx = child.data.iterationIndex ?? 0;
        if (!branches.has(branchIdx)) {
            branches.set(branchIdx, []);
        }
        branches.get(branchIdx)!.push(child);
    }

    // If only one branch or no iterationIndex grouping, fall back to side-by-side
    if (branches.size <= 1 && node.children.every(c => c.data.iterationIndex === undefined)) {
        let totalWidth = 0;
        let maxHeight = 0;

        for (const child of node.children) {
            totalWidth += child.width + SPACING.HORIZONTAL;
            maxHeight = Math.max(maxHeight, child.height);
        }

        if (node.children.length > 0) {
            totalWidth -= SPACING.HORIZONTAL;
        }

        const blockPadding = 16;
        node.width = totalWidth + blockPadding * 2;
        node.height = maxHeight + blockPadding * 2;
        return;
    }

    // Multiple branches - measure each branch (stacked vertically) and place side-by-side
    let totalWidth = 0;
    let maxBranchHeight = 0;

    const sortedBranches = Array.from(branches.entries()).sort((a, b) => a[0] - b[0]);
    for (const [, branchChildren] of sortedBranches) {
        let branchWidth = 0;
        let branchHeight = 0;

        for (const child of branchChildren) {
            branchWidth = Math.max(branchWidth, child.width);
            branchHeight += child.height + SPACING.VERTICAL;
        }

        if (branchChildren.length > 0) {
            branchHeight -= SPACING.VERTICAL;
        }

        totalWidth += branchWidth + SPACING.HORIZONTAL;
        maxBranchHeight = Math.max(maxBranchHeight, branchHeight);
    }

    if (sortedBranches.length > 0) {
        totalWidth -= SPACING.HORIZONTAL;
    }

    const blockPadding = 16;
    node.width = totalWidth + blockPadding * 2;
    node.height = maxBranchHeight + blockPadding * 2;
}

/**
 * Position children within node (recursive, top-down)
 */
function positionNode(node: LayoutNode): void {
    if (node.type === "agent" && node.data.variant !== "pill") {
        // Position children inside agent
        let currentY = node.y + NODE_HEIGHTS.AGENT_HEADER + SPACING.PADDING;
        const centerX = node.x + node.width / 2;

        for (const child of node.children) {
            child.x = centerX - child.width / 2; // Center horizontally
            child.y = currentY;
            positionNode(child); // Recursive
            currentY += child.height + SPACING.VERTICAL;
        }

        // Position parallel branches side-by-side
        if (node.parallelBranches) {
            let branchX = node.x + SPACING.PADDING;

            for (const branch of node.parallelBranches) {
                let branchMaxWidth = 0;
                let branchY = currentY;

                for (const branchNode of branch) {
                    branchNode.x = branchX;
                    branchNode.y = branchY;
                    positionNode(branchNode);
                    branchY += branchNode.height + SPACING.VERTICAL;
                    branchMaxWidth = Math.max(branchMaxWidth, branchNode.width);
                }

                branchX += branchMaxWidth + SPACING.HORIZONTAL;
            }
        }
    } else if (node.type === "group") {
        // Position children inside group
        let currentY = node.y + SPACING.PADDING + 30; // Offset for label
        const centerX = node.x + node.width / 2;

        for (const child of node.children) {
            child.x = centerX - child.width / 2;
            child.y = currentY;
            positionNode(child);
            currentY += child.height + SPACING.VERTICAL;
        }
    } else if (node.type === "parallelBlock") {
        // Group children by iterationIndex to form branch chains
        const branches = new Map<number, LayoutNode[]>();
        for (const child of node.children) {
            const branchIdx = child.data.iterationIndex ?? 0;
            if (!branches.has(branchIdx)) {
                branches.set(branchIdx, []);
            }
            branches.get(branchIdx)!.push(child);
        }

        const blockPadding = 16;

        // If only one branch or no iterationIndex grouping, position side-by-side
        if (branches.size <= 1 && node.children.every(c => c.data.iterationIndex === undefined)) {
            let currentX = node.x + blockPadding;
            for (const child of node.children) {
                child.x = currentX;
                child.y = node.y + blockPadding;
                positionNode(child);
                currentX += child.width + SPACING.HORIZONTAL;
            }
        } else {
            // Multiple branches - position each branch vertically, branches side-by-side
            const sortedBranches = Array.from(branches.entries()).sort((a, b) => a[0] - b[0]);
            let currentX = node.x + blockPadding;

            for (const [, branchChildren] of sortedBranches) {
                let currentY = node.y + blockPadding;
                let branchMaxWidth = 0;

                for (const child of branchChildren) {
                    child.x = currentX;
                    child.y = currentY;
                    positionNode(child);
                    currentY += child.height + SPACING.VERTICAL;
                    branchMaxWidth = Math.max(branchMaxWidth, child.width);
                }

                currentX += branchMaxWidth + SPACING.HORIZONTAL;
            }
        }
    } else if (node.type === "loop" && node.children.length > 0) {
        // Position children inside loop container
        const loopPadding = 16;
        const topLabelOffset = -4; // pt-3 is less than p-4
        const iterationLabelHeight = 16;
        let currentY = node.y + loopPadding + topLabelOffset;
        const centerX = node.x + node.width / 2;

        for (const child of node.children) {
            // Account for iteration label
            currentY += iterationLabelHeight;
            child.x = centerX - child.width / 2;
            child.y = currentY;
            positionNode(child);
            currentY += child.height + SPACING.VERTICAL;
        }
    } else if (node.type === "map" && node.children.length > 0) {
        // Group children by iterationIndex for positioning
        const branches = new Map<number, LayoutNode[]>();
        for (const child of node.children) {
            const iterationIndex = child.data.iterationIndex ?? 0;
            if (!branches.has(iterationIndex)) {
                branches.set(iterationIndex, []);
            }
            branches.get(iterationIndex)!.push(child);
        }

        // Position parallel branches side-by-side inside map container
        const containerPadding = 16;
        const topLabelOffset = -4; // pt-3 is less than p-4
        const iterationLabelHeight = 20;
        let currentX = node.x + containerPadding;
        const startY = node.y + containerPadding + topLabelOffset;

        // Sort branches by iteration index for consistent ordering
        const sortedBranches = Array.from(branches.entries()).sort((a, b) => a[0] - b[0]);

        for (const [, branchChildren] of sortedBranches) {
            let branchMaxWidth = 0;
            let currentY = startY + iterationLabelHeight; // Start below iteration label

            for (const child of branchChildren) {
                child.x = currentX;
                child.y = currentY;
                positionNode(child);
                currentY += child.height + SPACING.VERTICAL;
                branchMaxWidth = Math.max(branchMaxWidth, child.width);
            }

            currentX += branchMaxWidth + SPACING.HORIZONTAL;
        }
    }
}

/**
 * Calculate edges between nodes
 */
function calculateEdges(nodes: LayoutNode[]): Edge[] {
    const edges: Edge[] = [];
    const flatNodes = flattenNodes(nodes);

    // Create edges between sequential top-level nodes
    for (let i = 0; i < flatNodes.length - 1; i++) {
        const source = flatNodes[i];
        const target = flatNodes[i + 1];

        // Only connect nodes at the same level (not nested)
        if (shouldConnectNodes(source, target)) {
            edges.push({
                id: `edge_${source.id}_${target.id}`,
                source: source.id,
                target: target.id,
                sourceX: source.x + source.width / 2,
                sourceY: source.y + source.height,
                targetX: target.x + target.width / 2,
                targetY: target.y,
            });
        }
    }

    return edges;
}

/**
 * Flatten node tree into array
 */
function flattenNodes(nodes: LayoutNode[]): LayoutNode[] {
    const result: LayoutNode[] = [];

    function traverse(node: LayoutNode) {
        result.push(node);
        for (const child of node.children) {
            traverse(child);
        }
        if (node.parallelBranches) {
            for (const branch of node.parallelBranches) {
                for (const branchNode of branch) {
                    traverse(branchNode);
                }
            }
        }
    }

    for (const node of nodes) {
        traverse(node);
    }

    return result;
}

/**
 * Determine if two nodes should be connected
 */
function shouldConnectNodes(source: LayoutNode, target: LayoutNode): boolean {
    // Connect User → Agent
    if (source.type === "user" && source.data.isTopNode && target.type === "agent") {
        return true;
    }

    // Connect Agent → User (bottom)
    if (source.type === "agent" && target.type === "user" && target.data.isBottomNode) {
        return true;
    }

    // Connect Agent → Agent (for delegation returns)
    if (source.type === "agent" && target.type === "agent") {
        return true;
    }

    return false;
}

/**
 * Calculate total canvas size
 */
function calculateCanvasSize(nodes: LayoutNode[]): { totalWidth: number; totalHeight: number } {
    let maxX = 0;
    let maxY = 0;

    const flatNodes = flattenNodes(nodes);

    for (const node of flatNodes) {
        maxX = Math.max(maxX, node.x + node.width);
        maxY = Math.max(maxY, node.y + node.height);
    }

    return {
        totalWidth: maxX + 100, // Add margin
        totalHeight: maxY + 100,
    };
}
