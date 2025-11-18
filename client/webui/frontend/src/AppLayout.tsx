import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationSidebar, ToastContainer, Button, bottomNavigationItems, getTopNavigationItems } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { ChatProvider } from "@/lib/providers";

import { useAuthContext, useBeforeUnload, useConfigContext, useAudioSettings } from "@/lib/hooks";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { configFeatureEnablement } = useConfigContext();
    const { isMenuOpen, menuPosition, selectedText, clearSelection } = useTextSelection();
    const { settings } = useAudioSettings();

    // Get navigation items based on feature flags
    const topNavItems = getTopNavigationItems(configFeatureEnablement);

    // Enable beforeunload warning when chat data is present
    useBeforeUnload();

    // Apply font size to document root
    useEffect(() => {
        const fontSizeMap = {
            small: "14px",
            medium: "16px",
            large: "18px",
            "extra-large": "20px",
        };
        document.documentElement.style.fontSize = fontSizeMap[settings.fontSize];
    }, [settings.fontSize]);

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
            <div className="bg-background flex h-screen items-center justify-center">
                <Button onClick={login}>Login</Button>
            </div>
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
            <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
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
