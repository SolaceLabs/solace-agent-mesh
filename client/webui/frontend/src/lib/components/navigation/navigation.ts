import { MessageCircle, Bot, SunMoon, Command } from "lucide-react";

import type { NavigationItem } from "@/lib/types";

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
    
    // Add prompts only if explicitly enabled (requires SQL persistence)
    // Default to true if flag is undefined, but respect explicit false
    const promptLibraryEnabled = featureFlags?.promptLibrary ?? true;
    if (promptLibraryEnabled) {
        items.push({
            id: "prompts",
            label: "Prompts",
            icon: Command,
        });
    }
    
    return items;
};

// Backward compatibility: export static items for components that don't use feature flags yet
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
        id: "prompts",
        label: "Prompts",
        icon: Command,
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
