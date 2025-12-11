import type { VisualizerStep } from "@/lib/types";
import type {
    SubwayStop,
    TrackSegment,
    BranchPoint,
    SubwayBuildContext,
    SubwayGraphResult,
    LaneState,
    SUBWAY_LAYOUT,
} from "./types";

const SUBWAY_LAYOUT_CONST = {
    LANE_WIDTH: 40,
    STOP_HEIGHT: 60,
    STOP_SPACING: 20,
    LABEL_AREA_WIDTH: 200,
    LEFT_MARGIN: 50,
    STOP_CIRCLE_RADIUS: 8,
};

const TRACK_COLORS = {
    DEFAULT: '#3b82f6',
    WORKFLOW_1: '#8b5cf6',
    WORKFLOW_2: '#ec4899',
    WORKFLOW_3: '#10b981',
    WORKFLOW_4: '#f59e0b',
    ERROR: '#ef4444',
};

/**
 * Main entry point: Process VisualizerSteps into subway graph
 */
export function processStepsToSubway(
    steps: VisualizerStep[],
    agentNameMap: Record<string, string> = {}
): SubwayGraphResult {
    const context: SubwayBuildContext = {
        stops: [],
        tracks: [],
        branches: [],
        lanes: [createLane(0, TRACK_COLORS.DEFAULT)],
        nextStopY: 50,
        taskToLaneMap: new Map(),
        currentLane: 0,
        steps,
        stepIndex: 0,
        stopCounter: 0,
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

    return {
        stops: context.stops,
        tracks: context.tracks,
        branches: context.branches,
        totalLanes: context.lanes.length,
        totalHeight: context.nextStopY + 100,
    };
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
function getLaneForTask(taskId: string, context: SubwayBuildContext, color?: string): number {
    // Check if task already has a lane
    const existingLane = context.taskToLaneMap.get(taskId);
    if (existingLane !== undefined) {
        return existingLane;
    }

    // Find an inactive lane or create a new one
    let lane = context.lanes.findIndex(l => !l.isActive);

    if (lane === -1) {
        // No inactive lanes, create a new one
        lane = context.lanes.length;
        context.lanes.push(createLane(lane, color || TRACK_COLORS.DEFAULT));
    }

    // Activate the lane
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
function releaseLane(taskId: string, context: SubwayBuildContext): void {
    const lane = context.taskToLaneMap.get(taskId);
    if (lane !== undefined && context.lanes[lane]) {
        context.lanes[lane].isActive = false;
        context.lanes[lane].currentTaskId = undefined;
    }
}

/**
 * Create a stop on the subway map
 */
function createStop(
    type: SubwayStop['type'],
    label: string,
    laneIndex: number,
    step: VisualizerStep,
    context: SubwayBuildContext,
    additionalData?: Partial<SubwayStop>
): SubwayStop {
    const stop: SubwayStop = {
        id: `stop_${context.stopCounter++}`,
        type,
        label,
        y: context.nextStopY,
        laneIndex,
        visualizerStepId: step.id,
        trackColor: context.lanes[laneIndex]?.trackColor || TRACK_COLORS.DEFAULT,
        ...additionalData,
    };

    context.stops.push(stop);
    context.nextStopY += SUBWAY_LAYOUT_CONST.STOP_HEIGHT + SUBWAY_LAYOUT_CONST.STOP_SPACING;

    // Update lane's current stop
    if (context.lanes[laneIndex]) {
        context.lanes[laneIndex].currentStopId = stop.id;
    }

    return stop;
}

/**
 * Create a track segment between two stops
 */
function createTrack(
    fromStopId: string,
    toStopId: string,
    fromY: number,
    toY: number,
    fromLane: number,
    toLane: number,
    color: string,
    context: SubwayBuildContext,
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
function processStep(step: VisualizerStep, context: SubwayBuildContext): void {
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
 * Handle USER_REQUEST
 */
function handleUserRequest(step: VisualizerStep, context: SubwayBuildContext): void {
    const taskId = step.owningTaskId;
    const lane = getLaneForTask(taskId, context);

    // Create User stop
    const userStop = createStop('user', 'User', lane, step, context);

    // Create Agent stop
    const agentName = step.target || 'Agent';
    const displayName = context.agentNameMap[agentName] || agentName;
    const agentStop = createStop('agent', displayName, lane, step, context);

    // Connect them
    createTrack(
        userStop.id,
        agentStop.id,
        userStop.y,
        agentStop.y,
        lane,
        lane,
        context.lanes[lane].trackColor,
        context,
        'solid',
        step.id
    );
}

/**
 * Handle AGENT_LLM_CALL
 */
function handleLLMCall(step: VisualizerStep, context: SubwayBuildContext): void {
    const taskId = step.owningTaskId;
    const lane = context.taskToLaneMap.get(taskId) ?? 0;

    const prevStopId = context.lanes[lane]?.currentStopId;
    if (!prevStopId) return;

    const llmStop = createStop('llm', 'LLM', lane, step, context, {
        status: 'in-progress',
    });

    const prevStop = context.stops.find(s => s.id === prevStopId);
    if (prevStop) {
        createTrack(
            prevStopId,
            llmStop.id,
            prevStop.y,
            llmStop.y,
            lane,
            lane,
            context.lanes[lane].trackColor,
            context,
            'solid',
            step.id
        );
    }
}

/**
 * Handle AGENT_TOOL_INVOCATION_START
 */
function handleToolInvocation(step: VisualizerStep, context: SubwayBuildContext): void {
    const isPeer = step.data.toolInvocationStart?.isPeerInvocation || step.target?.startsWith('peer_');
    const target = step.target || '';
    const toolName = step.data.toolInvocationStart?.toolName || target;

    // Skip workflow tools (handled separately)
    if (target.includes('workflow_') || toolName.includes('workflow_')) {
        return;
    }

    const parentTaskId = step.owningTaskId;
    const parentLane = context.taskToLaneMap.get(parentTaskId) ?? 0;

    if (isPeer) {
        // Branch to new lane for sub-agent
        const peerName = target.startsWith('peer_') ? target.substring(5) : target;
        const displayName = context.agentNameMap[peerName] || peerName;
        const subTaskId = step.delegationInfo?.[0]?.subTaskId || step.owningTaskId;

        // Get new lane for sub-agent
        const newLane = getLaneForTask(subTaskId, context, context.lanes[parentLane].trackColor);

        const prevStopId = context.lanes[parentLane]?.currentStopId;
        const prevStop = context.stops.find(s => s.id === prevStopId);

        // Create branch point
        if (prevStop) {
            context.branches.push({
                id: `branch_${prevStop.id}_${newLane}`,
                y: context.nextStopY - SUBWAY_LAYOUT_CONST.STOP_SPACING,
                type: 'fork',
                sourceLane: parentLane,
                targetLanes: [newLane],
                color: context.lanes[parentLane].trackColor,
            });
        }

        // Create sub-agent stop on new lane
        const agentStop = createStop('agent', displayName, newLane, step, context);

        // Create track from parent lane to new lane
        if (prevStop) {
            createTrack(
                prevStop.id,
                agentStop.id,
                prevStop.y,
                agentStop.y,
                parentLane,
                newLane,
                context.lanes[newLane].trackColor,
                context,
                'solid',
                step.id
            );
        }
    } else {
        // Regular tool - stays on same lane
        const prevStopId = context.lanes[parentLane]?.currentStopId;
        if (!prevStopId) return;

        const toolStop = createStop('tool', toolName, parentLane, step, context, {
            status: 'in-progress',
        });

        const prevStop = context.stops.find(s => s.id === prevStopId);
        if (prevStop) {
            createTrack(
                prevStopId,
                toolStop.id,
                prevStop.y,
                toolStop.y,
                parentLane,
                parentLane,
                context.lanes[parentLane].trackColor,
                context,
                'solid',
                step.id
            );
        }
    }
}

/**
 * Handle AGENT_TOOL_EXECUTION_RESULT - merge back to parent lane if peer
 */
function handleToolResult(step: VisualizerStep, context: SubwayBuildContext): void {
    const isPeer = step.data.toolResult?.isPeerResponse;

    if (isPeer) {
        const subTaskId = step.owningTaskId;
        const subLane = context.taskToLaneMap.get(subTaskId);
        const parentTaskId = step.parentTaskId;
        const parentLane = parentTaskId ? context.taskToLaneMap.get(parentTaskId) : undefined;

        if (subLane !== undefined && parentLane !== undefined) {
            const subStopId = context.lanes[subLane]?.currentStopId;
            const parentStopId = context.lanes[parentLane]?.currentStopId;

            if (subStopId && parentStopId) {
                const subStop = context.stops.find(s => s.id === subStopId);
                const parentStop = context.stops.find(s => s.id === parentStopId);

                if (subStop && parentStop) {
                    // Create join point
                    context.branches.push({
                        id: `join_${subLane}_${parentLane}`,
                        y: context.nextStopY,
                        type: 'join',
                        sourceLane: subLane,
                        targetLanes: [parentLane],
                        color: context.lanes[subLane].trackColor,
                    });

                    // Create track merging back
                    createTrack(
                        subStop.id,
                        parentStop.id,
                        subStop.y,
                        context.nextStopY,
                        subLane,
                        parentLane,
                        context.lanes[subLane].trackColor,
                        context,
                        'solid',
                        step.id
                    );

                    // Release the sub-lane
                    releaseLane(subTaskId, context);
                }
            }
        }
    }
}

/**
 * Handle AGENT_RESPONSE_TEXT
 */
function handleAgentResponse(step: VisualizerStep, context: SubwayBuildContext): void {
    // Only for top-level responses
    if (step.nestingLevel && step.nestingLevel > 0) return;

    const taskId = step.owningTaskId;
    const lane = context.taskToLaneMap.get(taskId) ?? 0;
    const prevStopId = context.lanes[lane]?.currentStopId;

    if (!prevStopId) return;

    const userStop = createStop('user', 'User', lane, step, context);

    const prevStop = context.stops.find(s => s.id === prevStopId);
    if (prevStop) {
        createTrack(
            prevStopId,
            userStop.id,
            prevStop.y,
            userStop.y,
            lane,
            lane,
            context.lanes[lane].trackColor,
            context,
            'solid',
            step.id
        );
    }

    // Release the lane
    releaseLane(taskId, context);
}

/**
 * Handle WORKFLOW_EXECUTION_START - branch to new colored lane
 */
function handleWorkflowStart(step: VisualizerStep, context: SubwayBuildContext): void {
    const workflowName = step.data.workflowExecutionStart?.workflowName || 'Workflow';
    const displayName = context.agentNameMap[workflowName] || workflowName;
    const executionId = step.data.workflowExecutionStart?.executionId || step.owningTaskId;

    // Get a unique color for this workflow
    const workflowColor = getWorkflowColor(executionId, context);

    // Find parent task
    const parentTaskId = step.parentTaskId || step.owningTaskId;
    const parentLane = context.taskToLaneMap.get(parentTaskId) ?? 0;

    // Allocate new lane for workflow
    const workflowLane = getLaneForTask(executionId, context, workflowColor);

    const prevStopId = context.lanes[parentLane]?.currentStopId;
    const prevStop = context.stops.find(s => s.id === prevStopId);

    // Create branch point
    if (prevStop) {
        context.branches.push({
            id: `branch_wf_${executionId}`,
            y: context.nextStopY - SUBWAY_LAYOUT_CONST.STOP_SPACING,
            type: 'fork',
            sourceLane: parentLane,
            targetLanes: [workflowLane],
            color: workflowColor,
        });
    }

    // Create workflow start stop
    const workflowStop = createStop('workflow-start', `${displayName} ▸`, workflowLane, step, context, {
        trackColor: workflowColor,
    });

    // Create track
    if (prevStop) {
        createTrack(
            prevStop.id,
            workflowStop.id,
            prevStop.y,
            workflowStop.y,
            parentLane,
            workflowLane,
            workflowColor,
            context,
            'solid',
            step.id
        );
    }

    // Set current lane to workflow lane
    context.currentLane = workflowLane;
}

/**
 * Handle WORKFLOW_NODE_EXECUTION_START
 */
function handleWorkflowNodeStart(step: VisualizerStep, context: SubwayBuildContext): void {
    const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
    const nodeId = step.data.workflowNodeExecutionStart?.nodeId || 'unknown';
    const agentName = step.data.workflowNodeExecutionStart?.agentName;
    const label = agentName || nodeId;

    const executionId = step.owningTaskId;
    const lane = context.taskToLaneMap.get(executionId) ?? context.currentLane;

    const prevStopId = context.lanes[lane]?.currentStopId;
    if (!prevStopId) return;

    // Determine stop type
    let stopType: SubwayStop['type'] = 'agent';
    if (nodeType === 'conditional') stopType = 'conditional';

    const stop = createStop(stopType, label, lane, step, context, {
        condition: step.data.workflowNodeExecutionStart?.condition,
    });

    const prevStop = context.stops.find(s => s.id === prevStopId);
    if (prevStop) {
        createTrack(
            prevStopId,
            stop.id,
            prevStop.y,
            stop.y,
            lane,
            lane,
            context.lanes[lane].trackColor,
            context,
            'solid',
            step.id
        );
    }

    // For agent nodes, create sub-task context
    if (nodeType === 'agent') {
        const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
        if (subTaskId) {
            context.taskToLaneMap.set(subTaskId, lane);
        }
    }
}

/**
 * Handle WORKFLOW_EXECUTION_RESULT - merge back to parent
 */
function handleWorkflowEnd(step: VisualizerStep, context: SubwayBuildContext): void {
    const executionId = step.owningTaskId;
    const workflowLane = context.taskToLaneMap.get(executionId);

    if (workflowLane === undefined) return;

    const prevStopId = context.lanes[workflowLane]?.currentStopId;
    if (!prevStopId) return;

    // Create workflow end stop
    const displayName = context.workflowColors.has(executionId)
        ? `Workflow ◂`
        : 'End';

    const endStop = createStop('workflow-end', displayName, workflowLane, step, context);

    const prevStop = context.stops.find(s => s.id === prevStopId);
    if (prevStop) {
        createTrack(
            prevStopId,
            endStop.id,
            prevStop.y,
            endStop.y,
            workflowLane,
            workflowLane,
            context.lanes[workflowLane].trackColor,
            context,
            'solid',
            step.id
        );
    }

    // Find parent task and merge back
    const parentTaskId = step.parentTaskId;
    if (parentTaskId) {
        const parentLane = context.taskToLaneMap.get(parentTaskId);
        if (parentLane !== undefined) {
            const parentStopId = context.lanes[parentLane]?.currentStopId;
            if (parentStopId) {
                // Create join point
                context.branches.push({
                    id: `join_wf_${executionId}`,
                    y: context.nextStopY,
                    type: 'join',
                    sourceLane: workflowLane,
                    targetLanes: [parentLane],
                    color: context.lanes[workflowLane].trackColor,
                });

                // Create merge track
                createTrack(
                    endStop.id,
                    parentStopId,
                    endStop.y,
                    context.nextStopY,
                    workflowLane,
                    parentLane,
                    context.lanes[workflowLane].trackColor,
                    context,
                    'solid',
                    step.id
                );
            }
        }
    }

    // Release workflow lane
    releaseLane(executionId, context);
}

/**
 * Handle TASK_COMPLETED
 */
function handleTaskCompleted(step: VisualizerStep, context: SubwayBuildContext): void {
    const taskId = step.owningTaskId;
    releaseLane(taskId, context);
}

/**
 * Get workflow color (cycle through available colors)
 */
function getWorkflowColor(executionId: string, context: SubwayBuildContext): string {
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

