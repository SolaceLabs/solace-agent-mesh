import ActionRegistry from "./ActionRegistry";
import { createNavigationAction } from "./NavigationAction";
import type { Project } from "@/lib/types/projects";

/**
 * Dynamic navigation action loader
 * Fetches data and creates navigation actions for dynamic content
 */
export class DynamicNavigationLoader {
    private static instance: DynamicNavigationLoader;
    private projectsLoaded = false;

    private constructor() {
        // Private constructor for singleton pattern
    }

    static getInstance(): DynamicNavigationLoader {
        if (!DynamicNavigationLoader.instance) {
            DynamicNavigationLoader.instance = new DynamicNavigationLoader();
        }
        return DynamicNavigationLoader.instance;
    }

    /**
     * Load project-specific navigation actions
     */
    async loadProjectActions(projects: Project[]): Promise<void> {
        const registry = ActionRegistry.getInstance();

        // Unregister old project actions if they exist
        const existingProjectActions = registry.getAllActions().filter(action => action.id.startsWith("nav:project:"));
        existingProjectActions.forEach(action => registry.unregister(action.id));

        // Register new project actions
        const projectActions = projects.map(project =>
            createNavigationAction({
                id: `nav:project:${project.id}`,
                label: `Go to Project: ${project.name}`,
                path: `/projects/${project.id}`,
                description: project.description || `Open the ${project.name} project`,
                keywords: ["project", project.name.toLowerCase(), ...(project.description?.toLowerCase().split(" ") || [])],
            })
        );

        registry.registerMany(projectActions);
        this.projectsLoaded = true;
    }

    /**
     * Register static subsection navigation actions
     */
    registerStaticSubsections(): void {
        const registry = ActionRegistry.getInstance();

        // Chat subsections
        registry.register(
            createNavigationAction({
                id: "nav:chat:new",
                label: "New Chat Session",
                path: "/chat",
                description: "Start a new conversation",
                keywords: ["new", "chat", "conversation", "session", "start"],
            })
        );

        // Prompt subsections
        registry.registerMany([
            createNavigationAction({
                id: "nav:prompts:new",
                label: "Create New Prompt",
                path: "/prompts/new",
                description: "Open the prompt builder to create a new prompt template",
                keywords: ["new", "create", "prompt", "template", "builder"],
            }),
            createNavigationAction({
                id: "nav:prompts:new:manual",
                label: "Create Prompt Manually",
                path: "/prompts/new?mode=manual",
                description: "Create a new prompt using the manual editor",
                keywords: ["new", "create", "prompt", "manual", "editor"],
            }),
        ]);
    }

    /**
     * Reset loaded state (useful for forcing reload)
     */
    reset(): void {
        this.projectsLoaded = false;
    }

    /**
     * Check if projects have been loaded
     */
    isProjectsLoaded(): boolean {
        return this.projectsLoaded;
    }
}

export default DynamicNavigationLoader;
