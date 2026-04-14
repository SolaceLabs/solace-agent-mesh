/**
 * Hook that subscribes to the user-level notification SSE stream.
 *
 * The backend pushes events such as `session_created` when a scheduled task
 * execution creates a new chat session.  This hook listens for those events
 * and dispatches the corresponding window events so the session list hooks
 * (`useRecentSessions`, `useInfiniteSessions`) invalidate their caches
 * immediately — no polling required.
 *
 * Uses the shared SSEProvider for connection management, which handles
 * auth token injection, automatic reconnection with fresh tokens, and
 * exponential backoff.
 */
import { useCallback } from "react";

import { useSSESubscription } from "@/lib/providers/SSEProvider";

/**
 * Establishes a persistent SSE connection to `/api/v1/sse/notifications`.
 *
 * When a `session_created` event arrives the hook dispatches a
 * `"new-chat-session"` CustomEvent on `window`, which the session list
 * hooks already listen for.
 *
 * The connection automatically reconnects on error with exponential backoff
 * and refreshes the auth token on each reconnect attempt.
 */
export function useNotificationSSE(): void {
    const onMessage = useCallback(() => {
        window.dispatchEvent(new CustomEvent("new-chat-session"));
    }, []);

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "session_created",
        onMessage,
    });
}
