import { MessageCircle, Bot, SunMoon, PanelsTopLeft } from "lucide-react";

import type { NavigationItem } from "@/lib/types";

export const topNavigationItems: NavigationItem[] = [
    {
        id: "chat",
        label: "Chat",
        icon: MessageCircle,
    },
    {
        id: "agentMesh",
        label: "Agents",
        icon: Bot,
    },
    {
        id: "projects",
        label: "Projects",
        icon: PanelsTopLeft,
    }
];

export const bottomNavigationItems: NavigationItem[] = [
    {
        id: "theme-toggle",
        label: "Theme",
        icon: SunMoon,
        onClick: () => {}, // Will be handled in NavigationList
    },
];
