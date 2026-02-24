import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { cva } from "class-variance-authority";
import { Plus, Bot, FolderOpen, BookOpenText, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Bell, User, LayoutGrid, Settings, LogOut } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useChatContext, useConfigContext, useAuthContext, useSessionStorage } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { RecentChatsList } from "@/lib/components/chat/RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";

// ============================================================================
// CVA Style Definitions
// ============================================================================

/** Navigation button styles - full width buttons in expanded sidebar */
const navButtonStyles = cva(["h-10", "w-full", "justify-start", "pr-4", "text-sm", "font-normal", "enabled:hover:bg-[var(--color-background-w100)]"], {
    variants: {
        indent: {
            true: "pl-4",
            false: "pl-6",
        },
        active: {
            true: "bg-[var(--color-background-w100)]",
            false: "",
        },
    },
    compoundVariants: [
        {
            indent: true,
            active: true,
            className: "bg-[var(--color-background-w100)]",
        },
    ],
    defaultVariants: { indent: false, active: false },
});

/** Icon wrapper container styles */
const iconWrapperStyles = cva(["flex", "size-8", "items-center", "justify-center", "rounded"], {
    variants: {
        active: {
            true: "border border-[var(--color-brand-w60)] bg-[var(--color-background-w100)]",
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

/** Collapsed mode icon button styles */
const collapsedButtonStyles = cva(["h-10", "w-10", "p-0", "enabled:hover:bg-[var(--color-background-w100)]"]);

/** Bottom section button styles (notifications, user, logout) */
const bottomButtonStyles = cva(["h-10", "w-10", "p-2", "text-[var(--color-primary-text-w10)]", "enabled:hover:bg-[var(--color-background-w100)]"]);

interface NavItem {
    id: string;
    label: string;
    icon: React.ElementType;
    onClick?: () => void;
    badge?: string;
    tooltip?: string;
    hasSubmenu?: boolean;
    children?: NavItem[];
}

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
            {item.badge && <span className="ml-auto rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-600">{item.badge}</span>}
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

interface CollapsibleNavigationSidebarProps {
    onNavigate?: (page: string) => void;
    /**
     * Items for the System Management submenu (enterprise-only feature).
     */
    additionalSystemManagementItems?: Array<{ id: string; label: string; icon?: React.ElementType }>;
    /** Additional top-level navigation items (for enterprise extensions like Gateways) */
    additionalNavItems?: Array<{ id: string; label: string; icon: React.ElementType; position?: "before-agents" | "after-agents" | "after-system-management" }>;
}

export const CollapsibleNavigationSidebar: React.FC<CollapsibleNavigationSidebarProps> = ({ onNavigate, additionalSystemManagementItems, additionalNavItems = [] }) => {
    const { logout } = useAuthContext();
    const navigate = useNavigate();
    const location = useLocation();

    // Persist collapse state - default to expanded (false = not collapsed)
    const [isCollapsed, setIsCollapsed] = useSessionStorage("nav-collapsed", false);

    const [activeItem, setActiveItem] = useState<string>("chats");
    const [expandedMenus, setExpandedMenus] = useState<Record<string, boolean>>({
        assets: false,
        systemManagement: false,
    });
    const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
    const [sessionToMove, setSessionToMove] = useState<Session | null>(null);
    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);
    const { handleNewSession, addNotification } = useChatContext();
    const { configUseAuthorization, configFeatureEnablement } = useConfigContext();
    const { projects } = useProjectContext();

    // Feature flags
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const logoutEnabled = configUseAuthorization && configFeatureEnablement?.logout ? true : false;

    // Sync active item with current route
    useEffect(() => {
        const path = location.pathname;
        if (path.startsWith("/agents")) {
            setActiveItem("agents");
        } else if (path.startsWith("/projects")) {
            setActiveItem("projects");
        } else if (path.startsWith("/prompts")) {
            setActiveItem("prompts");
            // Auto-expand Assets menu when on prompts page
            setExpandedMenus(prev => ({ ...prev, assets: true }));
        } else if (path.startsWith("/artifacts")) {
            setActiveItem("artifacts");
            // Auto-expand Assets menu when on artifacts page
            setExpandedMenus(prev => ({ ...prev, assets: true }));
        } else {
            setActiveItem("chats");
        }
    }, [location.pathname]);

    // Handle move session dialog event
    const handleOpenMoveDialog = useCallback((event: CustomEvent<{ session: Session }>) => {
        setSessionToMove(event.detail.session);
        setIsMoveDialogOpen(true);
    }, []);

    useEffect(() => {
        window.addEventListener("open-move-session-dialog", handleOpenMoveDialog as EventListener);
        return () => {
            window.removeEventListener("open-move-session-dialog", handleOpenMoveDialog as EventListener);
        };
    }, [handleOpenMoveDialog]);

    const handleMoveConfirm = async (targetProjectId: string | null) => {
        if (!sessionToMove) return;

        await api.webui.patch(`/api/v1/sessions/${sessionToMove.id}/project`, { projectId: targetProjectId });

        // Dispatch event to notify other components
        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("session-moved", {
                    detail: {
                        sessionId: sessionToMove.id,
                        projectId: targetProjectId,
                    },
                })
            );
            // Also trigger session-updated to refresh the list
            window.dispatchEvent(new CustomEvent("session-updated", { detail: { sessionId: sessionToMove.id } }));
        }

        addNotification?.("Session moved successfully", "success");
    };

    const handleItemClick = (itemId: string, item: NavItem) => {
        setActiveItem(itemId);

        if (item.onClick) {
            item.onClick();
            return;
        }

        // Handle navigation based on item id using React Router
        // First call onNavigate callback so enterprise can handle custom navigation
        onNavigate?.(itemId);

        // Then handle known routes
        switch (itemId) {
            case "agents":
                navigate("/agents");
                break;
            case "chats":
                navigate("/chat");
                break;
            case "projects":
                navigate("/projects");
                break;
            case "prompts":
                navigate("/prompts");
                break;
            case "artifacts":
                navigate("/artifacts");
                break;
            // For unknown items (like enterprise-specific ones),
            // the onNavigate callback above handles navigation
            default:
                // Try to navigate to /{itemId} as a fallback
                navigate(`/${itemId}`);
                break;
        }
    };

    const handleNewChatClick = () => {
        // Switch to chat view first, then directly start new session
        navigate("/chat");
        handleNewSession();
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

    // Define navigation items matching the screenshot
    const navItems: NavItem[] = useMemo(() => {
        const items: NavItem[] = [];

        // Projects
        if (projectsEnabled) {
            items.push({
                id: "projects",
                label: "Projects",
                icon: FolderOpen,
            });
        }

        // Assets with submenu
        items.push({
            id: "assets",
            label: "Assets",
            icon: BookOpenText,
            hasSubmenu: true,
            children: [
                { id: "artifacts", label: "Artifacts", icon: BookOpenText },
                { id: "prompts", label: "Prompts", icon: BookOpenText, tooltip: "Experimental Feature" },
            ],
        });

        // Add additional nav items positioned "before-agents"
        additionalNavItems
            .filter(item => item.position === "before-agents")
            .forEach(item => {
                items.push({
                    id: item.id,
                    label: item.label,
                    icon: item.icon,
                });
            });

        // Agents
        items.push({
            id: "agents",
            label: "Agents",
            icon: Bot,
        });

        // Add additional nav items positioned "after-agents"
        additionalNavItems
            .filter(item => item.position === "after-agents")
            .forEach(item => {
                items.push({
                    id: item.id,
                    label: item.label,
                    icon: item.icon,
                });
            });

        // System Management with submenu (enterprise-only)
        // Only shown when additionalSystemManagementItems is provided
        if (additionalSystemManagementItems && additionalSystemManagementItems.length > 0) {
            const systemManagementChildren: NavItem[] = [{ id: "agentManagement", label: "Agent Management", icon: Settings }];

            // Add any additional items passed from enterprise (e.g., Activities)
            additionalSystemManagementItems.forEach(item => {
                systemManagementChildren.push({
                    id: item.id,
                    label: item.label,
                    icon: item.icon || Settings,
                });
            });

            items.push({
                id: "systemManagement",
                label: "System Management",
                icon: LayoutGrid,
                hasSubmenu: true,
                children: systemManagementChildren,
            });
        }

        // Add additional nav items positioned "after-system-management" or with no position specified
        additionalNavItems
            .filter(item => item.position === "after-system-management" || !item.position)
            .forEach(item => {
                items.push({
                    id: item.id,
                    label: item.label,
                    icon: item.icon,
                });
            });

        return items;
    }, [projectsEnabled, additionalSystemManagementItems, additionalNavItems]);

    return (
        <aside className={cn("navigation-sidebar flex h-full flex-col overflow-visible border-r bg-[var(--color-background-wMain)]", isCollapsed ? "w-16" : "w-64")}>
            {isCollapsed ? (
                /* Collapsed View - Icon Only */
                <>
                    {/* Header with Short Logo */}
                    <div className="relative flex w-full items-center justify-center overflow-visible border-b border-[var(--color-secondary-w70)] py-3">
                        <SolaceIcon variant="short" className="h-8 w-8" />
                        {/* Expand Chevron - positioned outside the panel */}
                        <Button variant="ghost" onClick={handleToggle} className="absolute -right-3 z-10 h-6 w-6 rounded bg-[var(--color-background-wMain)] p-0.5 shadow-md enabled:hover:bg-[var(--color-background-w100)]" tooltip="Expand Navigation">
                            <ChevronRight className="size-4 text-[var(--color-primary-text-w10)]" />
                        </Button>
                    </div>

                    {/* Icon Stack */}
                    <div className="flex flex-col items-center gap-2 py-3">
                        {/* New Chat */}
                        <Button variant="ghost" onClick={handleNewChatClick} className={collapsedButtonStyles()} tooltip="New Chat">
                            <div className={iconWrapperStyles({ active: activeItem === "chats" })}>
                                <Plus className={iconStyles({ active: activeItem === "chats" })} />
                            </div>
                        </Button>

                        {/* Navigation Icons */}
                        {projectsEnabled && (
                            <Button variant="ghost" onClick={() => handleItemClick("projects", { id: "projects", label: "Projects", icon: FolderOpen })} className={collapsedButtonStyles()} tooltip="Projects">
                                <div className={iconWrapperStyles({ active: activeItem === "projects" })}>
                                    <FolderOpen className={iconStyles({ active: activeItem === "projects" })} />
                                </div>
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            onClick={() => {
                                // Expand sidebar, open Assets submenu, and select parent
                                setActiveItem("assets");
                                setExpandedMenus(prev => ({ ...prev, assets: true }));
                                setIsCollapsed(false);
                            }}
                            className={collapsedButtonStyles()}
                            tooltip="Assets"
                        >
                            <div className={iconWrapperStyles({ active: activeItem === "assets" || activeItem === "artifacts" || activeItem === "prompts" })}>
                                <BookOpenText className={iconStyles({ active: activeItem === "assets" || activeItem === "artifacts" || activeItem === "prompts" })} />
                            </div>
                        </Button>
                        <Button variant="ghost" onClick={() => handleItemClick("agents", { id: "agents", label: "Agents", icon: Bot })} className={collapsedButtonStyles()} tooltip="Agents">
                            <div className={iconWrapperStyles({ active: activeItem === "agents" })}>
                                <Bot className={iconStyles({ active: activeItem === "agents" })} />
                            </div>
                        </Button>
                        {additionalSystemManagementItems && additionalSystemManagementItems.length > 0 && (
                            <Button
                                variant="ghost"
                                onClick={() => {
                                    // Expand sidebar, open System Management submenu, and select parent
                                    setActiveItem("systemManagement");
                                    setExpandedMenus(prev => ({ ...prev, systemManagement: true }));
                                    setIsCollapsed(false);
                                }}
                                className={collapsedButtonStyles()}
                                tooltip="System Management"
                            >
                                <div className={iconWrapperStyles({ active: activeItem === "systemManagement" || activeItem === "agentManagement" || activeItem === "activities" })}>
                                    <LayoutGrid className={iconStyles({ active: activeItem === "systemManagement" || activeItem === "agentManagement" || activeItem === "activities" })} />
                                </div>
                            </Button>
                        )}
                    </div>

                    {/* Bottom items */}
                    <div className="mt-auto flex flex-col items-center gap-2 border-t border-[var(--color-secondary-w70)] p-2">
                        <Button variant="ghost" className={bottomButtonStyles()} tooltip="Notifications">
                            <Bell className="size-6" />
                        </Button>
                        <Button variant="ghost" onClick={() => setIsSettingsDialogOpen(true)} className={bottomButtonStyles()} tooltip="Settings">
                            <User className="size-6" />
                        </Button>
                        {logoutEnabled && (
                            <Button variant="ghost" onClick={() => logout()} className={bottomButtonStyles()} tooltip="Log Out">
                                <LogOut className="size-6" />
                            </Button>
                        )}
                    </div>
                </>
            ) : (
                /* Expanded View */
                <>
                    {/* Header with Solace Logo and Collapse Button */}
                    <div className="flex items-center justify-between border-b border-[var(--color-secondary-w70)] py-3 pr-4 pl-6">
                        <div className="flex items-center gap-2">
                            <SolaceIcon className="h-8 w-24" />
                        </div>
                        <Button variant="ghost" onClick={handleToggle} className="h-8 w-8 p-1 text-[var(--color-primary-text-w10)] enabled:hover:bg-[var(--color-background-w100)]" tooltip="Collapse Navigation">
                            <ChevronLeft className="size-6" />
                        </Button>
                    </div>

                    {/* Scrollable Navigation Section */}
                    <div className="flex-1 overflow-y-auto py-3">
                        {/* New Chat Button */}
                        <Button variant="ghost" onClick={handleNewChatClick} className={navButtonStyles()}>
                            <div className={iconWrapperStyles({ active: activeItem === "chats", withMargin: true })}>
                                <Plus className={iconStyles({ active: activeItem === "chats" })} />
                            </div>
                            <span className={navTextStyles({ active: activeItem === "chats" })}>New Chat</span>
                        </Button>

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

                        {/* Divider */}
                        <div className="my-4 border-t border-[var(--color-secondary-w70)]" />

                        {/* Recent Chats Section */}
                        <div className="mb-2 flex items-center justify-between pr-4 pl-6">
                            <span className="text-sm font-bold text-[var(--color-secondary-text-wMain)]">Recent Chats</span>
                            <button onClick={() => navigate("/chats")} className="text-sm font-normal text-[var(--color-primary-w60)] hover:text-[var(--color-primary-text-w10)]">
                                View All
                            </button>
                        </div>

                        {/* Recent Chats List - fills available space until Notifications */}
                        <div className="flex-1">
                            <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                        </div>
                    </div>

                    {/* Bottom Section - Notifications and User Account */}
                    {/* Spacing: 8px above divider (mt-2) + 8px below divider (pt-2) = 16px total */}
                    <div className="mt-2 border-t border-[var(--color-secondary-w70)] pt-2">
                        <Button variant="ghost" className={navButtonStyles()}>
                            <div className={iconWrapperStyles({ withMargin: true })}>
                                <Bell className={iconStyles()} />
                            </div>
                            <span className={navTextStyles()}>Notifications</span>
                        </Button>
                        <Button variant="ghost" onClick={() => setIsSettingsDialogOpen(true)} className={navButtonStyles()}>
                            <div className={iconWrapperStyles({ withMargin: true })}>
                                <User className={iconStyles()} />
                            </div>
                            <span className={navTextStyles()}>User Account</span>
                        </Button>
                        {logoutEnabled && (
                            <Button variant="ghost" onClick={() => logout()} className={navButtonStyles()}>
                                <div className={iconWrapperStyles({ withMargin: true })}>
                                    <LogOut className={iconStyles()} />
                                </div>
                                <span className={navTextStyles()}>Log Out</span>
                            </Button>
                        )}
                    </div>
                </>
            )}

            {/* Move Session Dialog */}
            <MoveSessionDialog
                isOpen={isMoveDialogOpen}
                onClose={() => {
                    setIsMoveDialogOpen(false);
                    setSessionToMove(null);
                }}
                onConfirm={handleMoveConfirm}
                session={sessionToMove}
                projects={projects}
                currentProjectId={sessionToMove?.projectId}
            />

            {/* Settings Dialog */}
            <SettingsDialog open={isSettingsDialogOpen} onOpenChange={setIsSettingsDialogOpen} />
        </aside>
    );
};
