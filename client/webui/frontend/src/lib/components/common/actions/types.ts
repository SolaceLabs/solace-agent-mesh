/**
 * Base interface for all command palette actions
 */
export interface Action {
    /** Unique identifier for the action */
    id: string;
    /** Display name shown in the command palette */
    label: string;
    /** Optional description providing more context */
    description?: string;
    /** Optional keywords for better search matching */
    keywords?: string[];
    /** Category for grouping actions (e.g., "navigation", "file", "view") */
    category?: string;
}

/**
 * Context passed to action handlers
 */
export interface ActionContext {
    /** Router navigate function for navigation actions */
    navigate?: (path: string) => void;
    /** Toggle theme between light and dark */
    toggleTheme?: () => void;
    /** Set theme to a specific mode */
    setTheme?: (theme: "light" | "dark") => void;
    /** Any additional context needed by specific action types */
    [key: string]: unknown;
}

/**
 * Interface for executable actions
 */
export interface ExecutableAction extends Action {
    /** Execute the action with the given context */
    execute: (context: ActionContext) => void | Promise<void>;
}

/**
 * Type guard to check if an action is executable
 */
export function isExecutableAction(action: Action): action is ExecutableAction {
    return "execute" in action && typeof (action as ExecutableAction).execute === "function";
}
