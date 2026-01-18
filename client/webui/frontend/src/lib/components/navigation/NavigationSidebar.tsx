import React from "react";

import { NavigationHeader, NavigationList } from "@/lib/components/navigation";
import type { NavigationItem } from "@/lib/types";

interface NavigationSidebarProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string;
    onItemChange: (itemId: string) => void;
    onHeaderClick?: () => void;
}

export const NavigationSidebar: React.FC<NavigationSidebarProps> = ({ items, bottomItems, activeItem, onItemChange, onHeaderClick }) => {
    const handleItemClick = (itemId: string) => {
        onItemChange(itemId);
    };

    // Filter out theme-toggle from bottomItems
    const filteredBottomItems = bottomItems?.filter(item => item.id !== "theme-toggle");

    return (
        <nav className="h-[80px] w-full border-b border-[var(--color-secondary-w40)] bg-[var(--color-background-w10)] px-8">
            <div className="max-w-5xl h-full w-full mx-auto flex flex-row justify-between">
                <div className="flex items-center" onClick={onHeaderClick}>
                    <NavigationHeader onClick={onHeaderClick} />
                </div>
                <div className="flex items-center">
                    <NavigationList items={items} bottomItems={filteredBottomItems} activeItem={activeItem} onItemClick={handleItemClick} />
                </div>
            </div>
        </nav>
    );
};
