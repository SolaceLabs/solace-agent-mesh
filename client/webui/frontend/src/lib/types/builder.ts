/**
 * Builder Progress Types
 *
 * Types for tracking the creation progress of builder components
 * (agents, workflows, skills, connectors, gateways) during the
 * builder's object creation flow.
 */

/** Possible states for a builder component during creation */
export type BuilderComponentState = "queued" | "active" | "completed" | "failed" | "skipped" | "input-required";

/**
 * Represents the creation state of a single builder component —
 * an agent, workflow, skill, connector, or gateway.
 */
export interface BuilderComponentProgress {
    /** Unique ID for this component, e.g. "skill:web_search" */
    id: string;
    /** Component type from the build manifest */
    type: "gateway" | "workflow" | "agent" | "skill" | "connector";
    /** Display name for the component */
    name: string;
    /** Current creation state */
    state: BuilderComponentState;
    /** Optional status text, e.g. "Generating skill configuration..." */
    statusText?: string;
    /** Timestamp when state last changed */
    lastUpdated: number;
    /** For skills: estimated progress 0-100, if available */
    progressPercent?: number;
    /** Parent component ID for hierarchy (e.g., skill belongs to agent) */
    parentId?: string;
}

/**
 * Aggregate state for the entire build session, stored in ChatProvider.
 */
export interface BuilderCreationState {
    /** Whether a build is currently in progress */
    isBuilding: boolean;
    /** Parsed components from the build manifest */
    components: BuilderComponentProgress[];
    /** The build manifest filename for correlation */
    manifestFilename?: string;
    /** Overall build status */
    overallStatus: "idle" | "planning" | "building" | "completed" | "failed";
}

/**
 * SSE event payload for builder component progress updates.
 * Emitted by the Builder agent during creation.
 */
export interface BuilderComponentProgressEvent {
    type: "builder_component_progress";
    component_id: string;
    component_type: "gateway" | "workflow" | "agent" | "skill" | "connector";
    component_name: string;
    state: BuilderComponentState;
    status_text?: string;
    progress_percent?: number;
    parent_id?: string;
}

/** Default/initial builder creation state */
export const INITIAL_BUILDER_CREATION_STATE: BuilderCreationState = {
    isBuilding: false,
    components: [],
    overallStatus: "idle",
};
