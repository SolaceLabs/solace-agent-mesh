import React, { useState } from "react";
import { Settings, LogOut, User } from "lucide-react";

import { NavigationButton } from "@/lib/components/navigation";
import type { NavigationItem } from "@/lib/types";
import { Popover, PopoverTrigger, PopoverContent, Tooltip, TooltipTrigger, TooltipContent, Menu } from "@/lib/components/ui";
import { SettingsDialog } from "@/lib/components/settings";
import { useAuthContext, useConfigContext } from "@/lib/hooks";

interface NavigationListProps {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
    activeItem: string | null;
    onItemClick: (itemId: string) => void;
}

export const NavigationList: React.FC<NavigationListProps> = ({ items, bottomItems, activeItem, onItemClick }) => {
    const [menuOpen, setMenuOpen] = useState(false);
    const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);

    // When authorization is enabled, show menu with user info and settings/logout
    const { configUseAuthorization, configFeatureEnablement } = useConfigContext();
    const logoutEnabled = configUseAuthorization && configFeatureEnablement?.logout ? true : false;

    const { userInfo, logout } = useAuthContext();
    const userName = typeof userInfo?.username === "string" ? userInfo.username : "Guest";

    const handleSettingsClick = () => {
        setMenuOpen(false);
        setSettingsDialogOpen(true);
    };
    const handleLogoutClick = async () => {
        setMenuOpen(false);
        await logout();
    };

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
                {/* User or Settings */}
                {logoutEnabled ? (
                    <li className="my-4 flex justify-center">
                        <Popover open={menuOpen} onOpenChange={setMenuOpen}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <PopoverTrigger asChild>
                                        <button
                                            type="button"
                                            className="relative mx-auto flex w-full cursor-pointer flex-col items-center bg-[var(--color-primary-w100)] px-3 py-5 text-xs text-[var(--color-primary-text-w10)] transition-colors hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)]"
                                            aria-label="Open Menu"
                                        >
                                            <User className="h-6 w-6" />
                                        </button>
                                    </PopoverTrigger>
                                </TooltipTrigger>
                                <TooltipContent side="right">User & Settings</TooltipContent>
                            </Tooltip>
                            <PopoverContent side="right" align="end" className="w-60 p-0">
                                <div className="flex items-center gap-2 border-b px-3 py-4">
                                    <User className="size-4 shrink-0" />
                                    <div className="min-w-0 truncate text-sm font-medium" title={userName}>
                                        {userName}
                                    </div>
                                </div>
                                <Menu
                                    actions={[
                                        {
                                            id: "settings",
                                            label: "Settings",
                                            icon: <Settings />,
                                            onClick: handleSettingsClick,
                                        },
                                        {
                                            id: "logout",
                                            label: "Log Out",
                                            icon: <LogOut />,
                                            onClick: handleLogoutClick,
                                            divider: true,
                                        },
                                    ]}
                                />
                            </PopoverContent>
                        </Popover>
                    </li>
                ) : (
                    <li className="my-4 flex justify-center">
                        <SettingsDialog iconOnly={true} />
                    </li>
                )}
            </ul>

            {settingsDialogOpen && <SettingsDialog iconOnly={false} open={settingsDialogOpen} onOpenChange={setSettingsDialogOpen} />}
        </nav>
    );
};
