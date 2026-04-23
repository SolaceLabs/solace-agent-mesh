/**
 * Hook for monitoring and reconnecting to background tasks.
 * Stores active background tasks in localStorage and automatically reconnects on session load.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { BackgroundTaskState, BackgroundTaskStatusResponse, ActiveBackgroundTasksResponse, BackgroundTaskNotification } from "@/lib/types/background-tasks";

const STORAGE_KEY = "sam_background_tasks";
const POLL_INTERVAL_MS = 10_000;
// A task that disappears from the active-tasks batch response is treated as
// terminated only after this grace period has elapsed since local registration.
// This prevents a race where the backend hasn't yet persisted the task row from
// triggering a false completion.
const REGISTRATION_GRACE_MS = 3000;

interface UseBackgroundTaskMonitorProps {
    userId: string | null;
    currentSessionId: string;
    onTaskCompleted?: (taskId: string, sessionId: string) => void;
    onTaskFailed?: (taskId: string, error: string, sessionId: string) => void;
}

/**
 * Hook for monitoring and reconnecting to background tasks.
 * Stores active background tasks in localStorage and automatically reconnects on session load.
 */
export function useBackgroundTaskMonitor({ userId, currentSessionId, onTaskCompleted, onTaskFailed }: UseBackgroundTaskMonitorProps) {
    const [backgroundTasks, setBackgroundTasks] = useState<BackgroundTaskState[]>([]);
    const backgroundTasksRef = useRef<BackgroundTaskState[]>(backgroundTasks);
    const [notifications, setNotifications] = useState<BackgroundTaskNotification[]>([]);

    // Tracked via ref so the polling tick reads the latest session without being rebuilt
    // every time the user navigates.
    const currentSessionIdRef = useRef(currentSessionId);
    useEffect(() => {
        currentSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

    // Load background tasks from localStorage on mount
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored) as BackgroundTaskState[];
                setBackgroundTasks(parsed);
            } catch (error) {
                console.error("[BackgroundTaskMonitor] Failed to parse stored tasks:", error);
                localStorage.removeItem(STORAGE_KEY);
            }
        }
    }, []);

    // Keep the ref in sync with state
    useEffect(() => {
        backgroundTasksRef.current = backgroundTasks;
    }, [backgroundTasks]);

    // Save background tasks to localStorage whenever they change
    useEffect(() => {
        if (backgroundTasks.length > 0) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(backgroundTasks));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, [backgroundTasks]);

    // Register a background task
    const registerBackgroundTask = useCallback((taskId: string, sessionId: string, agentName?: string) => {
        const newTask: BackgroundTaskState = {
            taskId,
            sessionId,
            lastEventTimestamp: Date.now(),
            isBackground: true,
            startTime: Date.now(),
            agentName,
        };

        setBackgroundTasks(prev => {
            // Don't add duplicates
            if (prev.some(t => t.taskId === taskId)) {
                return prev;
            }
            return [...prev, newTask];
        });
    }, []);

    // Unregister a background task
    const unregisterBackgroundTask = useCallback((taskId: string) => {
        setBackgroundTasks(prev => {
            const filtered = prev.filter(t => t.taskId !== taskId);
            return filtered;
        });
    }, []);

    // Update last event timestamp for a task
    const updateTaskTimestamp = useCallback((taskId: string, timestamp: number) => {
        setBackgroundTasks(prev => prev.map(task => (task.taskId === taskId ? { ...task, lastEventTimestamp: timestamp } : task)));
    }, []);

    const checkTaskStatus = useCallback(
        async (taskId: string, signal?: AbortSignal): Promise<BackgroundTaskStatusResponse | null> => {
            try {
                const response = await api.webui.get(`/api/v1/tasks/${taskId}/status`, { fullResponse: true, signal });
                if (!response.ok) {
                    if (response.status === 404) {
                        unregisterBackgroundTask(taskId);
                    }
                    return null;
                }
                return await response.json();
            } catch (error: unknown) {
                console.warn(`[BackgroundTaskMonitor] Failed to check status for task ${taskId}:`, error);
                return null;
            }
        },
        [unregisterBackgroundTask]
    );

    // Fetch the authoritative list of running background tasks for this user.
    // Returns `null` on failure (distinguished from an empty list on success) so
    // callers can decide whether to act on the response or bail.
    const fetchActiveBackgroundTasks = useCallback(
        async (signal?: AbortSignal): Promise<BackgroundTaskState[] | null> => {
            if (!userId) {
                return [];
            }

            try {
                const response = await api.webui.get(`/api/v1/tasks/background/active?user_id=${encodeURIComponent(userId)}`, { fullResponse: true, signal });
                if (!response.ok) {
                    return null;
                }
                const data: ActiveBackgroundTasksResponse = await response.json();

                return data.tasks.map(task => ({
                    taskId: task.id,
                    sessionId: task.session_id ?? "",
                    lastEventTimestamp: task.last_activity_time || task.start_time,
                    isBackground: true,
                    startTime: task.start_time,
                }));
            } catch (error) {
                console.warn("[BackgroundTaskMonitor] Failed to fetch active background tasks:", error);
                return null;
            }
        },
        [userId]
    );

    // Dispatch the completion/failure callbacks for a single terminated task.
    // Called once per completion after the batched diff identifies it.
    const handleTerminalTask = useCallback(
        async (task: BackgroundTaskState, signal: AbortSignal) => {
            const status = await checkTaskStatus(task.taskId, signal);
            if (signal.aborted || !status) {
                return;
            }

            // The batch endpoint can transiently omit a still-running task (DB write lag,
            // execution_mode not yet set). Treat only actually-terminal tasks as complete;
            // a false positive here fires replayBufferedEvents on an in-flight task and
            // clobbers its final response.
            if (status.is_running) {
                return;
            }

            const taskStatus = status.task.status;
            let notificationType: "completed" | "failed" | "timeout" = "completed";
            let message = `Background task completed`;

            if (taskStatus === "failed" || taskStatus === "error") {
                notificationType = "failed";
                message = status.error_message || `Background task failed`;
            } else if (taskStatus === "timeout") {
                notificationType = "timeout";
                message = `Background task timed out`;
            }

            const notification: BackgroundTaskNotification = {
                taskId: task.taskId,
                type: notificationType,
                message,
                timestamp: Date.now(),
            };

            setNotifications(prev => [...prev, notification]);

            if (notificationType === "completed" && onTaskCompleted) {
                onTaskCompleted(task.taskId, task.sessionId);
            } else if (notificationType !== "completed" && onTaskFailed) {
                onTaskFailed(task.taskId, message, task.sessionId);
            }

            unregisterBackgroundTask(task.taskId);
        },
        [checkTaskStatus, onTaskCompleted, onTaskFailed, unregisterBackgroundTask]
    );

    // One polling tick: single batch request, diff against tracked tasks,
    // dispatch completion for any that have disappeared (past the grace period).
    const runPollTick = useCallback(
        async (signal: AbortSignal) => {
            const tasks = backgroundTasksRef.current;
            if (tasks.length === 0) {
                return;
            }

            const serverTasks = await fetchActiveBackgroundTasks(signal);
            if (signal.aborted || serverTasks === null) {
                // Request failed or was aborted — do not infer anything about
                // the state of tracked tasks.
                return;
            }

            const activeTaskIds = new Set(serverTasks.map(t => t.taskId));
            const now = Date.now();
            const activeSessionId = currentSessionIdRef.current;
            const terminalTasks: BackgroundTaskState[] = [];

            for (const task of tasks) {
                // SSE is authoritative for the session the user is currently viewing —
                // it delivers terminal events live and runs save-task itself. Firing
                // onTaskCompleted here would race with that save and can destructively
                // replay buffered events mid-flight.
                if (task.sessionId && task.sessionId === activeSessionId) {
                    continue;
                }

                if (activeTaskIds.has(task.taskId)) {
                    continue;
                }

                if (now - task.startTime >= REGISTRATION_GRACE_MS) {
                    terminalTasks.push(task);
                }
            }

            for (const terminal of terminalTasks) {
                if (signal.aborted) return;
                await handleTerminalTask(terminal, signal);
            }
        },
        [fetchActiveBackgroundTasks, handleTerminalTask]
    );

    // Stable ref to the latest tick function. The polling effect calls through
    // this ref so that changes to user-supplied callbacks (onTaskCompleted etc.)
    // don't tear down and rebuild the interval.
    const tickRef = useRef<(signal: AbortSignal) => Promise<void>>(runPollTick);
    useEffect(() => {
        tickRef.current = runPollTick;
    }, [runPollTick]);

    // Public handle for callers that want to force a check. Creates its own
    // AbortController so it composes safely outside the polling effect.
    const checkAllBackgroundTasks = useCallback(async () => {
        const controller = new AbortController();
        await tickRef.current(controller.signal);
    }, []);

    const fetchActiveBackgroundTasksPublic = useCallback(async (): Promise<BackgroundTaskState[]> => {
        const result = await fetchActiveBackgroundTasks();
        return result ?? [];
    }, [fetchActiveBackgroundTasks]);

    // Check for running background tasks on mount and when userId changes.
    useEffect(() => {
        if (!userId) {
            return;
        }

        const controller = new AbortController();

        const checkForRunningTasks = async () => {
            const serverTasks = await fetchActiveBackgroundTasks(controller.signal);
            if (controller.signal.aborted || serverTasks === null) {
                return;
            }

            // Merge with locally stored tasks
            setBackgroundTasks(prev => {
                const merged = [...prev];

                for (const serverTask of serverTasks) {
                    if (!merged.some(t => t.taskId === serverTask.taskId)) {
                        merged.push(serverTask);
                    }
                }

                return merged;
            });
        };

        checkForRunningTasks();

        return () => {
            controller.abort();
        };
    }, [userId, fetchActiveBackgroundTasks]);

    // Periodic polling to detect background task completion when not connected to SSE.
    const hasBackgroundTasks = backgroundTasks.length > 0;

    useEffect(() => {
        if (!hasBackgroundTasks) {
            return;
        }

        let currentController: AbortController | null = null;
        // Effect-scoped guard (not useRef) so every rebuild of this effect starts
        // with a fresh `false` — a hook-level ref could stay stuck at `true` if
        // a prior tick was mid-flight when the effect tore down.
        const isPollingRef = { current: false };

        const tick = async () => {
            if (isPollingRef.current) {
                return;
            }
            isPollingRef.current = true;
            const controller = new AbortController();
            currentController = controller;
            try {
                await tickRef.current(controller.signal);
            } finally {
                isPollingRef.current = false;
                if (currentController === controller) {
                    currentController = null;
                }
            }
        };

        const intervalId = setInterval(tick, POLL_INTERVAL_MS);

        return () => {
            clearInterval(intervalId);
            if (currentController) {
                currentController.abort();
            }
        };
    }, [hasBackgroundTasks]);

    // Dismiss a notification
    const dismissNotification = useCallback((taskId: string) => {
        setNotifications(prev => prev.filter(n => n.taskId !== taskId));
    }, []);

    // Get background tasks for current session
    const getSessionBackgroundTasks = useCallback(
        (sessionId: string) => {
            return backgroundTasks.filter(t => t.sessionId === sessionId);
        },
        [backgroundTasks]
    );

    // Check if a specific task is running in background
    const isTaskRunningInBackground = useCallback(
        (taskId: string) => {
            return backgroundTasks.some(t => t.taskId === taskId);
        },
        [backgroundTasks]
    );

    return {
        backgroundTasks,
        notifications,
        registerBackgroundTask,
        unregisterBackgroundTask,
        updateTaskTimestamp,
        checkTaskStatus,
        checkAllBackgroundTasks,
        dismissNotification,
        getSessionBackgroundTasks,
        isTaskRunningInBackground,
        fetchActiveBackgroundTasks: fetchActiveBackgroundTasksPublic,
    };
}
