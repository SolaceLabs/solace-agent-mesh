import React from "react";
import { Bot, FolderOpen, BookOpenText, User, LogOut } from "lucide-react";

import { LifecycleBadge } from "@/lib/components/ui";
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
            {
                id: "prompts",
                label: "Prompts",
                icon: BookOpenText,
                route: "/prompts",
                routeMatch: "/prompts",
                badge: React.createElement(
                    LifecycleBadge,
                    {
                        className: "scale-90 border-[var(--color-secondary-text-w50)] text-[var(--color-secondary-text-w50)]",
                    },
                    "EXPERIMENTAL"
                ),
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
    { id: "userAccount", label: "User Account", icon: User, position: "bottom" },
    { id: "logout", label: "Log Out", icon: LogOut, position: "bottom" },
];

/**
 * Combined navigation items for Solace Agent Mesh.
 * Use this with the single `items` prop on CollapsibleNavigationSidebar.
 */
export const SAM_ITEMS: NavItemConfig[] = [...SAM_NAV_ITEMS, ...SAM_BOTTOM_ITEMS];

/**
 * Helper to filter combined items by feature flags.
 * @example
 * filterItems(SAM_ITEMS, { projects: true, logout: true })
 */
export function filterItems(items: NavItemConfig[], enabledFeatures: Record<string, boolean>): NavItemConfig[] {
    return items.filter(item => {
        const featureMap: Record<string, string> = {
            projects: "projects",
            logout: "logout",
        };
        const featureKey = featureMap[item.id];
        if (featureKey && enabledFeatures[featureKey] === false) {
            return false;
        }
        return true;
    });
}
