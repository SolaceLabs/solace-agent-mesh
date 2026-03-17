import type { Meta, StoryObj } from "@storybook/react-vite";
import { http, HttpResponse } from "msw";
import { FolderOpen, BookOpenText, Bot, User, LogOut, Files } from "lucide-react";

import { CollapsibleNavigationSidebar } from "@/lib/components/navigation/CollapsibleNavigationSidebar";
import { LifecycleBadge } from "@/lib/components/ui";
import type { NavItemConfig } from "@/lib/types/fe";
import { sessions } from "../data/sessions";

// ============================================================================
// Mock data — mirrors useNavigationItems with all features enabled
// ============================================================================

const defaultItems: NavItemConfig[] = [
    {
        id: "projects",
        label: "Projects",
        icon: FolderOpen,
        route: "/projects",
        routeMatch: "/projects",
        position: "top",
    },
    {
        id: "assets",
        label: "Assets",
        icon: BookOpenText,
        position: "top",
        children: [
            {
                id: "prompts",
                label: "Prompts",
                icon: BookOpenText,
                route: "/prompts",
                routeMatch: "/prompts",
                badge: <LifecycleBadge className="scale-90 text-(--darkSurface-textMuted)">EXPERIMENTAL</LifecycleBadge>,
            },
            {
                id: "artifacts",
                label: "Artifacts",
                icon: Files,
                route: "/artifacts",
                routeMatch: "/artifacts",
                badge: <LifecycleBadge className="scale-90 text-(--darkSurface-textMuted)">EXPERIMENTAL</LifecycleBadge>,
            },
        ],
    },
    {
        id: "agents",
        label: "Agents",
        icon: Bot,
        route: "/agents",
        routeMatch: "/agents",
        position: "top",
    },
    {
        id: "userAccount",
        label: "User Account",
        icon: User,
        onClick: () => {},
        position: "bottom",
    },
    {
        id: "logout",
        label: "Log Out",
        icon: LogOut,
        onClick: () => {},
        position: "bottom",
    },
];

const sessionHandlers = [
    http.get("/api/v1/sessions", () => {
        return HttpResponse.json({
            data: sessions,
            totalItems: sessions.length,
            totalPages: 1,
            currentPage: 1,
        });
    }),
];

const meta = {
    title: "Navigation/CollapsibleNavigationSidebar",
    component: CollapsibleNavigationSidebar,
    parameters: {
        layout: "fullscreen",
        msw: { handlers: sessionHandlers },
    },
    decorators: [
        Story => (
            <div style={{ height: "100vh", display: "flex" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof CollapsibleNavigationSidebar>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Expanded: Story = {
    args: {
        items: defaultItems,
        isCollapsed: false,
    },
};

export const Collapsed: Story = {
    args: {
        items: defaultItems,
        isCollapsed: true,
    },
};

export const WithActiveItem: Story = {
    args: {
        items: defaultItems,
        isCollapsed: false,
        activeItemId: "projects",
    },
};

export const WithSubmenus: Story = {
    args: {
        items: defaultItems.map(item => (item.id === "assets" ? { ...item, defaultExpanded: true } : item)),
        isCollapsed: false,
        activeItemId: "prompts",
    },
};

export const CustomHeader: Story = {
    args: {
        items: defaultItems,
        isCollapsed: false,
        header: (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 20, fontWeight: 700, color: "var(--darkSurface-text)" }}>Custom Logo</span>
            </div>
        ),
    },
};
