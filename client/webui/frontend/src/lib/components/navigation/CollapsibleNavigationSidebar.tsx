import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Plus, ChevronLeft, ChevronRight } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useChatContext, useSessionStorage } from "@/lib/hooks";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { RecentChatsList } from "@/lib/components/chat/RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { cn } from "@/lib/utils";
import type { NavItemConfig, HeaderConfig, NewChatConfig } from "@/lib/types/fe";
import { NavItemButton } from "./NavItemButton";
import { navButtonStyles, iconWrapperStyles, iconStyles, navTextStyles } from "./navigationStyles";
import type { NavItem } from "./types";

/** Wraps children in a Tooltip when collapsed, renders children directly when expanded */
const ConditionalTooltip: React.FC<{ show: boolean; label: string; children: React.ReactElement }> = ({ show, label, children }) => (
    <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        {show && <TooltipContent side="right">{label}</TooltipContent>}
    </Tooltip>
);

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

    const textAnimClass = isCollapsed ? "max-w-0 opacity-0" : "max-w-[180px] opacity-100";
    const textAnimBase = "overflow-hidden whitespace-nowrap transition-[opacity,max-width] duration-200";

    return (
        <nav className={cn("navigation-sidebar flex h-full flex-col overflow-visible border-r bg-(--darkSurface-bg) transition-[width] duration-200 ease-out", isCollapsed ? "w-20" : "w-64")}>
            {/* Header */}
            <div className="relative flex min-h-[80px] w-full items-center border-b border-(--secondary-w70) py-3 pr-4 pl-7">
                <div className="flex items-center gap-2">{renderHeader()}</div>
                {!hideCollapseButton &&
                    (isCollapsed ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <button onClick={handleToggle} className="absolute -right-3 z-30 flex h-6 w-6 cursor-pointer items-center justify-center rounded bg-(--darkSurface-bg) p-0.5 shadow-md hover:bg-(--darkSurface-bgHover)">
                                    <ChevronRight className="size-4 text-(--darkSurface-text)" />
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="right">Expand Navigation</TooltipContent>
                        </Tooltip>
                    ) : (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <button onClick={handleToggle} className="ml-auto flex h-8 w-8 cursor-pointer items-center justify-center p-1 text-(--darkSurface-text) hover:bg-(--darkSurface-bgHover)">
                                    <ChevronLeft className="size-6" />
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="right">Collapse Navigation</TooltipContent>
                        </Tooltip>
                    ))}
            </div>

            {/* Nav items */}
            <div className="flex-shrink-0 py-3">
                {showNewChatButton && (
                    <ConditionalTooltip show={isCollapsed} label={newChatLabel}>
                        <button onClick={handleNewChatClickResolved} className={navButtonStyles()}>
                            <div className={iconWrapperStyles({ active: false, withMargin: true })}>
                                <NewChatIcon className={iconStyles({ active: false })} />
                            </div>
                            <span className={cn(navTextStyles({ active: false }), textAnimBase, textAnimClass)}>{newChatLabel}</span>
                        </button>
                    </ConditionalTooltip>
                )}

                <div>
                    {navItems.map(item => {
                        const hasActiveChild = item.children?.some(child => activeItem === child.id) ?? false;
                        return (
                            <div key={item.id}>
                                <ConditionalTooltip show={isCollapsed} label={item.label}>
                                    <NavItemButton
                                        item={item}
                                        isActive={activeItem === item.id}
                                        isCollapsed={isCollapsed}
                                        onClick={() => {
                                            if (isCollapsed && item.hasSubmenu) {
                                                setActiveItem(item.id);
                                                setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                                                setIsCollapsed(false);
                                            } else {
                                                handleItemClick(item.id, item);
                                            }
                                        }}
                                        isExpanded={expandedMenus[item.id]}
                                        onToggleExpand={() => {
                                            if (isCollapsed && item.hasSubmenu) {
                                                setActiveItem(item.id);
                                                setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                                                setIsCollapsed(false);
                                            } else {
                                                toggleMenu(item.id);
                                            }
                                        }}
                                        hasActiveChild={hasActiveChild}
                                    />
                                </ConditionalTooltip>
                                {!isCollapsed && item.hasSubmenu && expandedMenus[item.id] && item.children && (
                                    <div className="pl-10">
                                        {item.children.map(child => {
                                            const isChildActive = activeItem === child.id;
                                            return (
                                                <div key={child.id} className="group relative">
                                                    <div className={cn("absolute top-0 left-0 h-full bg-(--brand-w60) transition-all", isChildActive ? "w-[3px]" : "w-px opacity-30")} />
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

            {/* Recent Chats */}
            {showRecentChats && (
                <div className={cn("flex min-h-0 flex-col transition-[opacity] duration-200", isCollapsed ? "pointer-events-none h-0 min-h-0 flex-none overflow-hidden opacity-0" : "flex-1 opacity-100")}>
                    <div className="border-t border-(--secondary-w70)" />
                    <div className="mb-2 flex items-center justify-between pt-6 pr-6 pl-6">
                        <span className="text-sm font-bold text-(--secondaryText-wMain)">Recent Chats</span>
                        {/** Hard-code colours to avoid extra variables in the theme for a single usage, may reconsider if there is greater usage */}
                        <Link to="/chat" state={{ openSessionsPanel: true }} className="cursor-pointer text-sm font-bold text-[#679DB4] no-underline hover:text-[#E6EFF2]">
                            View All
                        </Link>
                    </div>
                    <div className="scrollbar-subtle min-h-[120px] flex-1 overflow-y-auto">
                        <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                    </div>
                </div>
            )}

            {/* Bottom items */}
            <div className="relative z-10 mt-auto border-t border-(--secondary-w70) bg-(--darkSurface-bg) py-3">
                {bottomItems.map(item => {
                    const isActive = activeItem === item.id;
                    return (
                        <ConditionalTooltip key={item.id} show={isCollapsed} label={item.label}>
                            <button onClick={() => handleBottomItemClick(item)} className={navButtonStyles()} disabled={item.disabled}>
                                <div className={iconWrapperStyles({ active: isActive, withMargin: true })}>
                                    <item.icon className={iconStyles({ active: isActive })} />
                                </div>
                                <span className={cn(navTextStyles(), textAnimBase, textAnimClass)}>{item.label}</span>
                            </button>
                        </ConditionalTooltip>
                    );
                })}
            </div>
        </nav>
    );
};
