import type { VisualizerStep } from "@/lib/types";
import type { LayoutNode, Edge, BuildContext, LayoutResult } from "./types";

// Layout constants
const NODE_WIDTHS = {
    AGENT: 220,
    TOOL: 180,
    LLM: 180,
    USER: 140,
    CONDITIONAL: 120,
    MIN_AGENT_CONTENT: 200,
};

const NODE_HEIGHTS = {
    AGENT_HEADER: 50,
    TOOL: 50,
    LLM: 50,
    USER: 50,
    CONDITIONAL: 80,
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
    };

    // Process all steps to build tree structure
    for (let i = 0; i < steps.length; i++) {
        context.stepIndex = i;
        const step = steps[i];
        processStep(step, context);
    }

    // Calculate layout (positions and dimensions)
    const nodes = calculateLayout(context.rootNodes);

    // Calculate edges between top-level nodes
    const edges = calculateEdges(nodes, steps);

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
        // Add other cases as needed
    }
}

/**
 * Handle USER_REQUEST step - creates User node + Agent node
 */
function handleUserRequest(step: VisualizerStep, context: BuildContext): void {
    // Create User node (top)
    const userNode = createNode(
        context,
        'user',
        {
            label: 'User',
            visualizerStepId: step.id,
            isTopNode: true,
        },
        step.owningTaskId
    );

    // Create Agent node
    const agentName = step.target || 'Agent';
    const displayName = context.agentNameMap[agentName] || agentName;

    const agentNode = createNode(
        context,
        'agent',
        {
            label: displayName,
            visualizerStepId: step.id,
        },
        step.owningTaskId
    );

    // Add to root nodes
    context.rootNodes.push(userNode);
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
        'llm',
        {
            label: 'LLM',
            visualizerStepId: step.id,
            status: 'in-progress',
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
 * Handle AGENT_TOOL_INVOCATION_START
 */
function handleToolInvocation(step: VisualizerStep, context: BuildContext): void {
    const isPeer = step.data.toolInvocationStart?.isPeerInvocation || step.target?.startsWith('peer_');
    const target = step.target || '';
    const toolName = step.data.toolInvocationStart?.toolName || target;

    // Skip workflow tools (handled separately)
    if (target.includes('workflow_') || toolName.includes('workflow_')) {
        return;
    }

    const agentNode = findAgentForStep(step, context);
    if (!agentNode) return;

    if (isPeer) {
        // Create nested agent node
        const peerName = target.startsWith('peer_') ? target.substring(5) : target;
        const displayName = context.agentNameMap[peerName] || peerName;

        const subAgentNode = createNode(
            context,
            'agent',
            {
                label: displayName,
                visualizerStepId: step.id,
            },
            step.delegationInfo?.[0]?.subTaskId || step.owningTaskId
        );

        // Add as child (recursive nesting!)
        agentNode.children.push(subAgentNode);

        // Map sub-task to this new agent
        const subTaskId = step.delegationInfo?.[0]?.subTaskId;
        if (subTaskId) {
            context.taskToNodeMap.set(subTaskId, subAgentNode);
        }

        // Track by functionCallId
        if (step.functionCallId) {
            context.functionCallToNodeMap.set(step.functionCallId, subAgentNode);
        }
    } else {
        // Regular tool
        const toolNode = createNode(
            context,
            'tool',
            {
                label: toolName,
                visualizerStepId: step.id,
                status: 'in-progress',
            },
            step.owningTaskId
        );

        agentNode.children.push(toolNode);

        if (step.functionCallId) {
            context.functionCallToNodeMap.set(step.functionCallId, toolNode);
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
        node.data.status = 'completed';
    }
}

/**
 * Handle AGENT_RESPONSE_TEXT - create bottom User node
 */
function handleAgentResponse(step: VisualizerStep, context: BuildContext): void {
    // Only for top-level tasks
    if (step.nestingLevel && step.nestingLevel > 0) return;

    const userNode = createNode(
        context,
        'user',
        {
            label: 'User',
            visualizerStepId: step.id,
            isBottomNode: true,
        },
        step.owningTaskId
    );

    context.rootNodes.push(userNode);
}

/**
 * Handle WORKFLOW_EXECUTION_START
 */
function handleWorkflowStart(step: VisualizerStep, context: BuildContext): void {
    const workflowName = step.data.workflowExecutionStart?.workflowName || 'Workflow';
    const displayName = context.agentNameMap[workflowName] || workflowName;

    // Find the calling agent (should be from parentTaskId)
    const callingAgent = step.parentTaskId
        ? context.taskToNodeMap.get(step.parentTaskId)
        : context.currentAgentNode;

    // Create group container
    const groupNode = createNode(
        context,
        'group',
        {
            label: displayName,
            visualizerStepId: step.id,
        },
        step.data.workflowExecutionStart?.executionId || step.owningTaskId
    );

    // Create Start node inside group
    const startNode = createNode(
        context,
        'agent',
        {
            label: 'Start',
            variant: 'pill',
            visualizerStepId: step.id,
        },
        step.owningTaskId
    );

    groupNode.children.push(startNode);

    // Add workflow to calling agent if available, otherwise to root
    if (callingAgent) {
        callingAgent.children.push(groupNode);
    } else {
        context.rootNodes.push(groupNode);
    }

    // Map execution ID to group for workflow nodes
    const executionId = step.data.workflowExecutionStart?.executionId;
    if (executionId) {
        context.taskToNodeMap.set(executionId, groupNode);
    }
}

/**
 * Handle WORKFLOW_NODE_EXECUTION_START
 */
function handleWorkflowNodeStart(step: VisualizerStep, context: BuildContext): void {
    const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
    const nodeId = step.data.workflowNodeExecutionStart?.nodeId || 'unknown';
    const agentName = step.data.workflowNodeExecutionStart?.agentName;

    // Find parent group
    const groupNode = findAgentForStep(step, context);
    if (!groupNode) return;

    // Determine node type and variant
    let type: LayoutNode['type'] = 'agent';
    let variant: 'default' | 'pill' = 'default';
    let label: string;

    if (nodeType === 'conditional') {
        type = 'conditional';
        label = 'Conditional';
    } else if (nodeType === 'map') {
        variant = 'pill';
        label = 'Map';
    } else if (nodeType === 'fork') {
        variant = 'pill';
        label = 'Fork';
    } else {
        // Agent nodes use their actual name
        label = agentName || nodeId;
    }

    const workflowNode = createNode(
        context,
        type,
        {
            label,
            variant,
            visualizerStepId: step.id,
            condition: step.data.workflowNodeExecutionStart?.condition,
            trueBranch: step.data.workflowNodeExecutionStart?.trueBranch,
            falseBranch: step.data.workflowNodeExecutionStart?.falseBranch,
            // Store the original nodeId for reference when clicked
            nodeId,
        },
        step.owningTaskId
    );

    // For agent nodes within workflows, create a sub-task context
    if (nodeType === 'agent') {
        const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
        if (subTaskId) {
            context.taskToNodeMap.set(subTaskId, workflowNode);
        }
    }

    groupNode.children.push(workflowNode);
}

/**
 * Handle WORKFLOW_EXECUTION_RESULT - creates Finish node
 */
function handleWorkflowExecutionResult(step: VisualizerStep, context: BuildContext): void {
    // Find the workflow group node by owningTaskId (which should be the execution ID)
    const groupNode = findAgentForStep(step, context);
    if (!groupNode) return;

    // Create Finish node
    const finishNode = createNode(
        context,
        'agent',
        {
            label: 'Finish',
            variant: 'pill',
            visualizerStepId: step.id,
        },
        step.owningTaskId
    );

    groupNode.children.push(finishNode);
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
function createNode(
    context: BuildContext,
    type: LayoutNode['type'],
    data: LayoutNode['data'],
    owningTaskId?: string
): LayoutNode {
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

    for (const node of rootNodes) {
        // Center each node horizontally
        node.x = centerX - node.width / 2;
        node.y = currentY;
        positionNode(node);

        currentY = node.y + node.height + SPACING.AGENT_VERTICAL;
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
        case 'agent':
            measureAgentNode(node);
            break;
        case 'tool':
            node.width = NODE_WIDTHS.TOOL;
            node.height = NODE_HEIGHTS.TOOL;
            break;
        case 'llm':
            node.width = NODE_WIDTHS.LLM;
            node.height = NODE_HEIGHTS.LLM;
            break;
        case 'user':
            node.width = NODE_WIDTHS.USER;
            node.height = NODE_HEIGHTS.USER;
            break;
        case 'conditional':
            node.width = NODE_WIDTHS.CONDITIONAL;
            node.height = NODE_HEIGHTS.CONDITIONAL;
            break;
        case 'group':
            measureGroupNode(node);
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
    if (node.data.variant === 'pill') {
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
        let branchWidth = 0;
        let maxBranchHeight = 0;

        for (const branch of node.parallelBranches) {
            let branchHeight = 0;
            let branchMaxWidth = 0;

            for (const branchNode of branch) {
                branchHeight += branchNode.height + SPACING.VERTICAL;
                branchMaxWidth = Math.max(branchMaxWidth, branchNode.width);
            }

            branchWidth += branchMaxWidth + SPACING.HORIZONTAL;
            maxBranchHeight = Math.max(maxBranchHeight, branchHeight);
        }

        contentWidth = Math.max(contentWidth, branchWidth);
        contentHeight += maxBranchHeight;
    }

    // Add header height and padding
    node.width = contentWidth + (SPACING.PADDING * 2);
    node.height = NODE_HEIGHTS.AGENT_HEADER + contentHeight + SPACING.PADDING;
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

    // Group uses p-6 (24px) padding in WorkflowGroupV2
    const groupPadding = 24;
    node.width = contentWidth + (groupPadding * 2);
    node.height = contentHeight + (groupPadding * 2);
}

/**
 * Position children within node (recursive, top-down)
 */
function positionNode(node: LayoutNode): void {
    if (node.type === 'agent' && node.data.variant !== 'pill') {
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
    } else if (node.type === 'group') {
        // Position children inside group
        let currentY = node.y + SPACING.PADDING + 30; // Offset for label
        const centerX = node.x + node.width / 2;

        for (const child of node.children) {
            child.x = centerX - child.width / 2;
            child.y = currentY;
            positionNode(child);
            currentY += child.height + SPACING.VERTICAL;
        }
    }
}

/**
 * Calculate edges between nodes
 */
function calculateEdges(nodes: LayoutNode[], _steps: VisualizerStep[]): Edge[] {
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
    if (source.type === 'user' && source.data.isTopNode && target.type === 'agent') {
        return true;
    }

    // Connect Agent → User (bottom)
    if (source.type === 'agent' && target.type === 'user' && target.data.isBottomNode) {
        return true;
    }

    // Connect Agent → Agent (for delegation returns)
    if (source.type === 'agent' && target.type === 'agent') {
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
