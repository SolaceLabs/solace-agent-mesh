/**
 * Custom hook for SSE error recovery with token refresh.
 *
 * Extracted from ChatProvider to enable independent testing.
 * Handles the logic of attempting a token refresh when an SSE connection
 * errors out (typically due to expired tokens), and triggering a reconnect.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { refreshToken } from "@/lib/api";

export interface SseErrorRecoveryCallbacks {
    /** Called to close the current EventSource before attempting refresh. */
    closeCurrentEventSource: () => void;
    /** Called to show an error dialog to the user. */
    setError: (error: { title: string; error: string }) => void;
    /** Called to set the responding state. */
    setIsResponding: (responding: boolean) => void;
    /** Called to clear the current task ID. */
    setCurrentTaskId: (taskId: string | null) => void;
    /** Called to clean up messages (remove status bubbles, mark last as complete). */
    cleanupMessages: () => void;
}

export interface SseErrorRecoveryState {
    /** Whether the system is currently responding to a user request. */
    isResponding: boolean;
    /** Whether the response is being finalized. */
    isFinalizing: React.RefObject<boolean>;
    /** Whether a cancellation is in progress. */
    isCancelling: React.RefObject<boolean>;
    /** The current task ID. */
    currentTaskId: string | null;
}

export interface SseErrorRecoveryResult {
    /** The SSE reconnect key — add to EventSource useEffect deps to trigger reconnect. */
    sseReconnectKey: number;
    /** The SSE error handler to attach to EventSource.onerror. */
    handleSseError: () => void;
    /** Clean up SSE-related state after a connection failure. */
    cleanupSseFailure: (title: string, message: string) => void;
}

export function useSseErrorRecovery(state: SseErrorRecoveryState, callbacks: SseErrorRecoveryCallbacks): SseErrorRecoveryResult {
    const { isResponding, isFinalizing, isCancelling, currentTaskId } = state;
    const { closeCurrentEventSource, setError, setIsResponding, setCurrentTaskId, cleanupMessages } = callbacks;

    // Track whether we've already attempted an SSE token refresh for the
    // current task to avoid infinite retry loops.
    const sseRefreshAttempted = useRef(false);
    // Track the task ID that the refresh guard applies to, so we only reset
    // the guard when a genuinely *new* task starts (not on reconnect bumps).
    const sseRefreshTaskId = useRef<string | null>(null);

    // Reconnect counter — incrementing this triggers the EventSource useEffect
    // to tear down and rebuild the connection without changing currentTaskId.
    const [sseReconnectKey, setSseReconnectKey] = useState(0);

    // Reset the refresh-attempted flag only when a genuinely new task starts
    useEffect(() => {
        if (currentTaskId && currentTaskId !== sseRefreshTaskId.current) {
            sseRefreshAttempted.current = false;
            sseRefreshTaskId.current = currentTaskId;
        }
    }, [currentTaskId]);

    /** Clean up SSE-related state after a connection failure. */
    const cleanupSseFailure = useCallback(
        (title: string, message: string) => {
            setError({ title, error: message });
            setIsResponding(false);
            setCurrentTaskId(null);
            cleanupMessages();
        },
        [setError, setIsResponding, setCurrentTaskId, cleanupMessages]
    );

    const handleSseError = useCallback(() => {
        // If we haven't tried refreshing the token yet for this SSE connection,
        // attempt a refresh and reconnect instead of immediately failing.
        // This handles the case where the token expired during a long-lived SSE stream.
        if (!sseRefreshAttempted.current && currentTaskId && isResponding && !isFinalizing.current && !isCancelling.current) {
            sseRefreshAttempted.current = true;
            console.log("[useSseErrorRecovery] SSE error — attempting token refresh before reconnect");
            closeCurrentEventSource();

            void refreshToken()
                .then(newToken => {
                    // Use the ref instead of the closed-over currentTaskId to avoid
                    // stale closure issues if the task changed during the async refresh.
                    const taskId = sseRefreshTaskId.current;
                    if (newToken && taskId) {
                        console.log("[useSseErrorRecovery] Token refreshed, reconnecting SSE for task", taskId);
                        // Bump the reconnect key to trigger the EventSource useEffect
                        // without changing currentTaskId. This avoids the React 18
                        // batching issue with null → restore tricks.
                        setSseReconnectKey(k => k + 1);
                    } else {
                        console.warn("[useSseErrorRecovery] Token refresh failed during SSE error");
                        cleanupSseFailure("Connection Failed", "Session expired. Please log in again.");
                    }
                })
                .catch(err => {
                    console.error("[useSseErrorRecovery] Unexpected error during SSE token refresh:", err);
                    cleanupSseFailure("Connection Failed", "Connection lost. Please try again.");
                });
            return;
        }

        if (isResponding && !isFinalizing.current && !isCancelling.current) {
            setError({ title: "Connection Failed", error: "Connection lost. Please try again." });
        }
        if (!isFinalizing.current) {
            setIsResponding(false);
            if (!isCancelling.current) {
                closeCurrentEventSource();
                setCurrentTaskId(null);
            }
        }
        cleanupMessages();
    }, [closeCurrentEventSource, isResponding, setError, currentTaskId, cleanupSseFailure, isFinalizing, isCancelling, setIsResponding, setCurrentTaskId, cleanupMessages]);

    return {
        sseReconnectKey,
        handleSseError,
        cleanupSseFailure,
    };
}
