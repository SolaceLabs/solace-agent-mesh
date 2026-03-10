import type { LucideIcon } from "lucide-react";
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
    icon?: LucideIcon;
    private path: string;

    constructor(config: { id: string; label: string; path: string; description?: string; keywords?: string[]; icon?: LucideIcon }) {
        this.id = config.id;
        this.label = config.label;
        this.path = config.path;
        this.description = config.description;
        this.keywords = config.keywords;
        this.icon = config.icon;
    }

    execute(context: ActionContext): void {
        if (!context.navigate) {
            console.error("Navigate function not provided in context");
            return;
        }
        context.navigate(this.path);

        // If navigating to chat, focus the input after navigation
        if (this.path.startsWith("/chat")) {
            setTimeout(() => {
                window.dispatchEvent(new Event("focus-chat-input"));
            }, 150);
        }
    }
}

/**
 * Factory function to create navigation actions
 */
export function createNavigationAction(config: { id: string; label: string; path: string; description?: string; keywords?: string[]; icon?: LucideIcon }): NavigationAction {
    return new NavigationAction(config);
}
