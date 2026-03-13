import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Plus, ChevronLeft, ChevronRight } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useChatContext, useSessionStorage } from "@/lib/hooks";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { RecentChatsList } from "@/lib/components/chat/RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { cn } from "@/lib/utils";
import type { NavItemConfig, HeaderConfig, NewChatConfig } from "@/lib/types/fe";
import { NavItemButton } from "./NavItemButton";
import { navButtonStyles, iconWrapperStyles, iconStyles, navTextStyles } from "./navigationStyles";
import type { NavItem } from "./types";

export interface CollapsibleNavigationSidebarProps {
    /**
     * Navigation items to display. Items are rendered as-is with no filtering.
     * Use `position: "bottom"` to place items in the bottom section.
     * Items should include onClick handlers or routes pre-configured.
     */
    items: NavItemConfig[];

    header?: HeaderConfig | React.ReactNode;

    showNewChatButton?: boolean;
    newChatConfig?: NewChatConfig;
    showRecentChats?: boolean;

    // Callbacks
    onNavigate?: (itemId: string, route?: string) => void;
    onCollapseChange?: (isCollapsed: boolean) => void;

    /**
     * Controls which item appears active. When provided, disables automatic
     * route-based detection. Parent should compute this from location.pathname.
     */
    activeItemId?: string;
    isCollapsed?: boolean;
    defaultCollapsed?: boolean;
}

export const CollapsibleNavigationSidebar: React.FC<CollapsibleNavigationSidebarProps> = ({
    items,
    header,
    showNewChatButton = true,
    newChatConfig,
    showRecentChats = true,
    onNavigate,
    onCollapseChange,
    activeItemId: controlledActiveItemId,
    isCollapsed: controlledIsCollapsed,
    defaultCollapsed = false,
}) => {
    const navigate = useNavigate();
    const location = useLocation();

    const [internalCollapsed, setInternalCollapsed] = useSessionStorage("nav-collapsed", defaultCollapsed);
    const isCollapsed = controlledIsCollapsed ?? internalCollapsed;
    const setIsCollapsed = (value: boolean) => {
        setInternalCollapsed(value);
        onCollapseChange?.(value);
    };

    const [internalActiveItem, setInternalActiveItem] = useState<string>("");
    const activeItem = controlledActiveItemId ?? internalActiveItem;
    const setActiveItem = (value: string) => {
        if (controlledActiveItemId === undefined) {
            setInternalActiveItem(value);
        }
    };

    const [expandedMenus, setExpandedMenus] = useState<Record<string, boolean>>(() => {
        const initial: Record<string, boolean> = { assets: false, systemManagement: false };
        items.forEach(item => {
            if (item.children && item.defaultExpanded !== undefined) {
                initial[item.id] = item.defaultExpanded;
            }
        });
        return initial;
    });
    const { handleNewSession } = useChatContext();

    const isItemActiveByRoute = useCallback(
        (item: NavItemConfig): boolean => {
            if (!item.routeMatch) return false;

            const patterns = Array.isArray(item.routeMatch) ? item.routeMatch : [item.routeMatch];
            return patterns.some(pattern => {
                if (pattern instanceof RegExp) return pattern.test(location.pathname);
                return location.pathname.startsWith(pattern);
            });
        },
        [location.pathname]
    );

    const findActiveItemId = useCallback(
        (items: NavItemConfig[]): string | null => {
            for (const item of items) {
                if (isItemActiveByRoute(item)) return item.id;
                if (item.children) {
                    const childMatch = item.children.find(child => isItemActiveByRoute(child));
                    if (childMatch) return childMatch.id;
                }
            }
            return null;
        },
        [isItemActiveByRoute]
    );

    useEffect(() => {
        // Only run auto-detection if NOT controlled
        if (controlledActiveItemId !== undefined) return;

        const matchedId = findActiveItemId(items);
        if (matchedId) {
            setInternalActiveItem(matchedId);
            // Auto-expand parent menus
            items.forEach(item => {
                if (item.children?.some(child => child.id === matchedId)) {
                    setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                }
            });
        } else {
            setInternalActiveItem("");
        }
    }, [location.pathname, items, controlledActiveItemId, findActiveItemId]);

    const handleItemClick = (itemId: string, item: NavItem) => {
        setActiveItem(itemId);

        if (item.onClick) {
            item.onClick();
            return;
        }

        onNavigate?.(itemId, item.route);

        if (item.route) {
            navigate(item.route);
        }
    };

    const toggleMenu = (menuId: string) => {
        setExpandedMenus(prev => ({
            ...prev,
            [menuId]: !prev[menuId],
        }));
    };

    const handleToggle = () => {
        setIsCollapsed(!isCollapsed);
    };

    const toNavItem = useCallback((config: NavItemConfig): NavItem => {
        const convertItem = (item: NavItemConfig): NavItem => ({
            ...item,
            hasSubmenu: !!item.children?.length,
            children: item.children?.map(convertItem),
        });
        return convertItem(config);
    }, []);

    const navItems: NavItem[] = useMemo(() => items.filter(item => item.position !== "bottom").map(toNavItem), [items, toNavItem]);
    const bottomItems: NavItem[] = useMemo(() => items.filter(item => item.position === "bottom").map(toNavItem), [items, toNavItem]);

    const handleNewChatClickResolved = useCallback(() => {
        if (newChatConfig?.onClick) {
            newChatConfig.onClick();
            return;
        }
        navigate("/chat");
        handleNewSession();
    }, [newChatConfig, navigate, handleNewSession]);

    const newChatLabel = newChatConfig?.label ?? "New Chat";
    const NewChatIcon = newChatConfig?.icon ?? Plus;

    const renderHeader = (): React.ReactNode => {
        if (header && typeof header === "object" && header !== null && "component" in header) {
            const headerConfig = header as HeaderConfig;
            if (headerConfig.component) return headerConfig.component;
        } else if (header !== undefined && header !== null) {
            return header as React.ReactNode;
        }
        return <SolaceIcon variant={isCollapsed ? "short" : "full"} className={isCollapsed ? "h-8 w-8" : "h-8 w-24"} />;
    };

    const hideCollapseButton = header && typeof header === "object" && "hideCollapseButton" in header && (header as HeaderConfig).hideCollapseButton;

    const handleBottomItemClick = (item: NavItem) => {
        item.onClick?.();
    };

    const isNavItemOrChildActive = (item: NavItem): boolean => {
        if (activeItem === item.id) return true;
        if (item.children?.some(child => activeItem === child.id)) return true;
        return false;
    };

    return (
        <aside className={cn("navigation-sidebar flex h-full flex-col overflow-visible border-r bg-(--darkSurface-bg)", isCollapsed ? "w-16" : "w-64")}>
            {isCollapsed ? (
                <>
                    <div className="relative flex min-h-[80px] w-full items-center justify-center overflow-visible border-b border-(--secondary-w70) py-3">
                        {renderHeader()}
                        {/* Positioned outside panel bounds to create floating expand button effect */}
                        {!hideCollapseButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button onClick={handleToggle} className="absolute -right-3 z-10 flex h-6 w-6 cursor-pointer items-center justify-center rounded bg-(--darkSurface-bg) p-0.5 shadow-md hover:bg-(--darkSurface-bgHover)">
                                        <ChevronRight className="size-4 text-(--darkSurface-text)" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Expand Navigation</TooltipContent>
                            </Tooltip>
                        )}
                    </div>

                    <div className="flex flex-col items-center py-3">
                        {showNewChatButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button onClick={handleNewChatClickResolved} className={navButtonStyles({ variant: "collapsed" })}>
                                        <div className={iconWrapperStyles({ active: false })}>
                                            <NewChatIcon className={iconStyles({ active: false })} />
                                        </div>
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">{newChatLabel}</TooltipContent>
                            </Tooltip>
                        )}

                        {navItems.map(item => {
                            const isActive = isNavItemOrChildActive(item);
                            const hasSubmenu = item.hasSubmenu && item.children?.length;

                            return (
                                <Tooltip key={item.id}>
                                    <TooltipTrigger asChild>
                                        <button
                                            onClick={() => {
                                                if (hasSubmenu) {
                                                    setActiveItem(item.id);
                                                    setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                                                    setIsCollapsed(false);
                                                } else {
                                                    handleItemClick(item.id, item);
                                                }
                                            }}
                                            className={navButtonStyles({ variant: "collapsed" })}
                                            disabled={item.disabled}
                                        >
                                            <div className={iconWrapperStyles({ active: isActive })}>
                                                <item.icon className={iconStyles({ active: isActive })} />
                                            </div>
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent side="right">{item.label}</TooltipContent>
                                </Tooltip>
                            );
                        })}
                    </div>

                    <div className="mt-auto flex flex-col items-center gap-2 border-t border-(--secondary-w70) py-3">
                        {bottomItems.map(item => {
                            const isActive = activeItem === item.id;
                            return (
                                <Tooltip key={item.id}>
                                    <TooltipTrigger asChild>
                                        <button onClick={() => handleBottomItemClick(item)} className={navButtonStyles({ variant: "collapsed" })} disabled={item.disabled}>
                                            <div className={iconWrapperStyles({ active: isActive })}>
                                                <item.icon className={iconStyles({ active: isActive })} />
                                            </div>
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent side="right">{item.label}</TooltipContent>
                                </Tooltip>
                            );
                        })}
                    </div>
                </>
            ) : (
                <>
                    <div className="flex min-h-[80px] items-center justify-between border-b border-(--secondary-w70) py-3 pr-4 pl-6">
                        <div className="flex items-center gap-2">{renderHeader()}</div>
                        {!hideCollapseButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button onClick={handleToggle} className="flex h-8 w-8 cursor-pointer items-center justify-center p-1 text-(--darkSurface-text) hover:bg-(--darkSurface-bgHover)">
                                        <ChevronLeft className="size-6" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Collapse Navigation</TooltipContent>
                            </Tooltip>
                        )}
                    </div>

                    <div className="flex-shrink-0 py-3">
                        {showNewChatButton && (
                            <button onClick={handleNewChatClickResolved} className={navButtonStyles()}>
                                <div className={iconWrapperStyles({ active: false, withMargin: true })}>
                                    <NewChatIcon className={iconStyles({ active: false })} />
                                </div>
                                <span className={navTextStyles({ active: false })}>{newChatLabel}</span>
                            </button>
                        )}

                        <div>
                            {navItems.map(item => {
                                const hasActiveChild = item.children?.some(child => activeItem === child.id) ?? false;
                                return (
                                    <div key={item.id}>
                                        <NavItemButton
                                            item={item}
                                            isActive={activeItem === item.id}
                                            onClick={() => handleItemClick(item.id, item)}
                                            isExpanded={expandedMenus[item.id]}
                                            onToggleExpand={() => toggleMenu(item.id)}
                                            hasActiveChild={hasActiveChild}
                                        />
                                        {item.hasSubmenu && expandedMenus[item.id] && item.children && (
                                            <div className="ml-10">
                                                {item.children.map(child => {
                                                    const isChildActive = activeItem === child.id;
                                                    return (
                                                        <div key={child.id} className="group relative">
                                                            <div className={cn("absolute top-0 left-0 h-full bg-(--brand-w60) transition-all", isChildActive ? "w-[3px]" : "w-px opacity-30 group-hover:w-[3px] group-hover:opacity-100")} />
                                                            <NavItemButton item={child} isActive={isChildActive} onClick={() => handleItemClick(child.id, child)} indent />
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {showRecentChats && (
                        <div className="flex min-h-0 flex-1 flex-col">
                            <div className="border-t border-(--secondary-w70)" />
                            <div className="mb-2 flex items-center justify-between pt-4 pr-6 pl-6">
                                <span className="text-sm font-bold text-(--darkSurface-textMuted)">Recent Chats</span>
                                <Button onClick={() => navigate("/chat", { state: { openSessionsPanel: true } })} variant="ghost" className="px-2">
                                    View All
                                </Button>
                            </div>
                            <div className="scrollbar-subtle min-h-[120px] flex-1 overflow-y-auto">
                                <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                            </div>
                        </div>
                    )}

                    <div className="relative z-10 border-t border-(--secondary-w70) bg-(--background-wMain) pt-2">
                        {bottomItems.map(item => (
                            <button key={item.id} onClick={() => handleBottomItemClick(item)} className={navButtonStyles()} disabled={item.disabled}>
                                <div className={iconWrapperStyles({ withMargin: true })}>
                                    <item.icon className={iconStyles()} />
                                </div>
                                <span className={navTextStyles()}>{item.label}</span>
                            </button>
                        ))}
                    </div>
                </>
            )}
        </aside>
    );
};
