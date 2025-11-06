import { useState, useMemo, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";

import { AgentMeshPage, ChatPage, bottomNavigationItems, getTopNavigationItems, NavigationSidebar, ToastContainer, Button } from "@/lib/components";
import { ProjectsPage } from "@/lib/components/projects";
import { PromptsPage } from "@/lib/components/pages/PromptsPage";
import { TextSelectionProvider, SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { AuthProvider, ChatProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider } from "@/lib/providers";
import { UnsavedChangesProvider, useUnsavedChangesContext } from "@/lib/contexts";

import { useAuthContext, useBeforeUnload, useConfigContext } from "@/lib/hooks";

function AppContentInner() {
    const [activeNavItem, setActiveNavItem] = useState<string>("chat");
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { configFeatureEnablement, projectsEnabled } = useConfigContext();
    const { isMenuOpen, menuPosition, selectedText, clearSelection } = useTextSelection();
    const { checkUnsavedChanges } = useUnsavedChangesContext();

    // Get navigation items based on feature flags
    const topNavItems = useMemo(
        () => getTopNavigationItems(configFeatureEnablement),
        [configFeatureEnablement]
    );

    // Enable beforeunload warning when chat data is present
    useBeforeUnload();

    // Listen for navigate-to-project events
    useEffect(() => {
        const handleNavigateToProject = (event: CustomEvent) => {
            if (projectsEnabled && !event.detail.handled) {
                setActiveNavItem("projects");
                setTimeout(() => {
                    window.dispatchEvent(new CustomEvent("navigate-to-project", {
                        detail: { ...event.detail, handled: true }
                    }));
                }, 100);
            }
        };

        window.addEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        return () => {
            window.removeEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        };
    }, [projectsEnabled]);

    // Listen for create-template-from-session events
    useEffect(() => {
        const handleCreateTemplateFromSession = () => {
            setActiveNavItem("prompts");
        };

        window.addEventListener("create-template-from-session", handleCreateTemplateFromSession);
        return () => {
            window.removeEventListener("create-template-from-session", handleCreateTemplateFromSession as EventListener);
        };
    }, []);

    // Listen for use-prompt-in-chat events
    useEffect(() => {
        const handleUsePromptInChat = () => {
            setActiveNavItem("chat");
        };

        window.addEventListener("use-prompt-in-chat", handleUsePromptInChat);
        return () => {
            window.removeEventListener("use-prompt-in-chat", handleUsePromptInChat as EventListener);
        };
    }, []);

    if (useAuthorization && !isAuthenticated) {
        return (
            <div className="bg-background flex h-screen items-center justify-center">
                <Button onClick={login}>Login</Button>
            </div>
        );
    }

    const handleNavItemChange = (itemId: string) => {
        // Check for unsaved changes before navigating
        checkUnsavedChanges(() => {
            const item = topNavItems.find(item => item.id === itemId) || bottomNavigationItems.find(item => item.id === itemId);

            if (item?.onClick && itemId !== "settings") {
                item.onClick();
            } else if (itemId !== "settings") {
                setActiveNavItem(itemId);
            }
        });
    };

    const handleHeaderClick = () => {
        // Check for unsaved changes before navigating to chat
        checkUnsavedChanges(() => {
            setActiveNavItem("chat");
        });
    };

    const renderMainContent = () => {
        switch (activeNavItem) {
            case "chat":
                return <ChatPage />;
            case "agentMesh":
                return <AgentMeshPage />;
            case "projects":
                // Only render ProjectsPage if projects are enabled
                if (projectsEnabled) {
                    return <ProjectsPage onProjectActivated={() => setActiveNavItem("chat")} />;
                }
                // Fallback to chat if projects are disabled but somehow navigated here
                return <ChatPage />;
            case "prompts":
                return <PromptsPage />;
            default:
                return <ChatPage />;
        }
    };

    return (
        <div className={`relative flex h-screen`}>
            <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={activeNavItem} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
            <main className="h-full w-full flex-1 overflow-auto">{renderMainContent()}</main>
            <ToastContainer />
            <SelectionContextMenu
                isOpen={isMenuOpen}
                position={menuPosition}
                selectedText={selectedText || ''}
                onClose={clearSelection}
            />
        </div>
    );
}

function AppContent() {
    return (
        <UnsavedChangesProvider>
            <TextSelectionProvider>
                <AppContentInner />
            </TextSelectionProvider>
        </UnsavedChangesProvider>
    );
}

function App() {
    return (
        <ThemeProvider>
            <CsrfProvider>
                <ConfigProvider>
                    <AuthProvider>
                        <ProjectProvider>
                            <BrowserRouter>
                                <ChatProvider>
                                    <TaskProvider>
                                        <AppContent />
                                    </TaskProvider>
                                </ChatProvider>
                            </BrowserRouter>
                        </ProjectProvider>
                    </AuthProvider>
                </ConfigProvider>
            </CsrfProvider>
        </ThemeProvider>
    );
}

export default App;
