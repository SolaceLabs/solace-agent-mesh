import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { cva } from "class-variance-authority";
import { Plus, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger, LifecycleBadge } from "@/lib/components/ui";
import { useChatContext, useSessionStorage } from "@/lib/hooks";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { RecentChatsList } from "@/lib/components/chat/RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { cn } from "@/lib/utils";

// ============================================================================
// CVA Style Definitions
// ============================================================================

// Shared color constants - matches RecentChatsList hover styling
const HOVER_BG = "enabled:hover:bg-[var(--color-background-w100)]";
const ACTIVE_BG = "bg-[var(--color-background-w100)]";

/** Unified navigation button styles with variant support */
const navButtonStyles = cva(["h-10", "transition-colors", HOVER_BG], {
    variants: {
        variant: {
            expanded: "w-full justify-start pr-4 pl-6 text-sm font-normal",
            collapsed: "w-10 p-0",
            bottom: "w-10 p-2 text-[var(--color-primary-text-w10)]",
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

/** Icon wrapper container styles */
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

/** Icon element styles */
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

/** Navigation text styles */
const navTextStyles = cva([], {
    variants: {
        active: {
            true: "font-bold text-white",
            false: "text-[var(--color-secondary-text-w50)]",
        },
    },
    defaultVariants: { active: false },
});

// ============================================================================
// Public Types - exported for external consumers
// ============================================================================

/** Single navigation item configuration */
export interface NavItemConfig {
    id: string;
    label: string;
    icon: React.ElementType;

    // Routing
    route?: string; // Route to navigate to (e.g., "/agents")
    routeMatch?: string | string[] | RegExp; // Pattern(s) to match for active state
    onClick?: () => void; // Custom click handler (overrides routing)

    // Visual
    badge?: string; // Badge text (e.g., "Beta") - for custom badges
    lifecycle?: "experimental" | "beta"; // Lifecycle badge (uses LifecycleBadge component)
    tooltip?: string; // Tooltip text
    disabled?: boolean; // Disable the item
    hidden?: boolean; // Hide the item

    // Submenu
    children?: NavItemConfig[]; // Sub-items (creates expandable submenu)
    defaultExpanded?: boolean; // Start with submenu expanded

    // Position
    position?: "top" | "bottom"; // Where to render the item (default: "top")
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

// Internal type alias for backward compatibility
type NavItem = NavItemConfig & { hasSubmenu?: boolean };

// Navigation item button component - uses dark theme colors always
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
        <Button variant="ghost" onClick={item.hasSubmenu ? onToggleExpand : onClick} className={cn(navButtonStyles({ indent: !!indent, active: !!indent && isActive }), className)}>
            {indent ? (
                // Subitem - no icon wrapper, just text
                <span className={navTextStyles({ active: isActive })}>{item.label}</span>
            ) : (
                // Main item - with icon wrapper
                <>
                    <div className={iconWrapperStyles({ active: isHighlighted, withMargin: true })}>
                        <item.icon className={iconStyles({ active: isHighlighted })} />
                    </div>
                    <span className={navTextStyles({ active: isHighlighted })}>{item.label}</span>
                </>
            )}
            {item.hasSubmenu && <span className="ml-auto text-[var(--color-primary-text-w10)]">{isExpanded ? <ChevronUp className="size-6" /> : <ChevronDown className="size-6" />}</span>}
            {item.lifecycle && <LifecycleBadge className="scale-90 border-[var(--color-secondary-text-w50)] text-[var(--color-secondary-text-w50)]">{item.lifecycle === "beta" ? "BETA" : "EXPERIMENTAL"}</LifecycleBadge>}
            {item.badge && !item.lifecycle && <span className="ml-auto rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-600">{item.badge}</span>}
        </Button>
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
    // Navigation items - REQUIRED, single prop with position indicator
    items: NavItemConfig[]; // All navigation items (position determines top vs bottom)

    // Header
    header?: HeaderConfig | React.ReactNode;

    // Special sections
    showNewChatButton?: boolean; // Show/hide "New Chat" button (default: true)
    newChatConfig?: NewChatConfig; // Customize "New Chat" button
    showRecentChats?: boolean; // Show/hide Recent Chats section (default: true)

    // Callbacks
    onNavigate?: (itemId: string, route?: string) => void;
    onCollapseChange?: (isCollapsed: boolean) => void;

    // State control (for controlled component pattern)
    activeItemId?: string; // Controlled active state
    isCollapsed?: boolean; // Controlled collapse state
    defaultCollapsed?: boolean; // Uncontrolled default collapse
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

    // Persist collapse state - supports controlled and uncontrolled modes
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
        // Initialize expanded state from items defaultExpanded
        const initial: Record<string, boolean> = { assets: false, systemManagement: false };
        items.forEach(item => {
            if (item.children && item.defaultExpanded !== undefined) {
                initial[item.id] = item.defaultExpanded;
            }
        });
        return initial;
    });
    const { handleNewSession } = useChatContext();

    // Helper to check if an item matches the current route
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

    // Find active item ID from resolved nav items
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

    // Sync active item with current route (only in uncontrolled mode)
    useEffect(() => {
        if (controlledActiveItemId !== undefined) return; // Controlled mode - don't sync

        // Use routeMatch-based detection from items
        const matchedId = findActiveItemId(items);
        if (matchedId) {
            setInternalActiveItem(matchedId);
            // Auto-expand parent menu if child is active
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

        // Call onNavigate callback with both itemId and route
        onNavigate?.(itemId, item.route);

        // If item has a route defined, use it
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

    // Convert NavItemConfig to internal NavItem format (adds hasSubmenu flag)
    const toNavItem = useCallback((config: NavItemConfig): NavItem => {
        const convertItem = (item: NavItemConfig): NavItem => ({
            ...item,
            hasSubmenu: !!item.children?.length,
            children: item.children?.map(convertItem),
        });
        return convertItem(config);
    }, []);

    // Split items by position - top items (default) and bottom items
    const navItems: NavItem[] = useMemo(() => items.filter(item => !item.hidden && item.position !== "bottom").map(toNavItem), [items, toNavItem]);

    const bottomItems: NavItem[] = useMemo(() => items.filter(item => !item.hidden && item.position === "bottom").map(toNavItem), [items, toNavItem]);

    // Handle new chat click - uses custom config if provided
    const handleNewChatClickResolved = useCallback(() => {
        if (newChatConfig?.onClick) {
            newChatConfig.onClick();
            return;
        }
        // Default behavior
        navigate("/chat");
        handleNewSession();
    }, [newChatConfig, navigate, handleNewSession]);

    // Resolve new chat button props
    const newChatLabel = newChatConfig?.label ?? "New Chat";
    const NewChatIcon = newChatConfig?.icon ?? Plus;

    // Helper to render header content
    const renderHeader = (): React.ReactNode => {
        // Check if header is a HeaderConfig object
        if (header && typeof header === "object" && header !== null && "component" in header) {
            const headerConfig = header as HeaderConfig;
            if (headerConfig.component) return headerConfig.component;
            // HeaderConfig without component - use default SolaceIcon
        } else if (header !== undefined && header !== null) {
            // header is a React.ReactNode (not HeaderConfig)
            return header as React.ReactNode;
        }

        // Default: SolaceIcon with appropriate variant based on collapsed state
        return <SolaceIcon variant={isCollapsed ? "short" : "full"} className={isCollapsed ? "h-8 w-8" : "h-8 w-24"} />;
    };

    // Check if collapse button should be hidden
    const hideCollapseButton = header && typeof header === "object" && "hideCollapseButton" in header && (header as HeaderConfig).hideCollapseButton;

    // Handle bottom item click - delegates to item's onClick handler
    const handleBottomItemClick = (item: NavItem) => {
        item.onClick?.();
    };

    // Check if a nav item or its children is active (for collapsed view icon highlighting)
    const isNavItemOrChildActive = (item: NavItem): boolean => {
        if (activeItem === item.id) return true;
        if (item.children?.some(child => activeItem === child.id)) return true;
        return false;
    };

    return (
        <aside className={cn("navigation-sidebar flex h-full flex-col overflow-visible border-r bg-[var(--color-background-wMain)]", isCollapsed ? "w-16" : "w-64")}>
            {isCollapsed ? (
                /* Collapsed View - Icon Only */
                <>
                    {/* Header with Short Logo */}
                    <div className="relative flex w-full items-center justify-center overflow-visible border-b border-[var(--color-secondary-w70)] py-3">
                        {renderHeader()}
                        {/* Expand Chevron - positioned outside the panel */}
                        {!hideCollapseButton && (
                            <Button
                                variant="ghost"
                                onClick={handleToggle}
                                className="absolute -right-3 z-10 h-6 w-6 rounded bg-[var(--color-background-wMain)] p-0.5 shadow-md enabled:hover:bg-[var(--color-background-w100)]"
                                tooltip="Expand Navigation"
                            >
                                <ChevronRight className="size-4 text-[var(--color-primary-text-w10)]" />
                            </Button>
                        )}
                    </div>

                    {/* Icon Stack */}
                    <div className="flex flex-col items-center gap-2 py-3">
                        {/* New Chat */}
                        {showNewChatButton && (
                            <Button variant="ghost" onClick={handleNewChatClickResolved} className={navButtonStyles({ variant: "collapsed" })} tooltip={newChatLabel}>
                                <div className={iconWrapperStyles({ active: activeItem === "chats" })}>
                                    <NewChatIcon className={iconStyles({ active: activeItem === "chats" })} />
                                </div>
                            </Button>
                        )}

                        {/* Navigation Icons - rendered from navItems */}
                        {navItems.map(item => {
                            const isActive = isNavItemOrChildActive(item);
                            const hasSubmenu = item.hasSubmenu && item.children?.length;

                            return (
                                <Button
                                    key={item.id}
                                    variant="ghost"
                                    onClick={() => {
                                        if (hasSubmenu) {
                                            // Expand sidebar and open submenu
                                            setActiveItem(item.id);
                                            setExpandedMenus(prev => ({ ...prev, [item.id]: true }));
                                            setIsCollapsed(false);
                                        } else {
                                            handleItemClick(item.id, item);
                                        }
                                    }}
                                    className={navButtonStyles({ variant: "collapsed" })}
                                    tooltip={item.label}
                                    disabled={item.disabled}
                                >
                                    <div className={iconWrapperStyles({ active: isActive })}>
                                        <item.icon className={iconStyles({ active: isActive })} />
                                    </div>
                                </Button>
                            );
                        })}
                    </div>

                    {/* Bottom items */}
                    <div className="mt-auto flex flex-col items-center gap-2 border-t border-[var(--color-secondary-w70)] p-2">
                        {bottomItems.map(item => (
                            <Button key={item.id} variant="ghost" onClick={() => handleBottomItemClick(item)} className={navButtonStyles({ variant: "bottom" })} tooltip={item.label} disabled={item.disabled}>
                                <item.icon className="size-6" />
                            </Button>
                        ))}
                    </div>
                </>
            ) : (
                /* Expanded View */
                <>
                    {/* Header with Solace Logo and Collapse Button */}
                    <div className="flex items-center justify-between border-b border-[var(--color-secondary-w70)] py-3 pr-4 pl-6">
                        <div className="flex items-center gap-2">{renderHeader()}</div>
                        {!hideCollapseButton && (
                            <Button variant="ghost" onClick={handleToggle} className="h-8 w-8 p-1 text-[var(--color-primary-text-w10)] enabled:hover:bg-[var(--color-background-w100)]" tooltip="Collapse Navigation">
                                <ChevronLeft className="size-6" />
                            </Button>
                        )}
                    </div>

                    {/* Scrollable Navigation Section */}
                    <div className="flex-1 overflow-y-auto py-3">
                        {/* New Chat Button */}
                        {showNewChatButton && (
                            <Button variant="ghost" onClick={handleNewChatClickResolved} className={navButtonStyles()}>
                                <div className={iconWrapperStyles({ active: activeItem === "chats", withMargin: true })}>
                                    <NewChatIcon className={iconStyles({ active: activeItem === "chats" })} />
                                </div>
                                <span className={navTextStyles({ active: activeItem === "chats" })}>{newChatLabel}</span>
                            </Button>
                        )}

                        {/* Navigation Items */}
                        <div>
                            {navItems.map(item => {
                                // Check if any child is active
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
                                        {/* Submenu items with vertical line */}
                                        {item.hasSubmenu && expandedMenus[item.id] && item.children && (
                                            <div className="ml-10">
                                                {item.children.map(child => {
                                                    const isChildActive = activeItem === child.id;
                                                    return (
                                                        <div key={child.id} className="group relative">
                                                            {/* Left border line - 1px default, 3px on hover/active */}
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

                        {/* Recent Chats Section - conditionally rendered */}
                        {showRecentChats && (
                            <>
                                <div className="my-4 border-t border-[var(--color-secondary-w70)]" />
                                <div className="mb-2 flex items-center justify-between pr-4 pl-6">
                                    <span className="text-sm font-bold text-[var(--color-secondary-text-wMain)]">Recent Chats</span>
                                    <button onClick={() => navigate("/chats")} className="text-sm font-normal text-[var(--color-primary-w60)] hover:text-[var(--color-primary-text-w10)]">
                                        View All
                                    </button>
                                </div>
                                <div className="flex-1">
                                    <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                                </div>
                            </>
                        )}
                    </div>

                    {/* Bottom Section - Notifications and User Account */}
                    {/* Spacing: 8px above divider (mt-2) + 8px below divider (pt-2) = 16px total */}
                    <div className="mt-2 border-t border-[var(--color-secondary-w70)] pt-2">
                        {bottomItems.map(item => (
                            <Button key={item.id} variant="ghost" onClick={() => handleBottomItemClick(item)} className={navButtonStyles()} disabled={item.disabled}>
                                <div className={iconWrapperStyles({ withMargin: true })}>
                                    <item.icon className={iconStyles()} />
                                </div>
                                <span className={navTextStyles()}>{item.label}</span>
                            </Button>
                        ))}
                    </div>
                </>
            )}
        </aside>
    );
};
