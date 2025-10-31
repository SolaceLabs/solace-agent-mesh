import { MessageCircle, Bot, SunMoon, FolderOpen } from "lucide-react";

import type { NavigationItem } from "@/lib/types";

const allTopNavigationItems: NavigationItem[] = [
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
    }
];

export const bottomNavigationItems: NavigationItem[] = [
    {
        id: "theme-toggle",
        label: "Theme",
        icon: SunMoon,
        onClick: () => {}, // Will be handled in NavigationList
    },
];

/**
 * Get filtered top navigation items based on feature flags
 * @param projectsEnabled - Whether projects feature is enabled
 * @returns Filtered navigation items
 */
export function getTopNavigationItems(projectsEnabled: boolean = true): NavigationItem[] {
    return allTopNavigationItems.filter(item => {
        // Filter out projects item if projects are disabled
        if (item.id === "projects" && !projectsEnabled) {
            return false;
        }
        return true;
    });
}

// Export default items for backward compatibility (with projects enabled)
export const topNavigationItems = getTopNavigationItems(true);
