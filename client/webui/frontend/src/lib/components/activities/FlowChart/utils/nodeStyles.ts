/**
 * Common base styles for different node types
 * Provides consistent styling for container, shape, shadow, and transitions
 */
export const ACTIVITY_NODE_BASE_STYLES = {
    /** Rectangular node style - used by Agent nodes
     * Figma Card: rounded (4px), shadow, 16px padding
     */
    RECTANGULAR:
        "group relative flex cursor-pointer items-center justify-between rounded border border-transparent bg-(--color-background-w10) px-4 py-2 shadow transition-all duration-200 ease-in-out hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",

    /** Rectangular compact style - used by Tool/LLM nodes */
    RECTANGULAR_COMPACT:
        "group relative flex cursor-pointer items-center justify-center rounded border border-transparent bg-(--color-background-w10) px-3 py-2 shadow transition-all duration-200 hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",

    /** Pill-shaped node style - used by Start/End/Join nodes */
    PILL: "flex items-center justify-center gap-2 rounded-full bg-(--color-primary-w10) px-4 py-2 shadow-sm dark:bg-(--color-primary-w90) dark:!shadow-none",

    /** Container header style - used by Loop/Map expanded header */
    CONTAINER_HEADER:
        "group relative mx-auto w-fit cursor-pointer rounded border border-transparent bg-(--color-background-w10) shadow transition-all duration-200 hover:shadow-md dark:border-(--color-secondary-w70) dark:bg-(--color-background-wMain) dark:hover:bg-(--color-primary-w100) dark:!shadow-none",
} as const;

/**
 * Shared CSS classes for node selection styling
 * Changes border color to accent-n2-wMain instead of adding a ring
 */
export const ACTIVITY_NODE_SELECTED_CLASS = "!border-(--color-accent-n2-wMain)";

/**
 * Shared CSS classes for node highlighting (used for processing state)
 * Note: This is different from workflow highlight (which uses amber for expression references)
 * Activity nodes use this for the processing-halo animation
 */
export const ACTIVITY_NODE_PROCESSING_CLASS = "processing-halo";

/**
 * Connector line styling for vertical lines between nodes
 * Matches workflow visualization connector colors
 * Dark mode hex value should be swapped out once the stateLayer dark mode is defined correctly in the palette
 */
export const CONNECTOR_LINE_CLASSES = "bg-(--color-stateLayer-w20) dark:bg-[#FFFFFF2a]";

/**
 * Connector stroke styling for SVG paths (used in WorkflowGroup bezier curves)
 * Dark mode hex value should be swapped out once the stateLayer dark mode is defined correctly in the palette
 */
export const CONNECTOR_STROKE_CLASSES = "stroke-(--color-stateLayer-w20) dark:stroke-[#FFFFFF2a]";

/**
 * Standard connector sizes
 */
export const CONNECTOR_SIZES = {
    MAIN: "h-4 w-0.5",
    BRANCH: "h-3 w-0.5",
} as const;

/**
 * Container children styling for dotted border containers
 * Used by Loop, Map, Workflow, and Agent nodes for their child content areas
 * Dark mode hex value should be swapped out once the stateLayer dark mode is defined correctly in the palette
 */
export const CONTAINER_CHILDREN_CLASSES = "rounded border-1 border-dashed border-(--color-secondary-w40) bg-(--color-stateLayer-w10) dark:border-(--color-secondary-w70) dark:bg-[#FFFFFF1a]";

/**
 * Layout dimensions and sizing constants for activity nodes
 * Contains only shared values used across multiple node types
 */
export const ACTIVITY_NODE_LAYOUT = {
    /** Standard header height for container nodes (Loop, Map, Workflow) */
    HEADER_HEIGHT: 44,
    /** Standard width for container nodes (Loop, Workflow) */
    CONTAINER_WIDTH: 280,
    /** Minimum height for leaf nodes (Agent, Tool) */
    LEAF_NODE_MIN_HEIGHT: 50,
} as const;
