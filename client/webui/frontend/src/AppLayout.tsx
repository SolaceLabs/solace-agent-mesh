import { useEffect, useState, useCallback } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationSidebar, CollapsibleNavigationSidebar, ToastContainer, bottomNavigationItems, getTopNavigationItems, EmptyState, SAM_ITEMS, filterItems } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { ChatProvider, useProjectContext } from "@/lib/providers";
import { useAuthContext, useBeforeUnload, useConfigContext, useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, logout, useAuthorization } = useAuthContext();
    const { configFeatureEnablement } = useConfigContext();
    const { isMenuOpen, menuPosition, selectedText, sourceTaskId, clearSelection } = useTextSelection();
    const { addNotification } = useChatContext();
    const { projects } = useProjectContext();

    // Dialog state (moved from CollapsibleNavigationSidebar)
    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);
    const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
    const [sessionToMove, setSessionToMove] = useState<Session | null>(null);

    // Temporary fix: Radix dialogs sometimes leave pointer-events: none on body when closed
    useEffect(() => {
        const observer = new MutationObserver(() => {
            const bodyStyle = document.body.style.pointerEvents;
            const hasOpenOverlays = document.querySelector('[data-state="open"]');

            // If no overlays (dialogs, popovers, etc.) are open but pointer-events is set to none, remove it
            if (!hasOpenOverlays && bodyStyle === "none") {
                document.body.style.removeProperty("pointer-events");
            }
        });

        // Observe changes to body styles and DOM changes for overlays
        observer.observe(document.body, {
            attributes: true,
            attributeFilter: ["style"],
            childList: true,
            subtree: true,
        });

        return () => {
            observer.disconnect();
        };
    }, []);

    // Handle move session dialog event (moved from CollapsibleNavigationSidebar)
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

    // Get navigation items based on feature flags
    const topNavItems = getTopNavigationItems(configFeatureEnablement);

    // Feature flag for new collapsible navigation
    const useNewNav = configFeatureEnablement?.newNavigation ?? false;

    // Feature flags for new navigation
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const logoutEnabled = configFeatureEnablement?.logout ?? false;

    // Filter SAM items based on feature flags
    const filteredItems = filterItems(SAM_ITEMS, { projects: projectsEnabled, logout: logoutEnabled });

    // Inject onClick handlers for bottom items that need special behavior
    const itemsWithHandlers = filteredItems.map(item => {
        if (item.id === "userAccount") {
            return { ...item, onClick: () => setIsSettingsDialogOpen(true) };
        }
        if (item.id === "logout") {
            return { ...item, onClick: logout };
        }
        return item;
    });

    // Enable beforeunload warning when chat data is present
    useBeforeUnload();

    const getActiveItem = () => {
        const path = location.pathname;
        if (path === "/" || path.startsWith("/chat")) return "chat";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/prompts")) return "prompts";
        if (path.startsWith("/agents")) return "agentMesh";
        return "chat";
    };

    if (useAuthorization && !isAuthenticated) {
        return (
            <EmptyState
                variant="noImage"
                title="Welcome to Solace Agent Mesh!"
                className="h-screen w-screen"
                buttons={[
                    {
                        text: "Login",
                        onClick: () => login(),
                        variant: "default",
                    },
                ]}
            />
        );
    }

    const handleNavItemChange = (itemId: string) => {
        const item = topNavItems.find(item => item.id === itemId) || bottomNavigationItems.find(item => item.id === itemId);

        if (item?.onClick && itemId !== "settings") {
            item.onClick();
        } else if (itemId !== "settings") {
            navigate(`/${itemId === "agentMesh" ? "agents" : itemId}`);
        }
    };

    const handleHeaderClick = () => {
        navigate("/chat");
    };

    return (
        <div className={`relative flex h-screen`}>
            {useNewNav ? (
                <CollapsibleNavigationSidebar items={itemsWithHandlers} showNewChatButton showRecentChats />
            ) : (
                <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
            )}
            <main className="h-full w-full flex-1 overflow-auto">
                <Outlet />
            </main>
            <ToastContainer />
            <SelectionContextMenu isOpen={isMenuOpen} position={menuPosition} selectedText={selectedText || ""} sourceTaskId={sourceTaskId} onClose={clearSelection} />

            {/* Dialogs (moved from CollapsibleNavigationSidebar) */}
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
            <SettingsDialog open={isSettingsDialogOpen} onOpenChange={setIsSettingsDialogOpen} />
        </div>
    );
}

function AppLayout() {
    return (
        <ChatProvider>
            <AppLayoutContent />
        </ChatProvider>
    );
}

export default AppLayout;
