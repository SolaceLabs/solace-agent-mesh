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
        caseNumber?: number; // The case number (1-indexed) for condition pills
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
    isHighlighted?: boolean;
    onClick?: (node: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
    onHighlightNodes?: (nodeIds: string[]) => void;
    knownNodeIds?: Set<string>;
    /** Current workflow name - used for building sub-workflow navigation URLs */
    currentWorkflowName?: string;
    /** Parent workflow path (for breadcrumb navigation) */
    parentPath?: string[];
}

/**
 * Shared CSS classes for node highlighting when referenced in expressions
 * Used by all node components to ensure consistent highlight styling
 */
export const NODE_HIGHLIGHT_CLASSES =
    "ring-1 ring-amber-400 ring-offset-2 shadow-lg shadow-amber-200/50 dark:ring-amber-500 dark:ring-offset-gray-900 dark:shadow-amber-500/30";

/**
 * Common base styles for different node types
 * Provides consistent styling for container, shape, shadow, and transitions
 * Based on Figma Card component design (resting state)
 */
export const NODE_BASE_STYLES = {
    /** Rectangular node style - used by Agent, Workflow, Switch nodes
     * Figma Card: rounded (4px), shadow, 16px padding
     */
    RECTANGULAR: "group relative flex cursor-pointer items-center justify-between rounded border border-transparent bg-(--color-background-w10) px-4 py-3 shadow transition-all duration-200 ease-in-out hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
    /** Rectangular compact style - used by Loop/Map collapsed nodes */
    RECTANGULAR_COMPACT: "group relative flex cursor-pointer items-center justify-between rounded border border-transparent bg-(--color-background-w10) px-3 py-2 shadow transition-all duration-200 hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
    /** Pill-shaped node style - used by Start/End nodes */
    PILL: "flex cursor-pointer items-center justify-center gap-2 rounded-full bg-(--color-primary-w10) dark:hover:bg-(--color-primary-wMain) px-4 py-2 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:bg-(--color-primary-w90) dark:!shadow-none",
    /** Container header style - used by Loop/Map expanded header */
    CONTAINER_HEADER: "group relative mx-auto w-fit cursor-pointer rounded border border-transparent bg-(--color-background-w10) shadow transition-all duration-200 hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
    /** Condition pill style - used by Switch condition pills */
    CONDITION_PILL: "flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium shadow-sm transition-all duration-200 bg-(--color-background-w10) dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
    /** Switch node style - similar to rectangular but without justify-between */
    SWITCH: "group relative cursor-pointer rounded border border-transparent bg-(--color-background-w10) shadow transition-all duration-200 hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
} as const;

/**
 * Shared CSS classes for node ID badge that appears on hover
 * Shows the node's ID at the bottom center with fade in/out animation
 */
export const NODE_ID_BADGE_CLASSES =
    "absolute -bottom-2 left-1/2 -translate-x-1/2 rounded bg-gray-700 px-2 py-0.5 font-mono text-xs text-gray-100 opacity-0 transition-opacity duration-[750ms] ease-in group-hover:opacity-100 group-hover:duration-75 group-hover:ease-out dark:bg-gray-600";

/**
 * Shared CSS classes for node selection styling
 * Changes border color to accent-n2-wMain instead of adding a ring
 */
/** Standard selection border for most nodes */
export const NODE_SELECTED_CLASS = "!border-(--color-accent-n2-wMain)";

/** Selection border for compact nodes (condition pills) */
export const NODE_SELECTED_CLASS_COMPACT = "!border-(--color-accent-n2-wMain)";

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
        LOOP_CONDITION_ROW: 28, // Extra height for loop condition/max iterations row
    },
    SPACING: {
        VERTICAL: 60,
        VERTICAL_BRANCH: 100, // Extra spacing when there are condition pills (switch branches)
        HORIZONTAL: 32,
        CONTAINER_PADDING: 24, // Padding inside container nodes (Map/Loop)
        BRANCH_GAP: 24,
    },
    COLLAPSE_THRESHOLDS: {
        SWITCH_CASES: 3,
        CONTAINER_CHILDREN: 3,
    },
};
