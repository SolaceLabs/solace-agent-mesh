import { useChatSurface } from "./useChatSurface";

/**
 * The route to navigate to when opening a chat. In the embedded surface this stays on
 * `/agent-mode/chat?agent=<pinned>` so the URL keeps the embedded route + pinned agent (survives
 * a refresh and back/forward); in the full UI it's the normal `/chat`.
 */
export function useChatRoute(): string {
    const surface = useChatSurface();
    if (surface.variant !== "embedded") return "/chat";
    return surface.pinnedAgent ? `/agent-mode/chat?agent=${encodeURIComponent(surface.pinnedAgent)}` : "/agent-mode/chat";
}
