import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { cva } from "class-variance-authority";
import { Plus, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useChatContext, useSessionStorage } from "@/lib/hooks";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { RecentChatsList } from "@/lib/components/chat/RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { cn } from "@/lib/utils";

const HOVER_BG = "hover:bg-[var(--color-background-w100)]";
const ACTIVE_BG = "bg-[var(--color-background-w100)]";

const navButtonStyles = cva(["flex", "h-10", "cursor-pointer", "items-center", "transition-colors", "py-6", "w-full", HOVER_BG], {
    variants: {
        variant: {
            expanded: "justify-start pr-4 pl-6 text-sm font-normal",
            collapsed: "justify-center p-0",
            bottom: "justify-center p-2 text-[var(--color-primary-text-w10)]",
        },
        active: {
            true: ACTIVE_BG,
            false: "",
        },
        indent: {
            true: "pl-4",
            false: "",
        },
    },
    defaultVariants: { variant: "expanded", active: false, indent: false },
});

const iconWrapperStyles = cva(["flex", "size-8", "items-center", "justify-center", "rounded"], {
    variants: {
        active: {
            true: `border border-[var(--color-brand-w60)] ${ACTIVE_BG}`,
            false: "",
        },
        withMargin: {
            true: "mr-2",
            false: "",
        },
    },
    defaultVariants: { active: false, withMargin: false },
});

const iconStyles = cva(["size-6"], {
    variants: {
        active: {
            true: "text-[var(--color-brand-w60)]",
            false: "text-[var(--color-secondary-text-w50)]",
        },
        muted: {
            true: "text-[var(--color-primary-text-w10)]",
            false: "",
        },
    },
    defaultVariants: { active: false, muted: false },
});

const navTextStyles = cva([], {
    variants: {
        active: {
            true: "font-bold text-white",
            false: "text-[var(--color-secondary-text-w50)]",
        },
    },
    defaultVariants: { active: false },
});

/**
 * Configuration for a single navigation item.
 *
 * This interface is used by external repos (e.g., solace-chat) to define
 * custom navigation structures. All properties support the presentational
 * component pattern where business logic is injected via callbacks.
 *
 * @example
 * ```tsx
 * const myNavItem: NavItemConfig = {
 *   id: "settings",
 *   label: "Settings",
 *   icon: SettingsIcon,
 *   onClick: () => openSettingsDialog(),
 *   badge: <LifecycleBadge>BETA</LifecycleBadge>,
 * };
 * ```
 */
export interface NavItemConfig {
    /** Unique identifier for this item, used for active state tracking and event handling */
    id: string;

    /** Display text shown next to the icon in expanded mode */
    label: string;

    /** Lucide icon component or any React component that accepts className prop */
    icon: React.ElementType;

    /**
     * Route path to navigate to when clicked (e.g., "/agents").
     * Ignored if `onClick` is provided.
     */
    route?: string;

    /**
     * Pattern(s) to determine active state based on current URL.
     * Supports string prefix matching, array of prefixes, or RegExp.
     * @example "/projects" matches "/projects" and "/projects/123"
     * @example ["/chat", "/conversations"] matches either prefix
     * @example /^\/users\/\d+$/ matches "/users/123" but not "/users"
     */
    routeMatch?: string | string[] | RegExp;

    /**
     * Custom click handler that overrides default routing behavior.
     * Use for items that open dialogs, trigger actions, or need custom logic.
     */
    onClick?: () => void;

    /**
     * Optional badge component rendered after the label.
     * Accepts any React node for full flexibility (e.g., LifecycleBadge, custom pill).
     * @example badge: <LifecycleBadge>EXPERIMENTAL</LifecycleBadge>
     */
    badge?: React.ReactNode;

    /** Tooltip text shown on hover (both collapsed and expanded modes) */
    tooltip?: string;

    /** When true, item is rendered but non-interactive */
    disabled?: boolean;

    /** When true, item is completely hidden from the navigation */
    hidden?: boolean;

    /**
     * Child items that create an expandable submenu.
     * Parent item becomes a toggle button; clicking expands/collapses children.
     */
    children?: NavItemConfig[];

    /** When true, submenu starts in expanded state on initial render */
    defaultExpanded?: boolean;

    /**
     * Determines whether item renders in the main nav area or bottom section.
     * Bottom items typically include user account, settings, and logout.
     * @default "top"
     */
    position?: "top" | "bottom";
}

/** Header configuration */
export interface HeaderConfig {
    /** Custom component to render instead of SolaceIcon (full override) */
    component?: React.ReactNode;
    /** Hide collapse/expand button */
    hideCollapseButton?: boolean;
}

/** New Chat button configuration */
export interface NewChatConfig {
    label?: string;
    icon?: React.ElementType;
    onClick?: () => void;
}

type NavItem = NavItemConfig & { hasSubmenu?: boolean };

const NavItemButton: React.FC<{
    item: NavItem;
    isActive: boolean;
    onClick: () => void;
    isExpanded?: boolean;
    onToggleExpand?: () => void;
    className?: string;
    indent?: boolean;
    hasActiveChild?: boolean;
}> = ({ item, isActive, onClick, isExpanded, onToggleExpand, className, indent, hasActiveChild }) => {
    const isHighlighted = isActive || hasActiveChild;
    const buttonContent = (
        <button onClick={item.hasSubmenu ? onToggleExpand : onClick} className={cn(navButtonStyles({ indent: !!indent, active: !!indent && isActive }), className)}>
            {indent ? (
                <span className={navTextStyles({ active: isActive })}>{item.label}</span>
            ) : (
                <>
                    <div className={iconWrapperStyles({ active: isHighlighted, withMargin: true })}>
                        <item.icon className={iconStyles({ active: isHighlighted })} />
                    </div>
                    <span className={navTextStyles({ active: isHighlighted })}>{item.label}</span>
                </>
            )}
            {item.hasSubmenu && <span className="ml-auto text-[var(--color-primary-text-w10)]">{isExpanded ? <ChevronUp className="size-6" /> : <ChevronDown className="size-6" />}</span>}
            {item.badge}
        </button>
    );

    if (item.tooltip) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
                <TooltipContent side="right">
                    <p>{item.tooltip}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

    return buttonContent;
};

export interface CollapsibleNavigationSidebarProps {
    items: NavItemConfig[];

    header?: HeaderConfig | React.ReactNode;

    showNewChatButton?: boolean;
    newChatConfig?: NewChatConfig;
    showRecentChats?: boolean;

    // Callbacks
    onNavigate?: (itemId: string, route?: string) => void;
    onCollapseChange?: (isCollapsed: boolean) => void;

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

    const [internalActiveItem, setInternalActiveItem] = useState<string>("chats");
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
        if (controlledActiveItemId !== undefined) return;

        const matchedId = findActiveItemId(items);
        if (matchedId) {
            setInternalActiveItem(matchedId);
            items.forEach(item => {
                if (item.children?.some(child => child.id === matchedId)) {
                    setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                }
            });
        } else {
            setInternalActiveItem("chats");
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

    const navItems: NavItem[] = useMemo(() => items.filter(item => !item.hidden && item.position !== "bottom").map(toNavItem), [items, toNavItem]);
    const bottomItems: NavItem[] = useMemo(() => items.filter(item => !item.hidden && item.position === "bottom").map(toNavItem), [items, toNavItem]);

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
        <aside className={cn("navigation-sidebar flex h-full flex-col overflow-visible border-r bg-[var(--color-background-wMain)]", isCollapsed ? "w-16" : "w-64")}>
            {isCollapsed ? (
                <>
                    <div className="relative flex w-full items-center justify-center overflow-visible border-b border-[var(--color-secondary-w70)] py-3">
                        {renderHeader()}
                        {/* Positioned outside panel bounds to create floating expand button effect */}
                        {!hideCollapseButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        onClick={handleToggle}
                                        className="absolute -right-3 z-10 flex h-6 w-6 cursor-pointer items-center justify-center rounded bg-[var(--color-background-wMain)] p-0.5 shadow-md hover:bg-[var(--color-background-w100)]"
                                    >
                                        <ChevronRight className="size-4 text-[var(--color-primary-text-w10)]" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Expand Navigation</TooltipContent>
                            </Tooltip>
                        )}
                    </div>

                    <div className="flex flex-col items-center gap-2 py-3">
                        {showNewChatButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button onClick={handleNewChatClickResolved} className={navButtonStyles({ variant: "collapsed" })}>
                                        <div className={iconWrapperStyles({ active: activeItem === "chats" })}>
                                            <NewChatIcon className={iconStyles({ active: activeItem === "chats" })} />
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

                    <div className="mt-auto flex flex-col items-center gap-2 border-t border-[var(--color-secondary-w70)] p-2">
                        {bottomItems.map(item => (
                            <Tooltip key={item.id}>
                                <TooltipTrigger asChild>
                                    <button onClick={() => handleBottomItemClick(item)} className={navButtonStyles({ variant: "bottom" })} disabled={item.disabled}>
                                        <item.icon className="size-6" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">{item.label}</TooltipContent>
                            </Tooltip>
                        ))}
                    </div>
                </>
            ) : (
                <>
                    <div className="flex items-center justify-between border-b border-[var(--color-secondary-w70)] py-3 pr-4 pl-6">
                        <div className="flex items-center gap-2">{renderHeader()}</div>
                        {!hideCollapseButton && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button onClick={handleToggle} className="flex h-8 w-8 cursor-pointer items-center justify-center p-1 text-[var(--color-primary-text-w10)] hover:bg-[var(--color-background-w100)]">
                                        <ChevronLeft className="size-6" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Collapse Navigation</TooltipContent>
                            </Tooltip>
                        )}
                    </div>

                    <div className="flex-1 overflow-y-auto py-3">
                        {showNewChatButton && (
                            <button onClick={handleNewChatClickResolved} className={navButtonStyles()}>
                                <div className={iconWrapperStyles({ active: activeItem === "chats", withMargin: true })}>
                                    <NewChatIcon className={iconStyles({ active: activeItem === "chats" })} />
                                </div>
                                <span className={navTextStyles({ active: activeItem === "chats" })}>{newChatLabel}</span>
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
                                                            <div className={cn("absolute top-0 left-0 h-full bg-[var(--color-brand-w60)] transition-all", isChildActive ? "w-[3px]" : "w-px opacity-30 group-hover:w-[3px] group-hover:opacity-100")} />
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

                        {showRecentChats && (
                            <>
                                <div className="my-4 border-t border-[var(--color-secondary-w70)]" />
                                <div className="mb-2 flex items-center justify-between pr-4 pl-6">
                                    <span className="text-sm font-bold text-[var(--color-secondary-text-wMain)]">Recent Chats</span>
                                    <button onClick={() => navigate("/chat", { state: { openSessionsPanel: true } })} className="cursor-pointer text-sm font-normal text-[var(--color-primary-w60)] hover:text-[var(--color-primary-text-w10)]">
                                        View All
                                    </button>
                                </div>
                                <div className="flex-1">
                                    <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                                </div>
                            </>
                        )}
                    </div>

                    <div className="mt-2 border-t border-[var(--color-secondary-w70)] pt-2">
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
