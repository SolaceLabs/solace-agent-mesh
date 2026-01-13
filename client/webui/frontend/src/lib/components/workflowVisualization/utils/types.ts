/**
 * Type definitions for Workflow Visualization components
 */

import type { WorkflowNodeConfig } from "@/lib/utils/agentUtils";

/**
 * Visual node types for workflow diagram
 */
export type WorkflowVisualNodeType =
    | "start"
    | "end"
    | "agent"
    | "workflow" // Nested workflow reference
    | "switch"
    | "map"
    | "loop"
    | "condition"; // Condition pill for switch branches

/**
 * Represents a positioned node in the visual layout
 */
export interface LayoutNode {
    id: string;
    type: WorkflowVisualNodeType;
    data: {
        label: string;
        agentName?: string;
        workflowName?: string; // For nested workflow references
        condition?: string; // For loop/switch nodes
        cases?: Array<{ condition: string; node: string }>; // For switch
        defaultCase?: string; // For switch default branch
        items?: string; // For map node
        maxIterations?: number; // For loop
        childNodeId?: string; // For map/loop inner node reference
        // For condition pill nodes
        conditionLabel?: string; // The condition text to display
        switchNodeId?: string; // The parent switch node ID
        targetNodeId?: string; // The node this condition leads to
        isDefaultCase?: boolean; // Whether this is the default case
        // Original workflow config for detail panel
        originalConfig?: WorkflowNodeConfig;
    };
    // Layout properties
    x: number;
    y: number;
    width: number;
    height: number;
    // Hierarchy
    children: LayoutNode[];
    // For switch node branches
    branches?: Array<{
        label: string;
        isDefault: boolean;
        nodes: LayoutNode[];
    }>;
    // UI state
    isCollapsed?: boolean;
    // Layout level (for positioning parallel nodes)
    level?: number;
}

/**
 * Represents an edge between nodes
 */
export interface Edge {
    id: string;
    source: string;
    target: string;
    sourceX: number;
    sourceY: number;
    targetX: number;
    targetY: number;
    label?: string; // For switch case labels
    isStraight?: boolean; // If true, render as straight line (used for pill -> target edges)
}

/**
 * Result of layout calculation
 */
export interface LayoutResult {
    nodes: LayoutNode[];
    edges: Edge[];
    totalWidth: number;
    totalHeight: number;
}

/**
 * Common props for all node components
 */
export interface NodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

/**
 * Layout constants for consistent sizing
 */
export const LAYOUT_CONSTANTS = {
    NODE_WIDTHS: {
        START: 100,
        END: 100,
        AGENT: 280,
        WORKFLOW: 280,
        SWITCH_COLLAPSED: 280,
        MAP_MIN: 320,
        LOOP_MIN: 320,
        CONDITION_PILL: 80, // Condition pills are smaller
    },
    NODE_HEIGHTS: {
        PILL: 40,
        AGENT: 56,
        SWITCH_COLLAPSED: 80,
        SWITCH_CASE_ROW: 32,
        CONTAINER_HEADER: 44,
        CONTAINER_COLLAPSED: 80, // Full collapsed height including "Content hidden" text
        CONDITION_PILL: 28, // Smaller height for condition pills
    },
    SPACING: {
        VERTICAL: 60,
        VERTICAL_BRANCH: 100, // Extra spacing when there are condition pills (switch branches)
        HORIZONTAL: 32,
        CONTAINER_PADDING: 16,
        BRANCH_GAP: 24,
    },
    COLLAPSE_THRESHOLDS: {
        SWITCH_CASES: 3,
        CONTAINER_CHILDREN: 3,
    },
};
