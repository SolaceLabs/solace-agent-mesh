import type { VisualizerStep } from "@/lib/types";

/**
 * Represents a "stop" on the subway map - could be an agent, tool, LLM, etc.
 */
export interface SubwayStop {
    id: string;
    type: 'user' | 'agent' | 'tool' | 'llm' | 'conditional' | 'workflow-start' | 'workflow-end';
    label: string;
    visualizerStepId?: string;
    y: number; // Vertical position
    laneIndex: number; // Which lane this stop is on (0 = leftmost)
    status?: 'idle' | 'in-progress' | 'completed' | 'error';

    // Track color (for workflows and different contexts)
    trackColor?: string;

    // For conditionals
    condition?: string;
    conditionResult?: boolean;

    // Additional data
    description?: string;
    [key: string]: any;
}

/**
 * Represents a track segment - the line connecting stops
 */
export interface TrackSegment {
    id: string;
    fromStopId: string;
    toStopId: string;
    fromY: number;
    toY: number;
    fromLane: number;
    toLane: number;
    color: string;
    style: 'solid' | 'dashed'; // Dashed for skipped branches
    visualizerStepId?: string;
}

/**
 * Represents a branch/merge point where tracks split or join
 */
export interface BranchPoint {
    id: string;
    y: number;
    type: 'fork' | 'join';
    sourceLane: number;
    targetLanes: number[]; // For fork: which lanes branch off
    color: string;
}

/**
 * Context for building the subway graph
 */
export interface SubwayBuildContext {
    stops: SubwayStop[];
    tracks: TrackSegment[];
    branches: BranchPoint[];

    // Lane management
    lanes: LaneState[];
    nextStopY: number;

    // Task tracking
    taskToLaneMap: Map<string, number>; // Which lane a task is on
    currentLane: number; // Current active lane

    // Step tracking
    steps: VisualizerStep[];
    stepIndex: number;
    stopCounter: number;

    // Agent name mapping
    agentNameMap: Record<string, string>;

    // Track colors by context
    workflowColors: Map<string, string>; // Workflow execution ID -> color
    defaultTrackColor: string;
}

/**
 * State of a single lane
 */
export interface LaneState {
    index: number;
    isActive: boolean; // Is this lane currently in use?
    currentTaskId?: string; // Which task is using this lane
    currentStopId?: string; // Last stop on this lane
    trackColor: string; // Current color of track in this lane
}

/**
 * Result of subway graph generation
 */
export interface SubwayGraphResult {
    stops: SubwayStop[];
    tracks: TrackSegment[];
    branches: BranchPoint[];
    totalLanes: number;
    totalHeight: number;
}

/**
 * Layout constants for subway graph
 */
export const SUBWAY_LAYOUT = {
    LANE_WIDTH: 40, // Horizontal space per lane
    STOP_HEIGHT: 60, // Vertical space per stop
    STOP_SPACING: 20, // Extra spacing between stops
    LABEL_AREA_WIDTH: 200, // Width of label area on the right
    LEFT_MARGIN: 50, // Left margin before first lane
    STOP_CIRCLE_RADIUS: 8, // Radius of the stop circle
};

/**
 * Track colors for different contexts
 */
export const TRACK_COLORS = {
    DEFAULT: '#3b82f6', // Blue
    WORKFLOW_1: '#8b5cf6', // Purple
    WORKFLOW_2: '#ec4899', // Pink
    WORKFLOW_3: '#10b981', // Green
    WORKFLOW_4: '#f59e0b', // Amber
    ERROR: '#ef4444', // Red
};
