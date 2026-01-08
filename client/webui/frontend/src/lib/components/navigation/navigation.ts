import { MessageCircle, Bot, SunMoon, FolderOpen, NotepadText } from "lucide-react";

import type { NavigationItem } from "@/lib/types";

/**
 * Get filtered top navigation items based on feature flags.
 * This is the single source of truth for navigation items.
 *
 * @param featureFlags - Feature flags from backend config
 * @returns Filtered navigation items based on enabled features
 */
export const getTopNavigationItems = (featureFlags?: Record<string, boolean>): NavigationItem[] => {
    const items: NavigationItem[] = [
        {
            id: "chat",
            label: "Chat",
            icon: MessageCircle,
        },
        {
            id: "agentMesh",
            label: "Agents",
            icon: Bot,
        },
    ];

    // Add projects only if explicitly enabled (requires SQL persistence)
    // Default to false if flag is undefined to be safe
    const projectsEnabled = featureFlags?.projects ?? false;
    if (projectsEnabled) {
        items.push({
            id: "projects",
            label: "Projects",
            icon: FolderOpen,
        });
    }

    // Add prompts only if explicitly enabled (requires SQL persistence)
    // Default to false if flag is undefined to be safe
    const promptLibraryEnabled = featureFlags?.promptLibrary ?? false;
    if (promptLibraryEnabled) {
        items.push({
            id: "prompts",
            label: "Prompts",
            icon: NotepadText,
            badge: "EXPERIMENTAL",
        });
    }

    return items;
};

// Backward compatibility: export static items with all features for components that don't use feature flags yet
export const topNavigationItems: NavigationItem[] = [
    {
        id: "chat",
        label: "Chat",
        icon: MessageCircle,
    },
    {
        id: "agentMesh",
        label: "Agents",
        icon: Bot,
    },
    {
        id: "projects",
        label: "Projects",
        icon: FolderOpen,
    },
    {
        id: "prompts",
        label: "Prompts",
        icon: NotepadText,
        badge: "EXPERIMENTAL",
    },
];

export const bottomNavigationItems: NavigationItem[] = [
    {
        id: "theme-toggle",
        label: "Theme",
        icon: SunMoon,
        onClick: () => {}, // Will be handled in NavigationList
    },
];
