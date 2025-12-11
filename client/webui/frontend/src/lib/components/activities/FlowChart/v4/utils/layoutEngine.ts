import type { VisualizerStep } from "@/lib/types";
import type {
    ContainerNode,
    Stop,
    LaneState,
    BuildContext,
    LayoutResult,
} from "./types";
import { TRACK_COLORS } from "./types";

const SPACING = {
    AGENT_MIN_WIDTH: 180,
    AGENT_HEADER_HEIGHT: 50,
    AGENT_PADDING: 20,
    WORKFLOW_MIN_WIDTH: 200,
    WORKFLOW_PADDING: 30,
    STOP_HEIGHT: 40,
    STOP_MIN_WIDTH: 120,
    STOP_SPACING: 12,
    STOP_CIRCLE_RADIUS: 8,
    LANE_WIDTH: 60,
    LEFT_MARGIN: 100,
    TRACK_WIDTH: 3,
    CONTAINER_VERTICAL_SPACING: 40,
    CONTAINER_HORIZONTAL_SPACING: 40,
    PARALLEL_BRANCH_GAP: 30,
};

/**
 * Main entry point: Process VisualizerSteps into V4 hybrid layout
 */
export function processSteps(
    steps: VisualizerStep[],
    agentNameMap: Record<string, string> = {}
): LayoutResult {
    const context: BuildContext = {
        containers: [],
        allStops: [],
        tracks: [],
        branches: [],
        lanes: [createLane(0, TRACK_COLORS.DEFAULT)],
        nextY: 50,
        taskToContainerMap: new Map(),
        taskToLaneMap: new Map(),
        stopIdMap: new Map(),
        containerIdMap: new Map(),
        currentContainer: undefined,
        currentLane: 0,
        steps,
        stepIndex: 0,
        stopCounter: 0,
        containerCounter: 0,
        agentNameMap,
        workflowColors: new Map(),
        defaultTrackColor: TRACK_COLORS.DEFAULT,
    };

    // Process all steps
    for (let i = 0; i < steps.length; i++) {
        context.stepIndex = i;
        const step = steps[i];
        processStep(step, context);
    }

    // Calculate layout dimensions and positions
    const layoutResult = calculateLayout(context);

    return layoutResult;
}

/**
 * Create a new lane
 */
function createLane(index: number, color: string): LaneState {
    return {
        index,
        isActive: false,
        trackColor: color,
    };
}

/**
 * Get or allocate a lane for a task
 */
function getLaneForTask(taskId: string, context: BuildContext, color?: string): number {
    const existingLane = context.taskToLaneMap.get(taskId);
    if (existingLane !== undefined) {
        return existingLane;
    }

    let lane = context.lanes.findIndex(l => !l.isActive);

    if (lane === -1) {
        lane = context.lanes.length;
        context.lanes.push(createLane(lane, color || TRACK_COLORS.DEFAULT));
    }

    context.lanes[lane].isActive = true;
    context.lanes[lane].currentTaskId = taskId;
    if (color) {
        context.lanes[lane].trackColor = color;
    }

    context.taskToLaneMap.set(taskId, lane);
    return lane;
}

/**
 * Release a lane (make it available for reuse)
 */
function releaseLane(taskId: string, context: BuildContext): void {
    const lane = context.taskToLaneMap.get(taskId);
    if (lane !== undefined && context.lanes[lane]) {
        context.lanes[lane].isActive = false;
        context.lanes[lane].currentTaskId = undefined;
    }
}

/**
 * Create a stop (tool, LLM, or standalone agent)
 */
function createStop(
    type: Stop['type'],
    label: string,
    laneIndex: number,
    step: VisualizerStep,
    context: BuildContext,
    additionalData?: Partial<Stop>
): Stop {
    const stop: Stop = {
        id: `stop_${context.stopCounter++}`,
        type,
        label,
        y: 0, // Will be calculated during layout
        laneIndex,
        visualizerStepId: step.id,
        trackColor: context.lanes[laneIndex]?.trackColor || TRACK_COLORS.DEFAULT,
        ...additionalData,
    };

    context.allStops.push(stop);
    context.stopIdMap.set(stop.id, stop);

    // Update lane's current stop
    if (context.lanes[laneIndex]) {
        context.lanes[laneIndex].currentStopId = stop.id;
    }

    return stop;
}

/**
 * Create a container node (agent or workflow group)
 */
function createContainer(
    type: ContainerNode['type'],
    label: string,
    laneIndex: number,
    step: VisualizerStep,
    context: BuildContext,
    additionalData?: Partial<ContainerNode>
): ContainerNode {
    const container: ContainerNode = {
        id: `container_${context.containerCounter++}`,
        type,
        label,
        visualizerStepId: step.id,
        stops: [],
        children: [],
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        laneIndex,
        trackColor: context.lanes[laneIndex]?.trackColor || TRACK_COLORS.DEFAULT,
        ...additionalData,
    };

    context.containerIdMap.set(container.id, container);

    return container;
}

/**
 * Create a track segment
 */
function createTrack(
    fromStopId: string,
    toStopId: string,
    fromY: number,
    toY: number,
    fromLane: number,
    toLane: number,
    color: string,
    context: BuildContext,
    style: 'solid' | 'dashed' = 'solid',
    stepId?: string
): void {
    context.tracks.push({
        id: `track_${fromStopId}_${toStopId}`,
        fromStopId,
        toStopId,
        fromY,
        toY,
        fromLane,
        toLane,
        color,
        style,
        visualizerStepId: stepId,
    });
}

/**
 * Process a single step
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
            handleWorkflowEnd(step, context);
            break;
        case "TASK_COMPLETED":
            handleTaskCompleted(step, context);
            break;
    }
}

/**
 * Handle USER_REQUEST - creates User stop + Agent container
 */
function handleUserRequest(step: VisualizerStep, context: BuildContext): void {
    const taskId = step.owningTaskId;
    const lane = getLaneForTask(taskId, context);

    // Create User stop
    createStop('user', 'User', lane, step, context);

    // Create Agent container
    const agentName = step.target || 'Agent';
    const displayName = context.agentNameMap[agentName] || agentName;
    const agentContainer = createContainer('agent', displayName, lane, step, context);

    // Add to root containers
    context.containers.push(agentContainer);

    // Track task -> container mapping
    context.taskToContainerMap.set(taskId, agentContainer);
    context.currentContainer = agentContainer;
}

/**
 * Handle AGENT_LLM_CALL - creates LLM stop inside current agent
 */
function handleLLMCall(step: VisualizerStep, context: BuildContext): void {
    const taskId = step.owningTaskId;
    const container = context.taskToContainerMap.get(taskId);

    if (!container) return;

    const lane = context.taskToLaneMap.get(taskId) ?? 0;

    // Create LLM stop and add to container
    const llmStop = createStop('llm', 'LLM', lane, step, context, {
        status: 'in-progress',
    });

    container.stops.push(llmStop);
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

    const parentTaskId = step.owningTaskId;
    const parentContainer = context.taskToContainerMap.get(parentTaskId);
    const parentLane = context.taskToLaneMap.get(parentTaskId) ?? 0;

    if (!parentContainer) return;

    if (isPeer) {
        // Sub-agent - create nested container
        const peerName = target.startsWith('peer_') ? target.substring(5) : target;
        const displayName = context.agentNameMap[peerName] || peerName;
        const subTaskId = step.delegationInfo?.[0]?.subTaskId || step.owningTaskId;

        // Get lane for sub-agent (may branch to new lane)
        const subLane = getLaneForTask(subTaskId, context, context.lanes[parentLane].trackColor);

        // Create sub-agent container
        const subAgentContainer = createContainer('agent', displayName, subLane, step, context);

        // Add to parent's children
        parentContainer.children.push(subAgentContainer);

        // Track task -> container mapping
        context.taskToContainerMap.set(subTaskId, subAgentContainer);

        // Create branch point if lane changed
        if (subLane !== parentLane) {
            // Will be created during layout phase
        }
    } else {
        // Regular tool - add as stop inside parent container
        const toolStop = createStop('tool', toolName, parentLane, step, context, {
            status: 'in-progress',
        });

        parentContainer.stops.push(toolStop);
    }
}

/**
 * Handle AGENT_TOOL_EXECUTION_RESULT - merge back if peer
 */
function handleToolResult(step: VisualizerStep, context: BuildContext): void {
    const isPeer = step.data.toolResult?.isPeerResponse;

    if (isPeer) {
        const subTaskId = step.owningTaskId;
        const subLane = context.taskToLaneMap.get(subTaskId);
        const parentTaskId = step.parentTaskId;
        const parentLane = parentTaskId ? context.taskToLaneMap.get(parentTaskId) : undefined;

        if (subLane !== undefined && parentLane !== undefined && subLane !== parentLane) {
            // Create join point (will be handled during layout)
            // Release the sub-lane
            releaseLane(subTaskId, context);
        }
    }
}

/**
 * Handle AGENT_RESPONSE_TEXT
 */
function handleAgentResponse(step: VisualizerStep, context: BuildContext): void {
    // Only for top-level responses
    if (step.nestingLevel && step.nestingLevel > 0) return;

    const taskId = step.owningTaskId;
    const lane = context.taskToLaneMap.get(taskId) ?? 0;

    // Create User stop for response
    createStop('user', 'User', lane, step, context);

    // Release the lane
    releaseLane(taskId, context);
}

/**
 * Handle WORKFLOW_EXECUTION_START - create workflow group container
 */
function handleWorkflowStart(step: VisualizerStep, context: BuildContext): void {
    const workflowName = step.data.workflowExecutionStart?.workflowName || 'Workflow';
    const displayName = context.agentNameMap[workflowName] || workflowName;
    const executionId = step.data.workflowExecutionStart?.executionId || step.owningTaskId;

    // Get a unique color for this workflow
    const workflowColor = getWorkflowColor(executionId, context);

    // Find parent task
    const parentTaskId = step.parentTaskId || step.owningTaskId;
    const parentContainer = context.taskToContainerMap.get(parentTaskId);

    // Allocate lane for workflow
    const workflowLane = getLaneForTask(executionId, context, workflowColor);

    // Create workflow group container
    const workflowGroup = createContainer('workflow-group', `${displayName}`, workflowLane, step, context, {
        isWorkflow: true,
        workflowName,
        trackColor: workflowColor,
    });

    // Add to parent container if it exists, otherwise to root
    if (parentContainer) {
        parentContainer.children.push(workflowGroup);
    } else {
        context.containers.push(workflowGroup);
    }

    // Track workflow container
    context.taskToContainerMap.set(executionId, workflowGroup);
    context.currentContainer = workflowGroup;
}

/**
 * Handle WORKFLOW_NODE_EXECUTION_START
 */
function handleWorkflowNodeStart(step: VisualizerStep, context: BuildContext): void {
    const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
    const nodeId = step.data.workflowNodeExecutionStart?.nodeId || 'unknown';
    const agentName = step.data.workflowNodeExecutionStart?.agentName;
    const label = agentName || nodeId;

    const executionId = step.owningTaskId;
    const workflowContainer = context.taskToContainerMap.get(executionId);
    const lane = context.taskToLaneMap.get(executionId) ?? context.currentLane;

    if (!workflowContainer) return;

    // For agent nodes, create a nested agent container inside the workflow
    if (nodeType === 'agent') {
        const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;

        const agentContainer = createContainer('agent', label, lane, step, context);
        workflowContainer.children.push(agentContainer);

        if (subTaskId) {
            context.taskToContainerMap.set(subTaskId, agentContainer);
        }
    } else if (nodeType === 'conditional') {
        // Create conditional stop inside workflow
        const conditionalStop = createStop('conditional', label, lane, step, context, {
            condition: step.data.workflowNodeExecutionStart?.condition,
        });

        workflowContainer.stops.push(conditionalStop);
    } else {
        // Other node types - create as stops
        const nodeStop = createStop('agent', label, lane, step, context);
        workflowContainer.stops.push(nodeStop);
    }
}

/**
 * Handle WORKFLOW_EXECUTION_RESULT - close workflow container
 */
function handleWorkflowEnd(step: VisualizerStep, context: BuildContext): void {
    const executionId = step.owningTaskId;
    releaseLane(executionId, context);
}

/**
 * Handle TASK_COMPLETED
 */
function handleTaskCompleted(step: VisualizerStep, context: BuildContext): void {
    const taskId = step.owningTaskId;
    releaseLane(taskId, context);
}

/**
 * Get workflow color (cycle through available colors)
 */
function getWorkflowColor(executionId: string, context: BuildContext): string {
    if (context.workflowColors.has(executionId)) {
        return context.workflowColors.get(executionId)!;
    }

    const colors = [
        TRACK_COLORS.WORKFLOW_1,
        TRACK_COLORS.WORKFLOW_2,
        TRACK_COLORS.WORKFLOW_3,
        TRACK_COLORS.WORKFLOW_4,
    ];

    const colorIndex = context.workflowColors.size % colors.length;
    const color = colors[colorIndex];

    context.workflowColors.set(executionId, color);
    return color;
}

/**
 * Calculate layout - measure and position all containers and stops
 */
function calculateLayout(context: BuildContext): LayoutResult {
    // First pass: measure all containers (bottom-up)
    for (const container of context.containers) {
        measureContainer(container);
    }

    // Second pass: position containers (top-down)
    let currentY = 50;
    const maxWidth = Math.max(
        ...context.containers.map(c => c.width),
        SPACING.AGENT_MIN_WIDTH
    );

    for (const container of context.containers) {
        // Center horizontally
        container.x = (maxWidth - container.width) / 2 + SPACING.LEFT_MARGIN;
        container.y = currentY;
        positionContainer(container);
        currentY += container.height + SPACING.CONTAINER_VERTICAL_SPACING;
    }

    // Third pass: create tracks between stops
    generateTracks(context);

    const totalWidth = maxWidth + SPACING.LEFT_MARGIN + context.lanes.length * SPACING.LANE_WIDTH + 200;
    const totalHeight = currentY + 100;

    return {
        containers: context.containers,
        stops: context.allStops,
        tracks: context.tracks,
        branches: context.branches,
        totalLanes: context.lanes.length,
        totalWidth,
        totalHeight,
    };
}

/**
 * Measure a container (calculate width and height)
 */
function measureContainer(container: ContainerNode): void {
    let contentWidth = SPACING.AGENT_MIN_WIDTH;
    let contentHeight = SPACING.AGENT_HEADER_HEIGHT;

    // Measure stops
    if (container.stops.length > 0) {
        contentWidth = Math.max(contentWidth, SPACING.STOP_MIN_WIDTH + SPACING.AGENT_PADDING * 2);
        contentHeight += container.stops.length * (SPACING.STOP_HEIGHT + SPACING.STOP_SPACING) + SPACING.AGENT_PADDING;
    }

    // Measure children recursively
    for (const child of container.children) {
        measureContainer(child);
        contentWidth = Math.max(contentWidth, child.width + SPACING.AGENT_PADDING * 2);
        contentHeight += child.height + SPACING.STOP_SPACING;
    }

    // Measure parallel branches
    if (container.parallelBranches) {
        let maxBranchHeight = 0;
        let totalBranchWidth = 0;

        for (const branch of container.parallelBranches) {
            let branchWidth = 0;
            let branchHeight = 0;

            for (const node of branch) {
                measureContainer(node);
                branchWidth = Math.max(branchWidth, node.width);
                branchHeight += node.height + SPACING.STOP_SPACING;
            }

            totalBranchWidth += branchWidth + SPACING.PARALLEL_BRANCH_GAP;
            maxBranchHeight = Math.max(maxBranchHeight, branchHeight);
        }

        contentWidth = Math.max(contentWidth, totalBranchWidth + SPACING.AGENT_PADDING * 2);
        contentHeight += maxBranchHeight + SPACING.AGENT_PADDING;
    }

    container.width = contentWidth;
    container.height = contentHeight + SPACING.AGENT_PADDING;

    // Adjust for workflow groups
    if (container.type === 'workflow-group') {
        container.width = Math.max(container.width, SPACING.WORKFLOW_MIN_WIDTH);
        container.height += SPACING.WORKFLOW_PADDING;
    }
}

/**
 * Position stops and child containers within a container
 */
function positionContainer(container: ContainerNode): void {
    let currentY = container.y + SPACING.AGENT_HEADER_HEIGHT + SPACING.AGENT_PADDING;

    // Position stops
    for (const stop of container.stops) {
        stop.y = currentY + SPACING.STOP_HEIGHT / 2; // Center of stop
        currentY += SPACING.STOP_HEIGHT + SPACING.STOP_SPACING;
    }

    // Position children
    for (const child of container.children) {
        child.x = container.x + (container.width - child.width) / 2; // Center horizontally
        child.y = currentY;
        positionContainer(child);
        currentY += child.height + SPACING.STOP_SPACING;
    }

    // Position parallel branches
    if (container.parallelBranches) {
        let currentX = container.x + SPACING.AGENT_PADDING;

        for (const branch of container.parallelBranches) {
            let branchY = currentY;
            let maxBranchWidth = 0;

            for (const node of branch) {
                node.x = currentX;
                node.y = branchY;
                positionContainer(node);
                branchY += node.height + SPACING.STOP_SPACING;
                maxBranchWidth = Math.max(maxBranchWidth, node.width);
            }

            currentX += maxBranchWidth + SPACING.PARALLEL_BRANCH_GAP;
        }
    }
}

/**
 * Generate track segments connecting all stops
 */
function generateTracks(context: BuildContext): void {
    // Connect stops in sequence within each lane
    const stopsByLane = new Map<number, Stop[]>();

    // Group stops by lane
    for (const stop of context.allStops) {
        if (!stopsByLane.has(stop.laneIndex)) {
            stopsByLane.set(stop.laneIndex, []);
        }
        stopsByLane.get(stop.laneIndex)!.push(stop);
    }

    // Sort stops by Y position within each lane and create tracks
    for (const [lane, stops] of stopsByLane) {
        const sortedStops = stops.sort((a, b) => a.y - b.y);

        for (let i = 0; i < sortedStops.length - 1; i++) {
            const fromStop = sortedStops[i];
            const toStop = sortedStops[i + 1];

            createTrack(
                fromStop.id,
                toStop.id,
                fromStop.y,
                toStop.y,
                lane,
                lane,
                fromStop.trackColor,
                context,
                'solid',
                toStop.visualizerStepId
            );
        }
    }
}
