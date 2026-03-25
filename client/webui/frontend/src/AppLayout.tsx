import { useEffect, useState, useCallback } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationSidebar, CollapsibleNavigationSidebar, ToastContainer, bottomNavigationItems, getTopNavigationItems, EmptyState } from "@/lib/components";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { ModelSetupDialog } from "@/lib/components/models/ModelSetupDialog";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { Button } from "@/lib/components/ui";
import { ChatProvider } from "@/lib/providers";
import { useAuthContext, useBeforeUnload, useConfigContext, useChatContext, useNavigationItems, useBooleanFlagDetails, useLocalStorage } from "@/lib/hooks";
import { useModelConfigStatus } from "@/lib/api/models";
import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, logout, useAuthorization } = useAuthContext();
    const { configFeatureEnablement } = useConfigContext();
    const { value: modelConfigUiEnabled } = useBooleanFlagDetails("model_config_ui", false);
    const { isMenuOpen, menuPosition, selectedText, sourceTaskId, clearSelection } = useTextSelection();
    const { addNotification, hasModelConfigWrite } = useChatContext();

    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);
    const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
    const [sessionToMove, setSessionToMove] = useState<Session | null>(null);
    const [isModelSetupDialogOpen, setIsModelSetupDialogOpen] = useState(false);
    const [modelSetupDismissed, setModelSetupDismissed] = useLocalStorage("model-setup-dialog-dismissed", false);

    const { data: modelConfigStatus } = useModelConfigStatus();
    const showModelWarning = modelConfigUiEnabled && modelConfigStatus && !modelConfigStatus.configured;

    useEffect(() => {
        if (modelConfigUiEnabled && modelConfigStatus && !modelConfigStatus.configured && !modelSetupDismissed) {
            setIsModelSetupDialogOpen(true);
        }
    }, [modelConfigStatus, modelSetupDismissed, modelConfigUiEnabled]);

    const handleModelSetupDialogChange = useCallback((open: boolean) => {
        setIsModelSetupDialogOpen(open);
        if (!open) {
            setModelSetupDismissed(true);
        }
    }, [setModelSetupDismissed]);

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

        try {
            await api.webui.patch(`/api/v1/sessions/${sessionToMove.id}/project`, { projectId: targetProjectId });

            window.dispatchEvent(
                new CustomEvent("session-updated", {
                    detail: {
                        sessionId: sessionToMove.id,
                        projectId: targetProjectId,
                    },
                })
            );

            addNotification?.("Session moved successfully", "success");
        } catch (error) {
            console.error("Failed to move session:", error);
            addNotification?.("Failed to move session", "warning");
        }
    };

    const topNavItems = getTopNavigationItems(configFeatureEnablement);
    const useNewNav = configFeatureEnablement?.newNavigation ?? false;
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const logoutEnabled = configFeatureEnablement?.logout ?? false;

    const handleUserAccountClick = useCallback(() => {
        setIsSettingsDialogOpen(true);
    }, []);

    const { items, activeItemId } = useNavigationItems({
        projectsEnabled,
        promptLibraryEnabled: configFeatureEnablement?.promptLibrary ?? false,
        artifactsPageEnabled: configFeatureEnablement?.artifactsPage ?? false,
        logoutEnabled,
        isAuthenticated,
        onUserAccountClick: handleUserAccountClick,
        onLogoutClick: logout,
    });

    useBeforeUnload();

    const getActiveItem = () => {
        const path = location.pathname;
        if (path === "/" || path.startsWith("/chat")) return "chat";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/artifacts")) return "artifacts";
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
                <CollapsibleNavigationSidebar items={items} activeItemId={activeItemId} showNewChatButton showRecentChats />
            ) : (
                <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
            )}
            <main className="h-full w-full flex-1 overflow-auto">
                {showModelWarning && (
                    <MessageBanner
                        variant="warning"
                        style={{ alignItems: "center" }}
                        message={
                            <div className="flex w-full items-center justify-between gap-3">
                                <span>
                                    No model has been set up. Some features may not work as intended without a configured model.
                                    {!hasModelConfigWrite && " Contact your administrator for assistance."}
                                </span>
                                {hasModelConfigWrite && (
                                    <Button variant="outline" size="sm" className="shrink-0" onClick={() => navigate("/agents?tab=models")}>
                                        Add Model
                                    </Button>
                                )}
                            </div>
                        }
                    />
                )}
                <Outlet />
            </main>
            <ToastContainer />
            <SelectionContextMenu isOpen={isMenuOpen} position={menuPosition} selectedText={selectedText || ""} sourceTaskId={sourceTaskId} onClose={clearSelection} />

            <MoveSessionDialog
                isOpen={isMoveDialogOpen}
                onClose={() => {
                    setIsMoveDialogOpen(false);
                    setSessionToMove(null);
                }}
                onConfirm={handleMoveConfirm}
                session={sessionToMove}
                currentProjectId={sessionToMove?.projectId}
            />
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
