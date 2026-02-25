import { useMemo } from "react";
import { useLocation } from "react-router-dom";
import { FolderOpen, BookOpenText, Bot, User, LogOut } from "lucide-react";
import { LifecycleBadge } from "@/lib/components/ui";
import type { NavItemConfig } from "@/lib/types/fe";

interface UseNavigationItemsProps {
    projectsEnabled: boolean;
    promptLibraryEnabled: boolean;
    logoutEnabled: boolean;
    isAuthenticated: boolean;
    onUserAccountClick: () => void;
    onLogoutClick: () => void;
}

export function useNavigationItems({ projectsEnabled, promptLibraryEnabled, logoutEnabled, isAuthenticated, onUserAccountClick, onLogoutClick }: UseNavigationItemsProps) {
    const location = useLocation();

    const items = useMemo((): NavItemConfig[] => {
        const navItems: NavItemConfig[] = [];

        if (projectsEnabled) {
            navItems.push({
                id: "projects",
                label: "Projects",
                icon: FolderOpen,
                route: "/projects",
                routeMatch: "/projects",
                position: "top",
            });
        }

        if (promptLibraryEnabled) {
            navItems.push({
                id: "assets",
                label: "Assets",
                icon: BookOpenText,
                children: [
                    {
                        id: "prompts",
                        label: "Prompts",
                        icon: BookOpenText,
                        route: "/prompts",
                        routeMatch: "/prompts",
                        badge: <LifecycleBadge className="scale-90">EXPERIMENTAL</LifecycleBadge>,
                    },
                ],
                position: "top",
            });
        }

        navItems.push({
            id: "agents",
            label: "Agents",
            icon: Bot,
            route: "/agents",
            routeMatch: "/agents",
            position: "top",
        });

        navItems.push({
            id: "userAccount",
            label: "User Account",
            icon: User,
            onClick: onUserAccountClick,
            position: "bottom",
        });

        if (logoutEnabled && isAuthenticated) {
            navItems.push({
                id: "logout",
                label: "Log Out",
                icon: LogOut,
                onClick: onLogoutClick,
                position: "bottom",
            });
        }

        return navItems;
    }, [projectsEnabled, promptLibraryEnabled, logoutEnabled, isAuthenticated, onUserAccountClick, onLogoutClick]);

    const activeItemId = useMemo((): string => {
        const path = location.pathname;
        if (path === "/" || path.startsWith("/chat")) return "chats";
        if (path.startsWith("/projects")) return "projects";
        if (path.startsWith("/prompts")) return "prompts";
        if (path.startsWith("/agents")) return "agents";
        return "chats";
    }, [location.pathname]);

    return { items, activeItemId };
}
