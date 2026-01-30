import type { VisualizerStep } from "@/lib/types";

/**
 * Represents a node in the layout tree structure.
 * Nodes can contain children (tools/LLMs/sub-agents) and have calculated positions/dimensions.
 */
export interface LayoutNode {
    id: string;
    type: "agent" | "tool" | "llm" | "user" | "switch" | "loop" | "map" | "group" | "workflow" | "parallelBlock";
    data: {
        label: string;
        visualizerStepId?: string;
        description?: string;
        status?: string;
        variant?: "default" | "pill";
        // Switch node fields
        condition?: string;
        cases?: { condition: string; node: string }[];
        defaultBranch?: string;
        selectedBranch?: string;
        selectedCaseIndex?: number;
        // Join node fields
        waitFor?: string[];
        joinStrategy?: string;
        joinN?: number;
        // Loop node fields
        maxIterations?: number;
        loopDelay?: string;
        currentIteration?: number;
        // Map/Fork node fields
        iterationIndex?: number;
        // Tool node fields - artifacts created by this tool
        createdArtifacts?: Array<{
            filename: string;
            version?: number;
            mimeType?: string;
            description?: string;
        }>;
        // Common fields
        isTopNode?: boolean;
        isBottomNode?: boolean;
        isSkipped?: boolean;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        [key: string]: any;
    };

    // Layout properties
    x: number; // Absolute X position
    y: number; // Absolute Y position
    width: number; // Calculated width
    height: number; // Calculated height

    // Hierarchy
    children: LayoutNode[]; // Sequential children (tools, LLMs, sub-agents)
    parallelBranches?: LayoutNode[][]; // For Map/Fork - each array is a parallel branch

    // Context
    owningTaskId?: string;
    parentTaskId?: string;
    functionCallId?: string;
}

/**
 * Represents an edge between two nodes in the visualization.
 */
export interface Edge {
    id: string;
    source: string; // Node ID
    target: string; // Node ID
    sourceX: number;
    sourceY: number;
    targetX: number;
    targetY: number;
    visualizerStepId?: string;
    label?: string;
    isError?: boolean;
    isSelected?: boolean;
}

/**
 * Context for building the layout tree from VisualizerSteps
 */
export interface BuildContext {
    steps: VisualizerStep[];
    stepIndex: number;
    nodeCounter: number;

    // Map task IDs to their container nodes
    taskToNodeMap: Map<string, LayoutNode>;

    // Map function call IDs to nodes (for tool results)
    functionCallToNodeMap: Map<string, LayoutNode>;

    // Current agent node being built
    currentAgentNode: LayoutNode | null;

    // Root nodes (top-level user/agent pairs)
    rootNodes: LayoutNode[];

    // Agent name display map
    agentNameMap: Record<string, string>;

    // Map workflow nodeId to Map/Fork node for parallel branch tracking
    parallelContainerMap: Map<string, LayoutNode>;

    // Track current branch within a parallel container
    currentBranchMap: Map<string, LayoutNode[]>;

    // Track if we've created top/bottom user nodes (only one each for entire flow)
    hasTopUserNode: boolean;
    hasBottomUserNode: boolean;

    // Track parallel peer delegation groups: maps a unique group key to the set of functionCallIds
    // Key format: `${owningTaskId}:parallel:${stepId}` where stepId is from the TOOL_DECISION step
    parallelPeerGroupMap: Map<string, Set<string>>;

    // Track the parallelBlock node for each parallel peer group (for adding peer agents to it)
    parallelBlockMap: Map<string, LayoutNode>;

    // Track sub-workflow -> parent group relationships (for workflow node types)
    // Maps subTaskId -> parent workflow group node
    subWorkflowParentMap: Map<string, LayoutNode>;
}

/**
 * Layout calculation result
 */
export interface LayoutResult {
    nodes: LayoutNode[];
    edges: Edge[];
    totalWidth: number;
    totalHeight: number;
}
