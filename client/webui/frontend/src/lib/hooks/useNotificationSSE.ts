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
 * Listens for:
 * - `execution_queued` — dispatched immediately after a PENDING execution row
 *   is inserted. Essential for fast-running tasks; without this the history
 *   list would race the row creation and appear empty until completion.
 * - `execution_started` — dispatched when an execution transitions to RUNNING.
 * - `session_created` — dispatched when an execution creates a chat session
 *   (usually at completion). Also triggers `"new-chat-session"` for the
 *   Recent Chats sidebar.
 *
 * All three trigger `"scheduled-task-completed"` so the execution history
 * queries refetch.
 */
export function useNotificationSSE(): void {
    const onSessionCreated = useCallback(() => {
        // Refresh the Recent Chats sidebar
        window.dispatchEvent(new CustomEvent("new-chat-session"));
        // Refresh the execution history list on the scheduled tasks page
        window.dispatchEvent(new CustomEvent("scheduled-task-completed"));
    }, []);

    const onExecutionActivity = useCallback(() => {
        // Refresh the execution history so the new/updated row appears.
        window.dispatchEvent(new CustomEvent("scheduled-task-completed"));
    }, []);

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "session_created",
        onMessage: onSessionCreated,
    });

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "execution_queued",
        onMessage: onExecutionActivity,
    });

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "execution_started",
        onMessage: onExecutionActivity,
    });
}
