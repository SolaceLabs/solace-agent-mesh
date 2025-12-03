import React from "react";

import { NavigationButton } from "@/lib/components/navigation";
import { UserMenu } from "@/lib/components/navigation/UserMenu";
import { useConfigContext } from "@/lib/hooks";
import type { NavigationItem } from "@/lib/types";

interface NavigationListProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string | null;
    onItemClick: (itemId: string) => void;
}

// Wrapper component to inject user info from config
const UserMenuWithConfig: React.FC<{ onUsageClick: () => void }> = ({ onUsageClick }) => {
    const { user } = useConfigContext();

    return <UserMenu userName={user?.name || "Username not found"} userEmail={user?.email || "Email not found"} onUsageClick={onUsageClick} />;
};

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
            <div className="flex-1" />

            {/* Bottom items */}
            <ul className="space-y-1">
                {bottomItems &&
                    bottomItems.length > 0 &&
                    bottomItems.map(item => (
                        <li key={item.id} className="my-4">
                            <NavigationButton key={item.id} item={item} isActive={activeItem === item.id} onItemClick={onItemClick} />
                        </li>
                    ))}
                {/* User Menu with Settings and Token Usage */}
                <li className="my-4 flex justify-center">
                    <UserMenuWithConfig onUsageClick={() => onItemClick("usage")} />
                </li>
            </ul>
        </nav>
    );
};
