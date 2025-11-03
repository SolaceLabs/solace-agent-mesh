import { useState, useMemo, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";

import { AgentMeshPage, ChatPage, bottomNavigationItems, getTopNavigationItems, NavigationSidebar, ToastContainer, Button } from "@/lib/components";
import { ProjectsPage } from "@/lib/components/projects";
import { AuthProvider, ChatProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider } from "@/lib/providers";

import { useAuthContext, useBeforeUnload, useConfigContext } from "@/lib/hooks";

function AppContent() {
    const [activeNavItem, setActiveNavItem] = useState<string>("chat");
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { projectsEnabled } = useConfigContext();

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

    // Get filtered navigation items based on feature flags
    const topNavigationItems = useMemo(() => {
        return getTopNavigationItems(projectsEnabled ?? false);
    }, [projectsEnabled]);

    if (useAuthorization && !isAuthenticated) {
        return (
            <div className="bg-background flex h-screen items-center justify-center">
                <Button onClick={login}>Login</Button>
            </div>
        );
    }

    const handleNavItemChange = (itemId: string) => {
        const item = topNavigationItems.find(item => item.id === itemId) || bottomNavigationItems.find(item => item.id === itemId);

        if (item?.onClick && itemId !== "settings") {
            item.onClick();
        } else if (itemId !== "settings") {
            setActiveNavItem(itemId);
        }
    };

    const handleHeaderClick = () => {
        setActiveNavItem("chat");
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
        }
    };

    return (
        <div className={`relative flex h-screen`}>
            <NavigationSidebar items={topNavigationItems} bottomItems={bottomNavigationItems} activeItem={activeNavItem} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
            <main className="h-full w-full flex-1 overflow-auto">{renderMainContent()}</main>
            <ToastContainer />
        </div>
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
