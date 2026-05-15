import type React from "react";
import { useEffect, useMemo, useState, useCallback } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { MessageCircle, Plus, FileBox, NotepadText } from "lucide-react";

import { NavigationSidebar, CollapsibleNavigationSidebar, ToastContainer, bottomNavigationItems, getTopNavigationItems, EmptyState, MobileNavDrawer } from "@/lib/components";
import type { MobileNavItem } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { ModelSetupDialog } from "@/lib/components/models/ModelSetupDialog";
import { ModelWarningBanner } from "@/lib/components/models/ModelWarningBanner";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { ChatProvider } from "@/lib/providers";
import { useBooleanFlagDetails } from "@openfeature/react-sdk";
import { useAuthContext, useBeforeUnload, useConfigContext, useChatContext, useNavigationItems, useLocalStorage, useMoveSession, useIsNewNavigationEnabled } from "@/lib/hooks";
import { useNotificationSSE } from "@/lib/hooks/useNotificationSSE";
import { useModelConfigStatus } from "@/lib/api/models";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, logout, useAuthorization } = useAuthContext();
    const { configFeatureEnablement } = useConfigContext();
    const { value: modelConfigUiEnabled } = useBooleanFlagDetails("model_config_ui", false);
    const { isMenuOpen, menuPosition, selectedText, sourceTaskId, clearSelection } = useTextSelection();
    const { hasModelConfigWrite, handleNewSession } = useChatContext();
    const { isMoveDialogOpen, sessionToMove, handleMoveConfirm, closeMoveDialog } = useMoveSession();

    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);
    const [isModelSetupDialogOpen, setIsModelSetupDialogOpen] = useState(false);
    const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
    const [modelSetupDismissed, setModelSetupDismissed] = useLocalStorage("model-setup-dialog-dismissed", false);

    const { data: modelConfigStatus } = useModelConfigStatus();

    useEffect(() => {
        if (modelConfigUiEnabled && modelConfigStatus && !modelConfigStatus.configured && !modelSetupDismissed) {
            setIsModelSetupDialogOpen(true);
        }
    }, [modelConfigStatus, modelSetupDismissed, modelConfigUiEnabled]);

    const handleModelSetupDialogChange = useCallback(
        (open: boolean) => {
            setIsModelSetupDialogOpen(open);
            if (!open) {
                setModelSetupDismissed(true);
            }
        },
        [setModelSetupDismissed]
    );

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

    const topNavItems = getTopNavigationItems(configFeatureEnablement);
    const useNewNav = useIsNewNavigationEnabled();
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const logoutEnabled = configFeatureEnablement?.logout ?? false;

    const handleUserAccountClick = useCallback(() => {
        setIsSettingsDialogOpen(true);
    }, []);

    const { items, activeItemId } = useNavigationItems({
        projectsEnabled,
        promptLibraryEnabled: configFeatureEnablement?.promptLibrary ?? false,
        artifactsPageEnabled: configFeatureEnablement?.artifactsPage ?? false,
        schedulerEnabled: configFeatureEnablement?.scheduler ?? false,
        logoutEnabled,
        isAuthenticated,
        onUserAccountClick: handleUserAccountClick,
        onLogoutClick: logout,
    });

    useBeforeUnload();

    // Subscribe to server-pushed notifications (e.g. scheduled task session created)
    // so the Recent Chats sidebar updates in real time.
    useNotificationSSE();

    const getActiveItem = () => {
        const path = location.pathname;
        if (path === "/" || path.startsWith("/chat") || path.startsWith("/recent-chats")) return "chat";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/artifacts")) return "artifacts";
        if (path.startsWith("/prompts")) return "prompts";
        if (path.startsWith("/agents")) return "agentMesh";
        return "chat";
    };

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

    // Build a flat list of items for the mobile nav drawer that works for both
    // legacy and new navigation modes. Drawer rows are icon + label.
    const { mobileNavItems, mobileBottomNavItems } = useMemo<{ mobileNavItems: MobileNavItem[]; mobileBottomNavItems: MobileNavItem[] }>(() => {
        const newChatItem: MobileNavItem = {
            id: "new-chat",
            label: "New Chat",
            icon: Plus,
            onClick: () => {
                if (location.pathname !== "/chat") navigate("/chat");
                handleNewSession();
            },
        };

        const recentChatsItem: MobileNavItem = {
            id: "recent-chats",
            label: "Recent Chats",
            icon: MessageCircle,
            onClick: () => navigate("/recent-chats"),
            isActive: location.pathname.startsWith("/recent-chats"),
        };

        // Match legacy nav icons for these destinations so the mobile drawer
        // looks consistent regardless of which nav mode is active.
        const legacyIconOverrides: Record<string, React.ElementType> = {
            prompts: NotepadText,
            artifacts: FileBox,
        };

        if (useNewNav) {
            const flat = items.flatMap(item => (item.children && item.children.length > 0 ? item.children.map(c => ({ ...c, position: item.position })) : [item]));
            const top: MobileNavItem[] = [];
            const bottom: MobileNavItem[] = [];
            for (const item of flat) {
                if (!item.icon) continue;
                const navItem: MobileNavItem = {
                    id: item.id,
                    label: item.label,
                    icon: legacyIconOverrides[item.id] ?? item.icon,
                    onClick: () => {
                        if (item.onClick) item.onClick();
                        else if (item.route) navigate(item.route);
                    },
                    isActive: activeItemId === item.id,
                };
                (item.position === "bottom" ? bottom : top).push(navItem);
            }
            return { mobileNavItems: [newChatItem, recentChatsItem, ...top], mobileBottomNavItems: bottom };
        }

        const activeId = getActiveItem();
        const top: MobileNavItem[] = topNavItems.map(item => ({
            id: item.id,
            label: item.label,
            icon: item.icon,
            onClick: () => handleNavItemChange(item.id),
            isActive: activeId === item.id,
        }));
        const bottom: MobileNavItem[] = bottomNavigationItems
            .filter(item => item.id !== "theme-toggle")
            .map(item => ({
                id: item.id,
                label: item.label,
                icon: item.icon,
                onClick: () => handleNavItemChange(item.id),
            }));
        return { mobileNavItems: [newChatItem, recentChatsItem, ...top], mobileBottomNavItems: bottom };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [useNewNav, items, activeItemId, topNavItems, location.pathname, navigate, handleNewSession]);

    // Allow page-level headers (e.g. ChatPage hamburger) to open the mobile nav drawer.
    useEffect(() => {
        const handler = () => setIsMobileNavOpen(true);
        window.addEventListener("open-mobile-nav", handler);
        return () => window.removeEventListener("open-mobile-nav", handler);
    }, []);

    if (useAuthorization && !isAuthenticated) {
        return (
            <EmptyState
                variant="noImage"
                title="Welcome to Solace Agent Mesh!"
                className="h-dvh w-screen"
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

    return (
        <div className={`relative flex h-dvh`}>
            <div className="hidden md:contents">
                {useNewNav ? (
                    <CollapsibleNavigationSidebar items={items} activeItemId={activeItemId} showNewChatButton showRecentChats />
                ) : (
                    <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
                )}
            </div>
            <main className="flex h-full w-full min-w-0 flex-1 flex-col">
                <ModelWarningBanner />
                <Outlet />
            </main>
            <MobileNavDrawer open={isMobileNavOpen} onOpenChange={setIsMobileNavOpen} items={mobileNavItems} bottomItems={mobileBottomNavItems} />
            <ToastContainer />
            <SelectionContextMenu isOpen={isMenuOpen} position={menuPosition} selectedText={selectedText || ""} sourceTaskId={sourceTaskId} onClose={clearSelection} />

            <MoveSessionDialog isOpen={isMoveDialogOpen} onClose={closeMoveDialog} onConfirm={handleMoveConfirm} session={sessionToMove} currentProjectId={sessionToMove?.projectId} />
            <SettingsDialog open={isSettingsDialogOpen} onOpenChange={setIsSettingsDialogOpen} />
            <ModelSetupDialog open={isModelSetupDialogOpen} onOpenChange={handleModelSetupDialogChange} hasWritePermissions={hasModelConfigWrite} />
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
