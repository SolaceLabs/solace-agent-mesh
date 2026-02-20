import { createContext } from "react";

import type { SSEConnectionState, SSETask } from "../types";

/**
 * Context value for managing SSE (Server-Sent Events) connections and task tracking.
 *
 * Provides a centralized registry for background tasks that communicate via SSE,
 * along with methods to subscribe to SSE endpoints and check task status.
 * Tasks are persisted in sessionStorage so they survive page navigations.
 *
 * @property registerTask - Register a new task. The `registeredAt` timestamp is added automatically.
 * @property unregisterTask - Remove a task from the registry by its ID.
 * @property getTask - Look up a single task by its ID. Returns `null` if not found.
 * @property getTasks - Return all currently registered tasks.
 * @property getTasksByMetadata - Find tasks whose metadata contains the given key-value pair.
 * @property subscribe - Open an SSE connection to the given endpoint. Returns an unsubscribe function that closes the connection.
 * @property checkTaskStatus - Check whether a task is still running on the server. Returns `null` if the task is unknown.
 */
export interface SSEContextValue {
    registerTask: (task: Omit<SSETask, "registeredAt">) => void;
    unregisterTask: (taskId: string) => void;
    getTask: (taskId: string) => SSETask | null;
    getTasks: () => SSETask[];
    getTasksByMetadata: (key: string, value: unknown) => SSETask[];
    subscribe: (endpoint: string, handlers: { onMessage?: (e: MessageEvent) => void; onError?: (e: Event) => void }, onStateChange: (state: SSEConnectionState) => void, eventType?: string) => () => void;
    checkTaskStatus: (taskId: string) => Promise<{ isRunning: boolean } | null>;
}

export const SSEContext = createContext<SSEContextValue | null>(null);
