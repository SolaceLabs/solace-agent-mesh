import ActionRegistry from "./ActionRegistry";
import { createNavigationAction } from "./NavigationAction";
import { createSettingsAction } from "./SettingsAction";
import { createThemeAction } from "./ThemeAction";
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

    // Register settings actions
    registry.registerMany([
        createSettingsAction({
            id: "settings:open",
            label: "Open Settings",
            description: "Open the settings dialog",
            keywords: ["settings", "preferences", "configuration", "config"],
        }),
        createSettingsAction({
            id: "settings:general",
            label: "General Settings",
            section: "general",
            description: "Configure general application settings",
            keywords: ["settings", "general", "preferences"],
        }),
        createSettingsAction({
            id: "settings:speech",
            label: "Speech Settings",
            section: "speech",
            description: "Configure speech-to-text and text-to-speech settings",
            keywords: ["settings", "speech", "voice", "audio", "tts", "stt"],
        }),
        createSettingsAction({
            id: "settings:about",
            label: "About Product",
            section: "about",
            description: "View product information and version details",
            keywords: ["about", "version", "info", "information"],
        }),
    ]);

    // Register theme actions (direct manipulation without opening settings)
    registry.registerMany([
        createThemeAction({
            id: "theme:toggle",
            label: "Toggle Theme",
            mode: "toggle",
            description: "Switch between light and dark mode",
            keywords: ["theme", "dark", "light", "mode", "appearance", "toggle"],
        }),
        createThemeAction({
            id: "theme:light",
            label: "Switch to Light Mode",
            mode: "light",
            description: "Change the theme to light mode",
            keywords: ["theme", "light", "mode", "appearance", "bright"],
        }),
        createThemeAction({
            id: "theme:dark",
            label: "Switch to Dark Mode",
            mode: "dark",
            description: "Change the theme to dark mode",
            keywords: ["theme", "dark", "mode", "appearance", "night"],
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
export * from "./SettingsAction";
export * from "./ThemeAction";
