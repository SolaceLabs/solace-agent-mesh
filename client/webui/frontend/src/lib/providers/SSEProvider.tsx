import React, { type ReactNode, useState, useRef, useEffect, useCallback } from "react";

import { SSEContext, type SSEContextValue } from "@/lib/contexts/SSEContext";
import { getApiBearerToken } from "@/lib/utils/api";
import { api } from "@/lib/api";
import type { SSEConnectionState, SSESubscriptionOptions, SSESubscriptionReturn, SSETask } from "@/lib/types";

// ============ Constants ============

const TASK_STORAGE_KEY = "sam_sse_tasks";
const INITIAL_RETRY_DELAY = 1000;
const MAX_RETRY_DELAY = 30000;
const MAX_RETRY_ATTEMPTS = 5;
const STALE_TASK_THRESHOLD_MS = 15 * 60 * 1000; // 15 minutes

// NOTE: No connection timeout is implemented. If EventSource gets stuck in "connecting"
// state indefinitely, there's no automatic recovery. Consider adding a timeout mechanism
// in a future iteration if this becomes a problem in practice.

// ============ Types ============

interface ConnectionEntry {
    eventSource: EventSource;
    state: SSEConnectionState;
    subscribers: Map<
        string,
        {
            onMessage?: (e: MessageEvent) => void;
            onError?: (e: Event) => void;
            onStateChange: (state: SSEConnectionState) => void;
        }
    >;
    retryCount: number;
    retryDelay: number;
    retryTimeoutId: ReturnType<typeof setTimeout> | null;
}

interface SSEProviderProps {
    children: ReactNode;
}

// ============ Module-scoped internals ============

interface ProviderInternals {
    subscribe: (endpoint: string, handlers: { onMessage?: (e: MessageEvent) => void; onError?: (e: Event) => void }, onStateChange: (state: SSEConnectionState) => void) => () => void;
    checkTaskStatus: (taskId: string) => Promise<{ isRunning: boolean } | null>;
}

let providerInternals: ProviderInternals | null = null;

// ============ Provider ============

/**
 * SSEProvider - Manages Server-Sent Events connections with automatic reconnection and task registry.
 *
 * Features:
 * - Connection pooling (multiple subscribers share one EventSource)
 * - Automatic reconnection with exponential backoff
 * - Task registry with sessionStorage persistence
 * - Status-check-on-reconnect to avoid connecting to completed tasks
 *
 * @example Basic Setup (in App.tsx)
 * ```tsx
 * <SSEProvider>
 *   <YourApp />
 * </SSEProvider>
 * ```
 *
 * @example Task Registry Usage
 * ```tsx
 * function MyComponent() {
 *   const { registerTask, unregisterTask } = useSSEContext();
 *
 *   // Register a task when it starts
 *   const handleTaskStart = (taskId: string, sseUrl: string) => {
 *     registerTask({
 *       taskId,
 *       sseUrl,
 *       metadata: { projectId: currentProject.id }
 *     });
 *   };
 *
 *   // Unregister when complete
 *   const handleTaskComplete = (taskId: string) => {
 *     unregisterTask(taskId);
 *   };
 * }
 * ```
 *
 * @example SSE Subscription
 * ```tsx
 * function TaskMonitor({ taskId, sseUrl }: { taskId: string; sseUrl: string }) {
 *   const [messages, setMessages] = useState<string[]>([]);
 *
 *   const { connectionState, isConnected } = useSSESubscription({
 *     endpoint: sseUrl,
 *     taskId: taskId,
 *     onMessage: (event) => {
 *       const data = JSON.parse(event.data);
 *       setMessages(prev => [...prev, data.message]);
 *
 *       // Clean up when task completes
 *       if (data.status === 'completed') {
 *         unregisterTask(taskId);
 *       }
 *     },
 *     onError: (error) => {
 *       console.error('SSE error:', error);
 *     },
 *     onTaskAlreadyCompleted: () => {
 *       // Called if task completed while component was unmounted
 *       console.log('Task already finished');
 *     }
 *   });
 *
 *   return (
 *     <div>
 *       <div>Status: {connectionState}</div>
 *       {messages.map((msg, i) => <div key={i}>{msg}</div>)}
 *     </div>
 *   );
 * }
 * ```
 */
export const SSEProvider: React.FC<SSEProviderProps> = ({ children }) => {
    const connectionsRef = useRef<Map<string, ConnectionEntry>>(new Map());

    // Task registry - persisted to sessionStorage
    const [tasks, setTasks] = useState<SSETask[]>([]);

    // Load tasks from sessionStorage on mount
    useEffect(() => {
        const stored = sessionStorage.getItem(TASK_STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored) as SSETask[];
                // Filter out stale tasks (older than 1 hour)
                const now = Date.now();
                const validTasks = parsed.filter(task => now - task.registeredAt < STALE_TASK_THRESHOLD_MS);
                setTasks(validTasks);
            } catch (error) {
                console.error("[SSEProvider] Failed to parse stored tasks:", error);
                sessionStorage.removeItem(TASK_STORAGE_KEY);
            }
        }
    }, []);

    // Save tasks to sessionStorage whenever they change
    useEffect(() => {
        if (tasks.length > 0) {
            sessionStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
        } else {
            sessionStorage.removeItem(TASK_STORAGE_KEY);
        }
    }, [tasks]);

    // Helper to update connection state and notify all subscribers
    const updateConnectionState = useCallback((endpoint: string, state: SSEConnectionState) => {
        const entry = connectionsRef.current.get(endpoint);
        if (entry) {
            entry.state = state;
            entry.subscribers.forEach(sub => sub.onStateChange(state));
        }
    }, []);

    const buildUrlWithAuth = useCallback((endpoint: string): string => {
        const baseUrl = api.webui.getFullUrl(endpoint);
        const accessToken = getApiBearerToken();

        if (accessToken) {
            const separator = baseUrl.includes("?") ? "&" : "?";
            return `${baseUrl}${separator}token=${accessToken}`;
        }

        return baseUrl;
    }, []);

    const createConnection = useCallback(
        (endpoint: string): ConnectionEntry => {
            const fullUrl = buildUrlWithAuth(endpoint);
            const eventSource = new EventSource(fullUrl, { withCredentials: true });

            const entry: ConnectionEntry = {
                eventSource,
                state: "connecting",
                subscribers: new Map(),
                retryCount: 0,
                retryDelay: INITIAL_RETRY_DELAY,
                retryTimeoutId: null,
            };

            eventSource.onopen = () => {
                entry.retryCount = 0;
                entry.retryDelay = INITIAL_RETRY_DELAY;
                updateConnectionState(endpoint, "connected");
            };

            eventSource.onmessage = (event: MessageEvent) => {
                entry.subscribers.forEach(sub => {
                    sub.onMessage?.(event);
                });
            };

            eventSource.onerror = (errorEvent: Event) => {
                console.error(`[SSEProvider] Connection error: ${endpoint}`, errorEvent);

                eventSource.close();

                entry.subscribers?.forEach(sub => {
                    sub.onError?.(errorEvent);
                });

                // Attempt reconnection if we haven't exceeded max attempts
                if (entry.retryCount < MAX_RETRY_ATTEMPTS) {
                    updateConnectionState(endpoint, "reconnecting");

                    const currentDelay = entry.retryDelay;
                    entry.retryCount++;
                    entry.retryDelay = Math.min(entry.retryDelay * 2, MAX_RETRY_DELAY);

                    entry.retryTimeoutId = setTimeout(() => {
                        entry.retryTimeoutId = null;

                        // Only reconnect if we still have subscribers
                        if (entry.subscribers?.size > 0) {
                            const newUrl = buildUrlWithAuth(endpoint);
                            const newEventSource = new EventSource(newUrl, { withCredentials: true });

                            // Copy event handlers to new EventSource
                            newEventSource.onopen = eventSource.onopen;
                            newEventSource.onmessage = eventSource.onmessage;
                            newEventSource.onerror = eventSource.onerror;

                            entry.eventSource = newEventSource;
                        }
                    }, currentDelay);
                } else {
                    console.error(`[SSEProvider] Max reconnection attempts reached: ${endpoint}`);
                    updateConnectionState(endpoint, "error");
                }
            };

            return entry;
        },
        [buildUrlWithAuth, updateConnectionState]
    );

    const subscribe = useCallback(
        (endpoint: string, handlers: { onMessage?: (e: MessageEvent) => void; onError?: (e: Event) => void }, onStateChange: (state: SSEConnectionState) => void): (() => void) => {
            const subscriberId = crypto.randomUUID();

            let entry = connectionsRef.current.get(endpoint);

            if (!entry) {
                entry = createConnection(endpoint);
                connectionsRef.current.set(endpoint, entry);
            }

            entry.subscribers.set(subscriberId, {
                onMessage: handlers.onMessage,
                onError: handlers.onError,
                onStateChange,
            });

            onStateChange(entry.state);

            return () => {
                const currentEntry = connectionsRef.current.get(endpoint);
                if (!currentEntry) return;

                currentEntry.subscribers.delete(subscriberId);

                // If no more subscribers, close connection
                if (currentEntry.subscribers.size === 0) {
                    if (currentEntry.retryTimeoutId) {
                        clearTimeout(currentEntry.retryTimeoutId);
                    }

                    currentEntry.eventSource.close();
                    connectionsRef.current.delete(endpoint);
                }
            };
        },
        [createConnection]
    );

    // Check task status via REST API
    const checkTaskStatus = useCallback(async (taskId: string): Promise<{ isRunning: boolean } | null> => {
        try {
            const response = await api.webui.get(`/api/v1/tasks/${taskId}/status`);
            return { isRunning: response.is_running };
        } catch (error) {
            console.warn(`[SSEProvider] Failed to check task status for ${taskId}:`, error);
            return null;
        }
    }, []);

    // Set module-scoped internals synchronously during render
    // Update on every render to keep functions current
    providerInternals = { subscribe, checkTaskStatus };

    useEffect(() => {
        return () => {
            providerInternals = null;
        };
    }, []);

    // Task registry functions
    const registerTask = useCallback((task: Omit<SSETask, "registeredAt">) => {
        setTasks(prev => {
            // Don't add duplicates
            if (prev.some(t => t.taskId === task.taskId)) {
                return prev;
            }
            return [...prev, { ...task, registeredAt: Date.now() }];
        });
    }, []);

    const unregisterTask = useCallback((taskId: string) => {
        setTasks(prev => prev.filter(t => t.taskId !== taskId));
    }, []);

    const getTask = useCallback(
        (taskId: string): SSETask | null => {
            return tasks.find(t => t.taskId === taskId) ?? null;
        },
        [tasks]
    );

    const getTasks = useCallback((): SSETask[] => {
        return tasks;
    }, [tasks]);

    const getTasksByMetadata = useCallback(
        (key: string, value: unknown): SSETask[] => {
            return tasks.filter(t => t.metadata?.[key] === value);
        },
        [tasks]
    );

    useEffect(() => {
        const connections = connectionsRef.current;
        return () => {
            // Close all connections
            connections.forEach(entry => {
                if (entry.retryTimeoutId) {
                    clearTimeout(entry.retryTimeoutId);
                }
                entry.eventSource.close();
            });
            connections.clear();
        };
    }, []);

    const contextValue: SSEContextValue = {
        registerTask,
        unregisterTask,
        getTask,
        getTasks,
        getTasksByMetadata,
    };

    return <SSEContext.Provider value={contextValue}>{children}</SSEContext.Provider>;
};

// ============ Hooks ============

/**
 * Hook to subscribe to SSE events with automatic connection management.
 *
 * Features:
 * - Automatic connection/disconnection based on component lifecycle
 * - Shared connections for same endpoint (connection pooling)
 * - Status-check-on-reconnect when taskId is provided
 * - Reconnection with exponential backoff on errors
 *
 * @param options - Subscription configuration
 * @param options.endpoint - SSE endpoint URL (relative path like "/api/v1/sse/task-123")
 * @param options.taskId - Optional task ID for status checking on reconnect
 * @param options.onMessage - Called when SSE message received
 * @param options.onError - Called when connection error occurs
 * @param options.onTaskAlreadyCompleted - Called if task completed while unmounted (requires taskId)
 *
 * @returns Object with connectionState and isConnected
 *
 * @example Simple subscription
 * ```tsx
 * const { isConnected } = useSSESubscription({
 *   endpoint: '/api/v1/sse/events',
 *   onMessage: (event) => console.log(event.data)
 * });
 * ```
 *
 * @example With task status checking
 * ```tsx
 * const { connectionState } = useSSESubscription({
 *   endpoint: task.sseUrl,
 *   taskId: task.id,
 *   onMessage: handleMessage,
 *   onTaskAlreadyCompleted: () => {
 *     // Task finished while we were gone - handle accordingly
 *     showNotification('Task completed');
 *   }
 * });
 * ```
 */
export function useSSESubscription(options: SSESubscriptionOptions): SSESubscriptionReturn {
    if (!providerInternals) {
        throw new Error("useSSESubscription must be used within SSEProvider");
    }

    const { endpoint, taskId, onMessage, onError, onTaskAlreadyCompleted } = options;
    const [connectionState, setConnectionState] = useState<SSEConnectionState>("disconnected");

    // Capture internals in a ref to avoid stale closures
    const internalsRef = useRef<ProviderInternals | null>(providerInternals);
    useEffect(() => {
        internalsRef.current = providerInternals;
    });

    // Refs for callbacks to avoid re-subscribing on every render
    const onMessageRef = useRef(onMessage);
    const onErrorRef = useRef(onError);
    const onTaskAlreadyCompletedRef = useRef(onTaskAlreadyCompleted);
    const hasCheckedStatus = useRef(false);

    // Keep refs in sync with props
    useEffect(() => {
        onMessageRef.current = onMessage;
        onErrorRef.current = onError;
        onTaskAlreadyCompletedRef.current = onTaskAlreadyCompleted;
    });

    // Reset status check flag when taskId changes
    const prevTaskIdRef = useRef(taskId);
    useEffect(() => {
        if (prevTaskIdRef.current !== taskId) {
            hasCheckedStatus.current = false;
            prevTaskIdRef.current = taskId;
        }
    }, [taskId]);

    // Main subscription effect
    useEffect(() => {
        if (!endpoint) {
            setConnectionState("disconnected");
            return;
        }

        const internals = internalsRef.current;
        if (!internals) {
            return;
        }

        let unsubscribe: (() => void) | undefined;
        let cancelled = false;

        const connect = async () => {
            // If taskId provided and we haven't checked yet, check status first
            if (taskId && !hasCheckedStatus.current) {
                hasCheckedStatus.current = true;
                const status = await internals.checkTaskStatus(taskId);

                if (cancelled) return;

                if (status && !status.isRunning) {
                    // Task completed while we were unmounted
                    setConnectionState("disconnected");
                    onTaskAlreadyCompletedRef.current?.();
                    return;
                }
            }

            // Task still running (or no taskId) - connect to SSE
            unsubscribe = internals.subscribe(
                endpoint,
                {
                    onMessage: e => onMessageRef.current?.(e),
                    onError: e => onErrorRef.current?.(e),
                },
                setConnectionState
            );
        };

        connect();

        return () => {
            cancelled = true;
            unsubscribe?.();
        };
    }, [endpoint, taskId]);

    return {
        connectionState,
        isConnected: connectionState === "connected",
    };
}
