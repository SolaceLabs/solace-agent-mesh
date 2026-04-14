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
 * Listens for two event types:
 * - `session_created` — dispatched when a scheduled task completes and creates a chat session
 * - `execution_started` — dispatched when a scheduled task execution begins running
 *
 * Both trigger `"scheduled-task-completed"` to refresh execution history.
 * `session_created` also triggers `"new-chat-session"` for the Recent Chats sidebar.
 */
export function useNotificationSSE(): void {
    const onSessionCreated = useCallback(() => {
        // Refresh the Recent Chats sidebar
        window.dispatchEvent(new CustomEvent("new-chat-session"));
        // Refresh the execution history list on the scheduled tasks page
        window.dispatchEvent(new CustomEvent("scheduled-task-completed"));
    }, []);

    const onExecutionStarted = useCallback(() => {
        // Refresh the execution history to show "running" status
        window.dispatchEvent(new CustomEvent("scheduled-task-completed"));
    }, []);

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "session_created",
        onMessage: onSessionCreated,
    });

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "execution_started",
        onMessage: onExecutionStarted,
    });
}
