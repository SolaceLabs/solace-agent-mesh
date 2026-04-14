/**
 * Hook that subscribes to the user-level notification SSE stream.
 *
 * The backend pushes events such as `session_created` when a scheduled task
 * execution creates a new chat session.  This hook listens for those events
 * and dispatches the corresponding window events so the session list hooks
 * (`useRecentSessions`, `useInfiniteSessions`) invalidate their caches
 * immediately — no polling required.
 */
import { useEffect, useRef } from "react";

import { api } from "@/lib/api";
import { getApiBearerToken } from "@/lib/utils/api";

/**
 * Establishes a persistent SSE connection to `/api/v1/sse/notifications`.
 *
 * When a `session_created` event arrives the hook dispatches a
 * `"new-chat-session"` CustomEvent on `window`, which the session list
 * hooks already listen for.
 *
 * The connection automatically reconnects on error with exponential backoff.
 */
export function useNotificationSSE(): void {
    const eventSourceRef = useRef<EventSource | null>(null);
    const retryCountRef = useRef(0);
    const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        let unmounted = false;

        const connect = () => {
            if (unmounted) return;

            const baseUrl = api.webui.getFullUrl("/api/v1/sse/notifications");
            const token = getApiBearerToken();
            const url = token ? `${baseUrl}?token=${token}` : baseUrl;

            const es = new EventSource(url, { withCredentials: true });
            eventSourceRef.current = es;

            es.onopen = () => {
                retryCountRef.current = 0;
            };

            // Listen for session_created events from the scheduler
            es.addEventListener("session_created", () => {
                window.dispatchEvent(new CustomEvent("new-chat-session"));
            });

            es.onerror = () => {
                es.close();
                eventSourceRef.current = null;

                if (unmounted) return;

                // Exponential backoff: 2s, 4s, 8s, … capped at 30s
                const delay = Math.min(2000 * 2 ** retryCountRef.current, 30_000);
                retryCountRef.current += 1;
                retryTimerRef.current = setTimeout(connect, delay);
            };
        };

        connect();

        return () => {
            unmounted = true;
            if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
            }
        };
    }, []);
}
