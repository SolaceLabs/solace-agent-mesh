import { MessageCircle, Bot, SunMoon, Command } from "lucide-react";

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
        id: "prompts",
        label: "Prompts",
        icon: Command,
    },
];

export const bottomNavigationItems: NavigationItem[] = [
    {
        id: "theme-toggle",
        label: "Theme",
        icon: SunMoon,
        onClick: () => {}, // Will be handled in NavigationList
    },
];
