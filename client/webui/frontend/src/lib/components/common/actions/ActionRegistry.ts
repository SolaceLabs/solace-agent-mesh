import type { ExecutableAction } from "./types";

/**
 * Central registry for all command palette actions
 * Follows the singleton pattern to maintain a single source of truth
 */
class ActionRegistry {
    private static instance: ActionRegistry;
    private actions: Map<string, ExecutableAction> = new Map();

    private constructor() {
        // Private constructor for singleton pattern
    }

    /**
     * Get the singleton instance of the ActionRegistry
     */
    static getInstance(): ActionRegistry {
        if (!ActionRegistry.instance) {
            ActionRegistry.instance = new ActionRegistry();
        }
        return ActionRegistry.instance;
    }

    /**
     * Register a new action
     * @param action The action to register
     */
    register(action: ExecutableAction): void {
        if (this.actions.has(action.id)) {
            console.warn(`Action with id "${action.id}" is already registered. Overwriting.`);
        }
        this.actions.set(action.id, action);
    }

    /**
     * Register multiple actions at once
     * @param actions Array of actions to register
     */
    registerMany(actions: ExecutableAction[]): void {
        actions.forEach(action => this.register(action));
    }

    /**
     * Unregister an action by ID
     * @param id The ID of the action to remove
     */
    unregister(id: string): void {
        this.actions.delete(id);
    }

    /**
     * Get an action by ID
     * @param id The ID of the action to retrieve
     */
    getAction(id: string): ExecutableAction | undefined {
        return this.actions.get(id);
    }

    /**
     * Get all registered actions
     */
    getAllActions(): ExecutableAction[] {
        return Array.from(this.actions.values());
    }

    /**
     * Get actions filtered by category
     * @param category The category to filter by
     */
    getActionsByCategory(category: string): ExecutableAction[] {
        return Array.from(this.actions.values()).filter(action => action.category === category);
    }

    /**
     * Clear all registered actions
     */
    clear(): void {
        this.actions.clear();
    }
}

export default ActionRegistry;
