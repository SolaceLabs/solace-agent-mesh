import React from "react";

import { SunMoon } from "lucide-react";

import { NavigationButton } from "@/lib/components/navigation";
import { useThemeContext } from "@/lib/hooks/useThemeContext";
import type { NavigationItem } from "@/lib/types";

interface NavigationListProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string | null;
    onItemClick: (itemId: string) => void;
}

export const NavigationList: React.FC<NavigationListProps> = ({ items, bottomItems, activeItem, onItemClick }) => {
    const { currentTheme, toggleTheme } = useThemeContext();

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
                            {item.id === "theme-toggle" ? (
                                <button
                                    type="button"
                                    disabled={item.disabled}
                                    onClick={toggleTheme}
                                    className="relative mx-auto flex w-full cursor-pointer flex-col items-center bg-[var(--color-primary-w100)] px-3 py-5 text-xs text-[var(--color-primary-text-w10)] transition-colors hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)] disabled:cursor-not-allowed disabled:opacity-50"
                                    aria-label={`Toggle theme (currently ${currentTheme})`}
                                    title={`Toggle theme (currently ${currentTheme})`}
                                >
                                    <SunMoon className="mb-1 h-6 w-6" />
                                </button>
                            ) : (
                                <NavigationButton key={item.id} item={item} isActive={activeItem === item.id} onItemClick={onItemClick} />
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </nav>
    );
};
