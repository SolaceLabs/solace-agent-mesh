import { useEffect, useState, useCallback } from "react";
import { Outlet } from "react-router-dom";

import { ToastContainer, EmptyState, NavigationSidebar } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { ChatProvider } from "@/lib/providers";
import { useAuthContext, useBeforeUnload } from "@/lib/hooks";

const NAV_COLLAPSED_STORAGE_KEY = "sam-nav-collapsed";

function AppLayoutContent() {
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { isMenuOpen, menuPosition, selectedText, clearSelection } = useTextSelection();

    // Initialize from localStorage, default to expanded (false)
    const [isNavCollapsed, setIsNavCollapsed] = useState(() => {
        if (typeof window !== "undefined") {
            const stored = localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY);
            // If stored value exists, use it; otherwise default to expanded (false)
            return stored !== null ? stored === "true" : false;
        }
        return false; // Default to expanded
    });

    const handleNavToggle = useCallback(() => {
        setIsNavCollapsed(prev => {
            const newValue = !prev;
            // Persist to localStorage
            if (typeof window !== "undefined") {
                localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, String(newValue));
            }
            return newValue;
        });
    }, []);

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
            {/* Navigation Sidebar - Persistent across all pages */}
            <NavigationSidebar onToggle={handleNavToggle} isCollapsed={isNavCollapsed} />
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
