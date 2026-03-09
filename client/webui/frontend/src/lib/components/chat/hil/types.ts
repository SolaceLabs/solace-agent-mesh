/**
 * Local types for HIL (Human-in-the-Loop) components.
 */

/** Callback when a Button action fires. */
export interface SurfaceAction {
    eventName: string; // "submit" or "cancel"
    context: Record<string, unknown>;
    completionText: string; // text to show in the banner after this action completes
}

/** Resolved data from the dataModel, keyed by JSON pointer path. */
export type DataModelState = Record<string, unknown>;
