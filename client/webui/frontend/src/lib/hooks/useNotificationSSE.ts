/**
 * Hook that subscribes to the user-level notification SSE stream.
 *
 * The backend pushes events such as `session_created` when a scheduled task
 * execution creates a new chat session.  This hook listens for those events
 * and invalidates the relevant React Query caches directly so the session and
 * scheduled-task lists refetch immediately — no polling, no CustomEvent bus.
 *
 * Uses the shared SSEProvider for connection management, which handles
 * auth token injection, automatic reconnection with fresh tokens, and
 * exponential backoff.
 */
import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { scheduledTaskKeys } from "@/lib/api/scheduled-tasks/keys";
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
 * All three invalidate scheduled-task query caches so execution history and
 * task lists refetch.
 */
export function useNotificationSSE(): void {
    const queryClient = useQueryClient();

    const invalidateScheduledTasks = useCallback(() => {
        // Invalidate all scheduled-task caches (lists, details, executions,
        // recent-executions) so any mounted consumer refetches.
        queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.all });
    }, [queryClient]);

    const onSessionCreated = useCallback(() => {
        // Refresh the Recent Chats sidebar (still event-driven; session hooks
        // listen for this from multiple sources including ChatProvider).
        window.dispatchEvent(new CustomEvent("new-chat-session"));
        invalidateScheduledTasks();
    }, [invalidateScheduledTasks]);

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "session_created",
        onMessage: onSessionCreated,
    });

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "execution_queued",
        onMessage: invalidateScheduledTasks,
    });

    useSSESubscription({
        endpoint: "/api/v1/sse/notifications",
        eventType: "execution_started",
        onMessage: invalidateScheduledTasks,
    });
}
