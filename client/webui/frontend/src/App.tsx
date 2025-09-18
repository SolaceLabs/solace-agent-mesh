import { useState } from "react";

import { AgentMeshPage, ChatPage, bottomNavigationItems, topNavigationItems, NavigationSidebar, ToastContainer, Button } from "@/lib/components";
import { AuthProvider, ChatProvider, ConfigProvider, CsrfProvider, TaskProvider, ThemeProvider } from "@/lib/providers";

import { useAuthContext, useBeforeUnload } from "@/lib/hooks";

function AppContent() {
    const [activeNavItem, setActiveNavItem] = useState<string>("chat");
    const { isAuthenticated, login, useAuthorization } = useAuthContext();

    // Enable beforeunload warning when chat data is present
    useBeforeUnload();

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
                        <ChatProvider>
                            <TaskProvider>
                                <AppContent />
                            </TaskProvider>
                        </ChatProvider>
                    </AuthProvider>
                </ConfigProvider>
            </CsrfProvider>
        </ThemeProvider>
    );
}

export default App;
