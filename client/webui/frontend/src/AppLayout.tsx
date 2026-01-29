import { useEffect, useState, useCallback } from "react";
import { Outlet } from "react-router-dom";

import { ToastContainer, EmptyState } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { SessionSidePanel } from "@/lib/components/chat";
import { ChatProvider } from "@/lib/providers";
import { useAuthContext, useBeforeUnload } from "@/lib/hooks";

function AppLayoutContent() {
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { isMenuOpen, menuPosition, selectedText, clearSelection } = useTextSelection();
    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);

    const handleSessionSidePanelToggle = useCallback(() => {
        setIsSessionSidePanelCollapsed(!isSessionSidePanelCollapsed);
    }, [isSessionSidePanelCollapsed]);

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

    // Enable beforeunload warning when chat data is present
    useBeforeUnload();

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

    return (
        <div className="relative flex h-screen">
            {/* Session Side Panel - Persistent across all pages */}
            <SessionSidePanel onToggle={handleSessionSidePanelToggle} isCollapsed={isSessionSidePanelCollapsed} />
            <main className="h-full w-full flex-1 overflow-auto">
                <Outlet />
            </main>
            <ToastContainer />
            <SelectionContextMenu isOpen={isMenuOpen} position={menuPosition} selectedText={selectedText || ""} onClose={clearSelection} />
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
