import React, { useState, type ReactNode } from "react";

import { ChatSurfaceContext, FULL_CHAT_SURFACE, type ChatSurface, type SessionAction } from "@/lib/contexts/ChatSurfaceContext";
import { getHashPath, getHashQueryParams } from "@/lib/utils/url";

const EMBEDDED_SESSION_ACTIONS: ReadonlyArray<SessionAction> = ["rename", "renameWithAI", "delete"];

/** The hash-route path that renders the embedded, single-agent surface. */
export const EMBEDDED_ROUTE_PATH = "/embed/chat";

/**
 * Compute the chat surface once at load from the hash-route path. Read-once (no
 * full-UI flash, no later recompute), so the pinned agent is stable even if
 * in-app navigation later strips the hash query.
 */
function computeChatSurface(): ChatSurface {
    const embedded = getHashPath() === EMBEDDED_ROUTE_PATH;

    if (!embedded) {
        return FULL_CHAT_SURFACE;
    }

    return {
        variant: "embedded",
        navigation: ["recentChats"],
        showAgentSelector: false,
        showActivityPanel: false,
        allowPrompts: false,
        // Mentions are collaboration, not agent routing, so they stay on: the
        // embedded surface is a UI-only default entry point, not an isolation boundary.
        allowMentions: true,
        pinnedAgent: getHashQueryParams().get("agent"),
        seedWelcomeBubble: false,
        sessionActions: EMBEDDED_SESSION_ACTIONS,
    };
}

interface ChatSurfaceProviderProps {
    children: ReactNode;
}

export const ChatSurfaceProvider: React.FC<ChatSurfaceProviderProps> = ({ children }) => {
    // useState initializer runs exactly once — the surface is fixed for the session.
    const [surface] = useState<ChatSurface>(computeChatSurface);
    return <ChatSurfaceContext.Provider value={surface}>{children}</ChatSurfaceContext.Provider>;
};
