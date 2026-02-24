import { Bot, FolderOpen, BookOpenText, Bell, User, LogOut } from "lucide-react";

import type { NavItemConfig } from "./CollapsibleNavigationSidebar";

/**
 * Default navigation items for Solace Agent Mesh.
 * External consumers can use these as a reference or import them directly.
 */
export const SAM_NAV_ITEMS: NavItemConfig[] = [
    {
        id: "projects",
        label: "Projects",
        icon: FolderOpen,
        route: "/projects",
        routeMatch: "/projects",
    },
    {
        id: "assets",
        label: "Assets",
        icon: BookOpenText,
        children: [
            // Artifacts page is not ready yet, so commenting out for now but keeping in presets for reference
            // {
            //     id: "artifacts",
            //     label: "Artifacts",
            //     icon: BookOpenText,
            //     route: "/artifacts",
            //     routeMatch: "/artifacts",
            // },
            {
                id: "prompts",
                label: "Prompts",
                icon: BookOpenText,
                route: "/prompts",
                routeMatch: "/prompts",
                lifecycle: "experimental",
            },
        ],
        defaultExpanded: false,
    },
    {
        id: "agents",
        label: "Agents",
        icon: Bot,
        route: "/agents",
        routeMatch: "/agents",
    },
];

/**
 * Default bottom navigation items for Solace Agent Mesh.
 * External consumers can use these as a reference or import them directly.
 */
export const SAM_BOTTOM_ITEMS: NavItemConfig[] = [
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "userAccount", label: "User Account", icon: User },
    { id: "logout", label: "Log Out", icon: LogOut },
];

/**
 * Helper to filter nav items by feature flags.
 * @example
 * filterNavItems(SAM_NAV_ITEMS, { projects: true })
 */
export function filterNavItems(items: NavItemConfig[], enabledFeatures: Record<string, boolean>): NavItemConfig[] {
    return items.filter(item => {
        // Map item IDs to feature flag names
        const featureMap: Record<string, string> = {
            projects: "projects",
        };
        const featureKey = featureMap[item.id];
        if (featureKey && enabledFeatures[featureKey] === false) {
            return false;
        }
        return true;
    });
}

/**
 * Helper to filter bottom items by feature flags.
 * @example
 * filterBottomItems(SAM_BOTTOM_ITEMS, { logout: true })
 */
export function filterBottomItems(items: NavItemConfig[], enabledFeatures: Record<string, boolean>): NavItemConfig[] {
    return items.filter(item => {
        const featureMap: Record<string, string> = {
            logout: "logout",
        };
        const featureKey = featureMap[item.id];
        if (featureKey && enabledFeatures[featureKey] === false) {
            return false;
        }
        return true;
    });
}
