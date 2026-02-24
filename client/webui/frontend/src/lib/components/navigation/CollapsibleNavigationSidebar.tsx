import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";

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
    const buttonContent = (
        <Button
            variant="ghost"
            onClick={item.hasSubmenu ? onToggleExpand : onClick}
            className={cn("h-10 w-full justify-start px-2 text-sm font-normal hover:bg-[var(--color-background-w100)]", indent && "pl-4", indent && isActive && "bg-[var(--color-background-w200)]", className)}
        >
            {indent ? (
                // Subitem - no icon wrapper, just text
                <span className={cn(isActive ? "text-[var(--color-primary-text-w10)]" : "text-[var(--color-secondary-text-w50)]")}>{item.label}</span>
            ) : (
                // Main item - with icon wrapper
                <>
                    <div className={cn("mr-2 flex size-8 items-center justify-center rounded", (isActive || hasActiveChild) && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]")}>
                        <item.icon className={cn("size-6", isActive || hasActiveChild ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
                    </div>
                    <span className={cn(isActive || hasActiveChild ? "text-[var(--color-primary-text-w10)]" : "text-[var(--color-secondary-text-w50)]")}>{item.label}</span>
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
                        <Button variant="ghost" onClick={handleToggle} className="absolute -right-3 z-10 h-6 w-6 rounded bg-[var(--color-background-wMain)] p-0.5 shadow-md hover:bg-[var(--color-background-w100)]" tooltip="Expand Navigation">
                            <ChevronRight className="size-4 text-[var(--color-primary-text-w10)]" />
                        </Button>
                    </div>

                    {/* Icon Stack */}
                    <div className="flex flex-col items-center gap-2 py-3">
                        {/* New Chat */}
                        <Button variant="ghost" onClick={handleNewChatClick} className="h-10 w-10 p-0 hover:bg-[var(--color-background-w100)]" tooltip="New Chat">
                            <div className={cn("flex size-8 items-center justify-center rounded", activeItem === "chats" && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]")}>
                                <Plus className={cn("size-6", activeItem === "chats" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
                            </div>
                        </Button>

                        {/* Navigation Icons */}
                        {projectsEnabled && (
                            <Button variant="ghost" onClick={() => handleItemClick("projects", { id: "projects", label: "Projects", icon: FolderOpen })} className="h-10 w-10 p-0 hover:bg-[var(--color-background-w100)]" tooltip="Projects">
                                <div className={cn("flex size-8 items-center justify-center rounded", activeItem === "projects" && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]")}>
                                    <FolderOpen className={cn("size-6", activeItem === "projects" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
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
                            className="h-10 w-10 p-0 hover:bg-[var(--color-background-w100)]"
                            tooltip="Assets"
                        >
                            <div
                                className={cn(
                                    "flex size-8 items-center justify-center rounded",
                                    (activeItem === "assets" || activeItem === "artifacts" || activeItem === "prompts") && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]"
                                )}
                            >
                                <BookOpenText className={cn("size-6", activeItem === "assets" || activeItem === "artifacts" || activeItem === "prompts" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
                            </div>
                        </Button>
                        <Button variant="ghost" onClick={() => handleItemClick("agents", { id: "agents", label: "Agents", icon: Bot })} className="h-10 w-10 p-0 hover:bg-[var(--color-background-w100)]" tooltip="Agents">
                            <div className={cn("flex size-8 items-center justify-center rounded", activeItem === "agents" && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]")}>
                                <Bot className={cn("size-6", activeItem === "agents" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
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
                                className="h-10 w-10 p-0 hover:bg-[var(--color-background-w100)]"
                                tooltip="System Management"
                            >
                                <div
                                    className={cn(
                                        "flex size-8 items-center justify-center rounded",
                                        (activeItem === "systemManagement" || activeItem === "agentManagement" || activeItem === "activities") && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]"
                                    )}
                                >
                                    <LayoutGrid
                                        className={cn("size-6", activeItem === "systemManagement" || activeItem === "agentManagement" || activeItem === "activities" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")}
                                    />
                                </div>
                            </Button>
                        )}
                    </div>

                    {/* Bottom items */}
                    <div className="mt-auto flex flex-col items-center gap-2 border-t border-[var(--color-secondary-w70)] p-2">
                        <Button variant="ghost" className="h-10 w-10 p-2 text-[var(--color-primary-text-w10)] hover:bg-[var(--color-background-w100)]" tooltip="Notifications">
                            <Bell className="size-6" />
                        </Button>
                        <Button variant="ghost" onClick={() => setIsSettingsDialogOpen(true)} className="h-10 w-10 p-2 text-[var(--color-primary-text-w10)] hover:bg-[var(--color-background-w100)]" tooltip="Settings">
                            <User className="size-6" />
                        </Button>
                        {logoutEnabled && (
                            <Button variant="ghost" onClick={() => logout()} className="h-10 w-10 p-2 text-[var(--color-primary-text-w10)] hover:bg-[var(--color-background-w100)]" tooltip="Log Out">
                                <LogOut className="size-6" />
                            </Button>
                        )}
                    </div>
                </>
            ) : (
                /* Expanded View */
                <>
                    {/* Header with Solace Logo and Collapse Button */}
                    <div className="flex items-center justify-between border-b border-[var(--color-secondary-w70)] px-4 py-3">
                        <div className="flex items-center gap-2">
                            <SolaceIcon className="h-8 w-24" />
                        </div>
                        <Button variant="ghost" onClick={handleToggle} className="h-8 w-8 p-1 text-[var(--color-primary-text-w10)] hover:bg-[var(--color-background-w100)]" tooltip="Collapse Navigation">
                            <ChevronLeft className="size-6" />
                        </Button>
                    </div>

                    {/* Scrollable Navigation Section */}
                    <div className="flex-1 overflow-y-auto px-2 py-3">
                        {/* New Chat Button */}
                        <Button variant="ghost" onClick={handleNewChatClick} className="h-10 w-full justify-start px-2 text-sm font-normal hover:bg-[var(--color-background-w100)]">
                            <div className={cn("mr-2 flex size-8 items-center justify-center rounded", activeItem === "chats" && "border border-[var(--color-brand-w60)] bg-[var(--color-background-w200)]")}>
                                <Plus className={cn("size-6", activeItem === "chats" ? "text-[var(--color-brand-w60)]" : "text-[var(--color-secondary-wMain)]")} />
                            </div>
                            <span className={cn(activeItem === "chats" ? "text-[var(--color-primary-text-w10)]" : "text-[var(--color-secondary-text-w50)]")}>New Chat</span>
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
                                            <div className="relative ml-12">
                                                {/* Vertical section line */}
                                                <div className="absolute top-0 left-0 h-full w-px" style={{ backgroundColor: "color-mix(in srgb, var(--color-brand-wMain) 30%, transparent)" }} />
                                                {item.children.map(child => {
                                                    const isChildActive = activeItem === child.id;
                                                    return (
                                                        <div key={child.id} className="relative">
                                                            {/* Selected state line - thicker when active */}
                                                            {isChildActive && <div className="absolute top-0 left-0 h-full w-[3px] bg-[var(--color-brand-w60)]" />}
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
                        <div className="mb-2 flex items-center justify-between px-2">
                            <span className="text-sm font-normal text-[var(--color-primary-text-w10)]">Recent Chats</span>
                            <button onClick={() => navigate("/chats")} className="text-sm font-normal text-[var(--color-secondary-w70)] hover:text-[var(--color-primary-text-w10)]">
                                View All
                            </button>
                        </div>

                        {/* Recent Chats List - fills available space until Notifications */}
                        <div className="flex-1 px-2">
                            <RecentChatsList maxItems={MAX_RECENT_CHATS} />
                        </div>
                    </div>

                    {/* Bottom Section - Notifications and User Account */}
                    {/* Spacing: 8px above divider (mt-2) + 8px below divider (pt-2) = 16px total */}
                    <div className="mt-2 border-t border-[var(--color-secondary-w70)] px-2 pt-2">
                        <Button variant="ghost" className="h-10 w-full justify-start px-2 text-sm font-normal hover:bg-[var(--color-background-w100)]">
                            <div className="mr-2 flex size-8 items-center justify-center rounded">
                                <Bell className="size-6 text-[var(--color-secondary-wMain)]" />
                            </div>
                            <span className="text-[var(--color-secondary-text-w50)]">Notifications</span>
                        </Button>
                        <Button variant="ghost" onClick={() => setIsSettingsDialogOpen(true)} className="h-10 w-full justify-start px-2 text-sm font-normal hover:bg-[var(--color-background-w100)]">
                            <div className="mr-2 flex size-8 items-center justify-center rounded">
                                <User className="size-6 text-[var(--color-secondary-wMain)]" />
                            </div>
                            <span className="text-[var(--color-secondary-text-w50)]">User Account</span>
                        </Button>
                        {logoutEnabled && (
                            <Button variant="ghost" onClick={() => logout()} className="h-10 w-full justify-start px-2 text-sm font-normal hover:bg-[var(--color-background-w100)]">
                                <div className="mr-2 flex size-8 items-center justify-center rounded">
                                    <LogOut className="size-6 text-[var(--color-secondary-wMain)]" />
                                </div>
                                <span className="text-[var(--color-secondary-text-w50)]">Log Out</span>
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
