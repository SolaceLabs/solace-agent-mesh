import { createContext } from "react";

import type { SSEConnectionState, SSETask } from "../types";

export interface SSEContextValue {
    registerTask: (task: Omit<SSETask, "registeredAt">) => void;
    unregisterTask: (taskId: string) => void;
    getTask: (taskId: string) => SSETask | null;
    getTasks: () => SSETask[];
    getTasksByMetadata: (key: string, value: unknown) => SSETask[];
    /** Subscribe to SSE events for an endpoint */
    subscribe: (endpoint: string, handlers: { onMessage?: (e: MessageEvent) => void; onError?: (e: Event) => void }, onStateChange: (state: SSEConnectionState) => void, eventType?: string) => () => void;
    /** Check if a task is still running via REST API */
    checkTaskStatus: (taskId: string) => Promise<{ isRunning: boolean } | null>;
}

export const SSEContext = createContext<SSEContextValue | null>(null);
