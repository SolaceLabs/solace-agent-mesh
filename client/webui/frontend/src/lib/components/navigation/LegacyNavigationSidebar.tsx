import React from "react";

import { NavigationHeader } from "@/lib/components/navigation";
import { LegacyNavigationList } from "@/lib/components/navigation/LegacyNavigationList";
import type { NavigationItem } from "@/lib/types";

interface LegacyNavigationSidebarProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string;
    onItemChange: (itemId: string) => void;
    onHeaderClick?: () => void;
}

/**
 * Legacy Navigation Sidebar - Original simple navigation from main branch
 * This is the old navigation that was used before the new collapsible sidebar
 */
export const LegacyNavigationSidebar: React.FC<LegacyNavigationSidebarProps> = ({ items, bottomItems, activeItem, onItemChange, onHeaderClick }) => {
    const handleItemClick = (itemId: string) => {
        onItemChange(itemId);
    };

    // Filter out theme-toggle from bottomItems
    const filteredBottomItems = bottomItems?.filter(item => item.id !== "theme-toggle");

    return (
        <aside className="flex h-screen w-[100px] flex-col overflow-y-auto border-r border-[var(--color-secondary-w70)] bg-[var(--color-primary-w100)]">
            <NavigationHeader onClick={onHeaderClick} />
            <LegacyNavigationList items={items} bottomItems={filteredBottomItems} activeItem={activeItem} onItemClick={handleItemClick} />
        </aside>
    );
};
