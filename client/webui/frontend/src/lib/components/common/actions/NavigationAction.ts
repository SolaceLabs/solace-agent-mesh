import type { ExecutableAction, ActionContext } from "./types";

/**
 * Navigation action for navigating to different pages in the application
 */
export class NavigationAction implements ExecutableAction {
    id: string;
    label: string;
    description?: string;
    keywords?: string[];
    category = "navigation";
    private path: string;

    constructor(config: { id: string; label: string; path: string; description?: string; keywords?: string[] }) {
        this.id = config.id;
        this.label = config.label;
        this.path = config.path;
        this.description = config.description;
        this.keywords = config.keywords;
    }

    execute(context: ActionContext): void {
        if (!context.navigate) {
            console.error("Navigate function not provided in context");
            return;
        }
        context.navigate(this.path);
    }
}

/**
 * Factory function to create navigation actions
 */
export function createNavigationAction(config: { id: string; label: string; path: string; description?: string; keywords?: string[] }): NavigationAction {
    return new NavigationAction(config);
}
