import ActionRegistry from "./ActionRegistry";
import { createNavigationAction } from "./NavigationAction";
import DynamicNavigationLoader from "./DynamicNavigationLoader";

/**
 * Initialize and register all default actions
 */
export function initializeActions(): void {
    const registry = ActionRegistry.getInstance();

    // Clear any existing actions (useful for hot reloading)
    registry.clear();

    // Register navigation actions for all top-level pages
    registry.registerMany([
        createNavigationAction({
            id: "nav:chat",
            label: "Go to Chat",
            path: "/chat",
            description: "Open the chat interface to start or continue conversations",
            keywords: ["chat", "conversation", "message", "talk"],
        }),
        createNavigationAction({
            id: "nav:projects",
            label: "Go to Projects",
            path: "/projects",
            description: "View and manage your projects",
            keywords: ["projects", "workspace", "folders"],
        }),
        createNavigationAction({
            id: "nav:prompts",
            label: "Go to Prompt Library",
            path: "/prompts",
            description: "Browse and manage your prompt templates",
            keywords: ["prompts", "templates", "library", "saved"],
        }),
        createNavigationAction({
            id: "nav:agents",
            label: "Go to Agent Mesh",
            path: "/agents",
            description: "View the agent mesh and workflow visualizations",
            keywords: ["agents", "mesh", "workflow", "visualization", "network"],
        }),
    ]);

    // Register static subsection actions
    const loader = DynamicNavigationLoader.getInstance();
    loader.registerStaticSubsections();
}

// Export the registry and types
export { default as ActionRegistry } from "./ActionRegistry";
export { default as DynamicNavigationLoader } from "./DynamicNavigationLoader";
export * from "./types";
export * from "./NavigationAction";
