import { useState, useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { ToastContainer, Button } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { SessionSidePanel } from "@/lib/components/chat/SessionSidePanel";
import { ChatProvider } from "@/lib/providers";

import { useAuthContext, useBeforeUnload, useChatContext } from "@/lib/hooks";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { isMenuOpen, menuPosition, selectedText, clearSelection } = useTextSelection();
    const { handleNewSession } = useChatContext();

    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(false);

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

    // Keyboard shortcut for new chat (Cmd/Ctrl + K)
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Check for Cmd+K (Mac) or Ctrl+K (Windows/Linux)
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                // Navigate to chat page first
                navigate("/chat");
                // Then start new session
                handleNewSession();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [handleNewSession, navigate]);

    // Listen for navigation events from session panel
    useEffect(() => {
        const handleNavigateToAgents = () => {
            navigate("/agents");
        };

        const handleNavigateToChat = () => {
            navigate("/chat");
        };

        const handleNavigateToProjects = () => {
            navigate("/projects");
        };

        const handleNavigateToPrompts = () => {
            navigate("/prompts");
        };

        if (typeof window !== "undefined") {
            window.addEventListener("navigate-to-agents", handleNavigateToAgents as EventListener);
            window.addEventListener("navigate-to-chat", handleNavigateToChat as EventListener);
            window.addEventListener("navigate-to-projects", handleNavigateToProjects as EventListener);
            window.addEventListener("navigate-to-prompts", handleNavigateToPrompts as EventListener);
            return () => {
                window.removeEventListener("navigate-to-agents", handleNavigateToAgents as EventListener);
                window.removeEventListener("navigate-to-chat", handleNavigateToChat as EventListener);
                window.removeEventListener("navigate-to-projects", handleNavigateToProjects as EventListener);
                window.removeEventListener("navigate-to-prompts", handleNavigateToPrompts as EventListener);
            };
        }
    }, [navigate]);

    const handleSessionSidePanelToggle = () => {
        setIsSessionSidePanelCollapsed(!isSessionSidePanelCollapsed);
    };

    const getCurrentPage = (): "chat" | "agentMesh" | "projects" | "prompts" => {
        const path = location.pathname;
        if (path.startsWith("/agents")) return "agentMesh";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/prompts")) return "prompts";
        return "chat";
    };

    const handleNavigate = (page: string) => {
        if (page === "agentMesh") {
            navigate("/agents");
        } else if (page === "projects") {
            navigate("/projects");
        } else if (page === "prompts") {
            navigate("/prompts");
        } else {
            navigate("/chat");
        }
    };

    if (useAuthorization && !isAuthenticated) {
        return (
            <div className="bg-background flex h-screen items-center justify-center">
                <Button onClick={login}>Login</Button>
            </div>
        );
    }

    return (
        <div className={`relative flex h-screen`}>
            {/* Session Panel with integrated navigation */}
            <div className="absolute top-0 left-0 z-20 h-screen">
                <SessionSidePanel onToggle={handleSessionSidePanelToggle} currentPage={getCurrentPage()} isCollapsed={isSessionSidePanelCollapsed} onNavigate={handleNavigate} />
            </div>

            <main className={`h-full w-full flex-1 overflow-auto transition-all duration-300 ${isSessionSidePanelCollapsed ? "ml-16" : "ml-80"}`}>
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
