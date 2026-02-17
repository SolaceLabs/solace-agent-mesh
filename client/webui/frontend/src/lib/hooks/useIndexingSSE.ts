import { useCallback, useEffect, useRef, useState } from "react";
import { useSSEContext } from "./useSSEContext";
import { useSSESubscription } from "@/lib/providers";
import type { SSEConnectionState } from "@/lib/types";

/**
 * SSE event received during indexing operations.
 * @property type - The event type identifier
 */
export interface IndexingSSEEvent {
    type: string;
    [key: string]: unknown;
}

/**
 * Options for the useIndexingSSE hook.
 * @property resourceId - Resource ID to find existing tasks (e.g., projectId)
 * @property metadataKey - Metadata key to search for existing tasks
 * @property onComplete - Called when indexing completes successfully
 * @property onError - Called when indexing fails
 * @property onEvent - Called for each SSE event (for custom handling)
 */
export interface UseIndexingSSEOptions {
    resourceId: string;
    metadataKey?: string;
    onComplete?: () => void;
    onError?: (error: string) => void;
    onEvent?: (event: IndexingSSEEvent) => void;
}

/**
 * Return value from the useIndexingSSE hook.
 * @property connectionState - Current SSE connection state
 * @property isConnected - Whether currently connected
 * @property isIndexing - Whether an indexing task is active
 * @property latestEvent - Most recent SSE event received
 * @property startIndexing - Register a new indexing task from SSE location header
 */
export interface UseIndexingSSEReturn {
    connectionState: SSEConnectionState;
    isConnected: boolean;
    isIndexing: boolean;
    latestEvent: IndexingSSEEvent | null;
    startIndexing: (sseLocation: string, operation?: string) => void;
}

/**
 * Hook for subscribing to indexing SSE events.
 *
 * Handles:
 * - Finding existing tasks for a resource (from sessionStorage)
 * - Subscribing to SSE events
 * - Logging events to console
 * - Cleaning up on task completion
 *
 * @example
 * ```tsx
 * const { isIndexing, startIndexing, connectionState } = useIndexingSSE({
 *     resourceId: project.id,
 *     onComplete: () => refetchArtifacts(),
 * });
 *
 * const handleUpload = async (files) => {
 *     const result = await uploadFiles(files);
 *     if (result.sseLocation) {
 *         startIndexing(result.sseLocation, "upload");
 *     }
 * };
 * ```
 */
export function useIndexingSSE(options: UseIndexingSSEOptions): UseIndexingSSEReturn {
    const { resourceId, metadataKey = "projectId", onComplete, onError, onEvent } = options;

    const { registerTask, unregisterTask, getTasksByMetadata } = useSSEContext();
    const [latestEvent, setLatestEvent] = useState<IndexingSSEEvent | null>(null);

    // Store callbacks in refs to avoid stale closures
    const onCompleteRef = useRef(onComplete);
    const onErrorRef = useRef(onError);
    const onEventRef = useRef(onEvent);
    useEffect(() => {
        onCompleteRef.current = onComplete;
        onErrorRef.current = onError;
        onEventRef.current = onEvent;
    });

    // Task registry is the single source of truth
    const existingTask = getTasksByMetadata(metadataKey, resourceId)[0] ?? null;
    const taskId = existingTask?.taskId ?? null;
    const sseUrl = existingTask?.sseUrl ?? null;

    const handleTaskComplete = useCallback(
        (success: boolean, errorMessage?: string) => {
            setLatestEvent(null);
            if (taskId) {
                unregisterTask(taskId);
            }

            if (success) {
                onCompleteRef.current?.();
            } else if (errorMessage) {
                onErrorRef.current?.(errorMessage);
            }
        },
        [taskId, unregisterTask]
    );

    const { connectionState, isConnected } = useSSESubscription({
        endpoint: sseUrl,
        eventType: "index_message",
        onMessage: event => {
            try {
                const data = JSON.parse(event.data) as IndexingSSEEvent;

                setLatestEvent(data);
                onEventRef.current?.(data);

                // Handle terminal events
                if (data.type === "task_completed") {
                    handleTaskComplete(true);
                } else if (data.type === "conversion_failed" || data.type === "indexing_failed") {
                    const errorMsg = typeof data.error === "string" ? data.error : "Indexing failed";
                    console.error("[useIndexingSSE] Task error:", errorMsg);
                    handleTaskComplete(false, errorMsg);
                }
            } catch (e) {
                console.error("[useIndexingSSE] Failed to parse event:", e);
            }
        },
        onError: event => {
            console.error("[useIndexingSSE] Connection error:", event);
        },
    });

    // Start a new indexing task
    const startIndexing = useCallback(
        (sseLocation: string, operation = "unknown") => {
            // Extract task ID from URL (e.g., "/api/v1/sse/subscribe/indexing_upload_xxx")
            const newTaskId = sseLocation.split("/").pop();
            if (newTaskId) {
                registerTask({
                    taskId: newTaskId,
                    sseUrl: sseLocation,
                    metadata: { [metadataKey]: resourceId, operation },
                });
            }
        },
        [registerTask, metadataKey, resourceId]
    );

    return {
        connectionState,
        isConnected,
        isIndexing: taskId !== null,
        latestEvent,
        startIndexing,
    };
}
