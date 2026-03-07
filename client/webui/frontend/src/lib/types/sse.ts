/**
 * SSE connection states.
 */
export type SSEConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";

/**
 * Represents a registered SSE task in the task registry.
 *
 * @property taskId - Unique task identifier
 * @property sseUrl - SSE endpoint URL for this task
 * @property metadata - Feature-specific metadata for querying
 * @property registeredAt - When the task was registered (timestamp in ms since epoch)
 */
export interface SSETask {
    taskId: string;
    sseUrl: string;
    metadata?: Record<string, unknown>;
    registeredAt: number;
}

/**
 * Options for subscribing to SSE events via useSSESubscription hook.
 *
 * @property endpoint - SSE endpoint. null = don't connect
 * @property taskId - Optional task ID for status-check-on-reconnect behavior
 * @property eventType - SSE event type to listen for (default: "message"). Use custom types like "index_message" for specific event streams.
 * @property onMessage - Called when message received
 * @property onError - Called on error
 * @property onTaskAlreadyCompleted - Called if task completed while component was unmounted (requires taskId)
 */
export interface SSESubscriptionOptions {
    endpoint: string | null;
    taskId?: string;
    eventType?: string;
    onMessage?: (event: MessageEvent) => void;
    onError?: (event: Event) => void;
    onTaskAlreadyCompleted?: () => void;
}

/**
 * Return value from useSSESubscription hook.
 *
 * @property connectionState - Current connection state
 * @property isConnected - true when connectionState is "connected"
 */
export interface SSESubscriptionReturn {
    connectionState: SSEConnectionState;
    isConnected: boolean;
}
