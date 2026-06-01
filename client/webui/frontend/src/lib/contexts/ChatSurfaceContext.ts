import { createContext } from "react";

/**
 * A session-menu action key. The set a surface allows is rendered in a fixed
 * canonical order by SessionActionMenu — adding an action to the menu means
 * adding it to the relevant surface's `sessionActions`, not editing a branch.
 */
export type SessionAction = "goToProject" | "rename" | "renameWithAI" | "move" | "share" | "delete";

/**
 * A navigation-sidebar section.
 * - `newChat` — the New Chat button (new nav only)
 * - `appNav` — the app-level nav items (Chat/Projects/Artifacts/Agents/…); the legacy
 *   icon rail is entirely app-nav, so it renders only when this section is allowed
 * - `recentChats` — the Recent Chats list (new nav only)
 */
export type NavSection = "newChat" | "appNav" | "recentChats";

/**
 * The single source of truth for which chrome the chat UI exposes.
 *
 * Components read *intent* (e.g. `showActivityPanel`) rather than the activation
 * mechanism, so suppression decisions live here in one struct instead of being
 * threaded as scattered `if (embedded)` checks. The activation mechanism (today the
 * `/embed/chat` route) can change without touching consumers.
 *
 * Derived once at load from the hash route (`/#/embed/chat?agent=Foo`), never
 * persisted, and deliberately NOT part of server config — so an admin on the same
 * origin can't inherit a sticky embedded surface.
 */
export interface ChatSurface {
    /** "full" = the standard web UI; "embedded" = chat-only, single-agent. */
    variant: "full" | "embedded";
    /**
     * Which navigation sections the sidebar exposes. The new nav renders each allowed
     * section (header always kept); the legacy icon rail is pure app-nav, so it renders
     * only when `appNav` is allowed and nothing otherwise. `[]` means no sidebar at all.
     * Embedded uses `["recentChats"]` — chat navigation only, no New Chat or app nav.
     */
    navigation: ReadonlyArray<NavSection>;
    /** Render the agent selector dropdown in the chat input. */
    showAgentSelector: boolean;
    /** Render the Activity tab/icon and the per-message "View activity" button. */
    showActivityPanel: boolean;
    /** Allow the "/" prompt-library popover. */
    allowPrompts: boolean;
    /** Allow the "@" mention popover (collaboration, not agent routing). */
    allowMentions: boolean;
    /**
     * Wire name of the agent this surface is pinned to, captured once at load.
     * Stable across in-app navigation that strips the hash query. null in "full".
     */
    pinnedAgent: string | null;
    /** Seed the left-aligned welcome bubble. false in "embedded" — the centered hero owns the empty state. */
    seedWelcomeBubble: boolean;
    /** Which session-action-menu items this surface exposes. */
    sessionActions: ReadonlyArray<SessionAction>;
}

/** The standard, unconstrained web UI. Also the context default: absence of a provider means full capabilities. */
export const FULL_CHAT_SURFACE: ChatSurface = {
    variant: "full",
    navigation: ["newChat", "appNav", "recentChats"],
    showAgentSelector: true,
    showActivityPanel: true,
    allowPrompts: true,
    allowMentions: true,
    pinnedAgent: null,
    seedWelcomeBubble: true,
    sessionActions: ["goToProject", "rename", "renameWithAI", "move", "share", "delete"],
};

export const ChatSurfaceContext = createContext<ChatSurface>(FULL_CHAT_SURFACE);
