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

    return (
        <aside className="flex h-screen w-[100px] flex-col border-r border-[var(--color-secondary-w70)] bg-[var(--color-primary-w100)]">
            <NavigationHeader onClick={onHeaderClick} />
            <NavigationList items={items} bottomItems={bottomItems} activeItem={activeItem} onItemClick={handleItemClick} />
        </aside>
    );
};
