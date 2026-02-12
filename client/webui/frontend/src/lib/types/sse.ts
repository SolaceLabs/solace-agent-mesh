// ============ Types ============

export type SSEConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";

export interface SSETask {
    /** Unique task identifier from backend */
    taskId: string;
    /** SSE endpoint URL for this task */
    sseUrl: string;
    /** Feature-specific metadata for querying */
    metadata?: Record<string, unknown>;
    /** When the task was registered */
    registeredAt: number;
}

export interface SSESubscriptionOptions {
    /** SSE endpoint. null = don't connect */
    endpoint: string | null;
    /** Optional task ID for status-check-on-reconnect behavior */
    taskId?: string;
    /** Called when message received */
    onMessage?: (event: MessageEvent) => void;
    /** Called on error */
    onError?: (event: Event) => void;
    /** Called if task completed while component was unmounted (requires taskId) */
    onTaskAlreadyCompleted?: () => void;
}

export interface SSESubscriptionReturn {
    connectionState: SSEConnectionState;
    isConnected: boolean;
}
