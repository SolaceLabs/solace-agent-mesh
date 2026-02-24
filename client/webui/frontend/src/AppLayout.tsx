import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationSidebar, CollapsibleNavigationSidebar, ToastContainer, bottomNavigationItems, getTopNavigationItems, EmptyState, SAM_NAV_ITEMS, SAM_BOTTOM_ITEMS, filterNavItems, filterBottomItems } from "@/lib/components";
import { SelectionContextMenu, useTextSelection } from "@/lib/components/chat/selection";
import { ChatProvider } from "@/lib/providers";
import { useAuthContext, useBeforeUnload, useConfigContext } from "@/lib/hooks";

function AppLayoutContent() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isAuthenticated, login, useAuthorization } = useAuthContext();
    const { configFeatureEnablement } = useConfigContext();
    const { isMenuOpen, menuPosition, selectedText, sourceTaskId, clearSelection } = useTextSelection();

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

    // Get navigation items based on feature flags
    const topNavItems = getTopNavigationItems(configFeatureEnablement);

    // Feature flag for new collapsible navigation
    const useNewNav = configFeatureEnablement?.newNavigation ?? false;

    // Feature flags for new navigation
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const logoutEnabled = configFeatureEnablement?.logout ?? false;

    // Filter SAM nav items based on feature flags
    const filteredNavItems = filterNavItems(SAM_NAV_ITEMS, { projects: projectsEnabled });
    const filteredBottomItems = filterBottomItems(SAM_BOTTOM_ITEMS, { logout: logoutEnabled });

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
                <CollapsibleNavigationSidebar navItems={filteredNavItems} bottomItems={filteredBottomItems} showNewChatButton />
            ) : (
                <NavigationSidebar items={topNavItems} bottomItems={bottomNavigationItems} activeItem={getActiveItem()} onItemChange={handleNavItemChange} onHeaderClick={handleHeaderClick} />
            )}
            <main className="h-full w-full flex-1 overflow-auto">
                <Outlet />
            </main>
            <ToastContainer />
            <SelectionContextMenu isOpen={isMenuOpen} position={menuPosition} selectedText={selectedText || ""} sourceTaskId={sourceTaskId} onClose={clearSelection} />
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
