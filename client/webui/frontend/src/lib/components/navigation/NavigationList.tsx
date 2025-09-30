import React from "react";

import { NavigationButton } from "@/lib/components/navigation";
import type { NavigationItem } from "@/lib/types";
import { ToggleThemeButton } from "./ToggleThemeButton";

interface NavigationListProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string | null;
    onItemClick: (itemId: string) => void;
}

export const NavigationList: React.FC<NavigationListProps> = ({ items, bottomItems, activeItem, onItemClick }) => {
    return (
        <nav className="flex flex-1 flex-col" role="navigation" aria-label="Main navigation">
            {/* Main navigation items */}
            <ul className="space-y-1">
                {items.map(item => (
                    <li key={item.id}>
                        <NavigationButton item={item} isActive={activeItem === item.id} onItemClick={onItemClick} />
                        {item.showDividerAfter && <div className="mx-4 my-3 border-t border-[var(--color-secondary-w70)]" />}
                    </li>
                ))}
            </ul>

            {/* Spacer */}
            {bottomItems && bottomItems.length > 0 && <div className="flex-1" />}

            {/* Bottom items */}
            {bottomItems && bottomItems.length > 0 && (
                <ul className="space-y-1">
                    {bottomItems.map(item => (
                        <li key={item.id} className="my-4">
                            {item.id === "theme-toggle" ? <ToggleThemeButton /> : <NavigationButton key={item.id} item={item} isActive={activeItem === item.id} onItemClick={onItemClick} />}
                        </li>
                    ))}
                </ul>
            )}
        </nav>
    );
};
