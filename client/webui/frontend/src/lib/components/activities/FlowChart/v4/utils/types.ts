import type { VisualizerStep } from "@/lib/types";

/**
 * V4 Hybrid Types: Combines V2's containment with V3's subway tracks
 *
 * Concept: Agents are "cities" with multiple internal "stops" (tools/LLMs).
 * Subway tracks run through the cities, connecting the stops.
 */

/**
 * A stop on the subway track - can be inside a container or standalone
 */
export interface Stop {
    id: string;
    type: 'user' | 'agent' | 'tool' | 'llm' | 'conditional';
    label: string;
    visualizerStepId?: string;

    // Position (relative to parent container if inside one)
    y: number;

    // Lane assignment
    laneIndex: number;

    // Track styling
    trackColor: string;

    // Status
    status?: 'idle' | 'in-progress' | 'completed' | 'error';

    // For conditionals
    condition?: string;
    conditionResult?: boolean;
}

/**
 * A container node that holds stops and other containers
 * Agents and Workflows are containers
 */
export interface ContainerNode {
    id: string;
    type: 'agent' | 'workflow-group';
    label: string;
    visualizerStepId?: string;

    // Contains stops (tools, LLMs) and nested containers (sub-agents)
    stops: Stop[];
    children: ContainerNode[];

    // Parallel branches (for Map/Fork nodes)
    parallelBranches?: ContainerNode[][];

    // Position and dimensions (calculated by layout engine)
    x: number;
    y: number;
    width: number;
    height: number;

    // Lane assignment - the track runs through this container
    laneIndex: number;
    trackColor: string;

    // For workflow groups
    isWorkflow?: boolean;
    workflowName?: string;
}

/**
 * Track segment connecting stops (may cross container boundaries)
 */
export interface TrackSegment {
    id: string;
    fromStopId: string;
    toStopId: string;
    fromY: number; // Absolute Y position
    toY: number;
    fromLane: number;
    toLane: number;
    color: string;
    style: 'solid' | 'dashed';
    visualizerStepId?: string;

    // Track path may go through containers
    throughContainerIds?: string[];
}

/**
 * Branch/merge point for parallel execution
 */
export interface BranchPoint {
    id: string;
    y: number; // Absolute Y position
    type: 'fork' | 'join';
    sourceLane: number;
    targetLanes: number[];
    color: string;
}

/**
 * Lane state - tracks which containers/stops are using each lane
 */
export interface LaneState {
    index: number;
    isActive: boolean;
    currentTaskId?: string;
    currentStopId?: string;
    trackColor: string;
}

/**
 * Build context for processing steps
 */
export interface BuildContext {
    // Output data structures
    containers: ContainerNode[];
    allStops: Stop[];
    tracks: TrackSegment[];
    branches: BranchPoint[];

    // Lane management
    lanes: LaneState[];
    nextY: number; // Next available Y position

    // Task/node tracking
    taskToContainerMap: Map<string, ContainerNode>; // Task ID -> containing node
    taskToLaneMap: Map<string, number>;
    stopIdMap: Map<string, Stop>; // Stop ID -> Stop object
    containerIdMap: Map<string, ContainerNode>;

    // Current context
    currentContainer?: ContainerNode;
    currentLane: number;

    // Input data
    steps: VisualizerStep[];
    stepIndex: number;
    stopCounter: number;
    containerCounter: number;

    // Agent name mapping
    agentNameMap: Record<string, string>;

    // Workflow colors
    workflowColors: Map<string, string>;
    defaultTrackColor: string;
}

/**
 * Result of V4 layout processing
 */
export interface LayoutResult {
    containers: ContainerNode[];
    stops: Stop[];
    tracks: TrackSegment[];
    branches: BranchPoint[];
    totalLanes: number;
    totalWidth: number;
    totalHeight: number;
}

/**
 * Layout constants
 */
export const LAYOUT_CONSTANTS = {
    // Container sizing
    AGENT_MIN_WIDTH: 180,
    AGENT_HEADER_HEIGHT: 50,
    AGENT_PADDING: 20,
    WORKFLOW_MIN_WIDTH: 200,
    WORKFLOW_PADDING: 30,

    // Stop sizing
    STOP_HEIGHT: 40,
    STOP_MIN_WIDTH: 120,
    STOP_SPACING: 12,
    STOP_CIRCLE_RADIUS: 8,

    // Lane and track
    LANE_WIDTH: 60,
    LEFT_MARGIN: 100,
    TRACK_WIDTH: 3,

    // Spacing
    CONTAINER_VERTICAL_SPACING: 40,
    CONTAINER_HORIZONTAL_SPACING: 40,
    PARALLEL_BRANCH_GAP: 30,
};

/**
 * Track colors
 */
export const TRACK_COLORS = {
    DEFAULT: '#3b82f6', // Blue
    WORKFLOW_1: '#8b5cf6', // Purple
    WORKFLOW_2: '#ec4899', // Pink
    WORKFLOW_3: '#10b981', // Green
    WORKFLOW_4: '#f59e0b', // Amber
    ERROR: '#ef4444', // Red
};
