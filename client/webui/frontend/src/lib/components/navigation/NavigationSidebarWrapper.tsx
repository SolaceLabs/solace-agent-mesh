import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { NavigationSidebar } from "./NavigationSidebar";
import { LegacyNavigationSidebar } from "./LegacyNavigationSidebar";
import { getTopNavigationItems, bottomNavigationItems } from "./navigation";
import { useConfigContext } from "@/lib/hooks";

interface NavigationSidebarWrapperProps {
    onToggle?: () => void;
    isCollapsed?: boolean;
    onNavigate?: (page: string) => void;
    additionalSystemManagementItems?: Array<{ id: string; label: string; icon?: React.ElementType }>;
    additionalNavItems?: Array<{ id: string; label: string; icon: React.ElementType; position?: "before-agents" | "after-agents" | "after-system-management" }>;
}

/**
 * Navigation Sidebar Wrapper - Conditionally renders new or legacy navigation based on feature flag
 * Feature flag: configFeatureEnablement.newNavigation (default: false for legacy nav)
 */
export const NavigationSidebarWrapper: React.FC<NavigationSidebarWrapperProps> = ({ onToggle, isCollapsed = false, onNavigate, additionalSystemManagementItems, additionalNavItems = [] }) => {
    const { configFeatureEnablement } = useConfigContext();
    const navigate = useNavigate();
    const location = useLocation();

    // Feature flag - default to true (new navigation) if not specified
    const useNewNavigation = configFeatureEnablement?.newNavigation ?? false;

    // Get navigation items using the same function as main branch
    const topNavItems = getTopNavigationItems(configFeatureEnablement);

    // Get active item - matching main branch logic
    const getActiveItem = () => {
        const path = location.pathname;
        if (path === "/" || path.startsWith("/chat")) return "chat";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/prompts")) return "prompts";
        if (path.startsWith("/agents")) return "agentMesh";
        return "chat";
    };

    const handleLegacyItemChange = (itemId: string) => {
        onNavigate?.(itemId);

        // Find the item to check if it has an onClick handler
        const item = topNavItems.find(item => item.id === itemId) || bottomNavigationItems.find(item => item.id === itemId);

        if (item?.onClick && itemId !== "settings") {
            item.onClick();
        } else if (itemId !== "settings") {
            // Navigate using the same logic as main branch
            navigate(`/${itemId === "agentMesh" ? "agents" : itemId}`);
        }
    };

    const handleLegacyHeaderClick = () => {
        navigate("/chat");
    };

    // Render new or legacy navigation based on feature flag
    if (useNewNavigation) {
        return <NavigationSidebar onToggle={onToggle} isCollapsed={isCollapsed} onNavigate={onNavigate} additionalSystemManagementItems={additionalSystemManagementItems} additionalNavItems={additionalNavItems} />;
    }

    // Legacy navigation doesn't support collapse/expand or additional items
    // Use the exact same props as main branch AppLayout
    return <LegacyNavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleLegacyItemChange} onHeaderClick={handleLegacyHeaderClick} />;
};
