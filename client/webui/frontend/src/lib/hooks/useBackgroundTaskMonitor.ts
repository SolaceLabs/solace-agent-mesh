import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { BackgroundTaskState, BackgroundTaskStatusResponse, ActiveBackgroundTasksResponse, BackgroundTaskNotification } from "@/lib/types/background-tasks";

const STORAGE_KEY = "sam_background_tasks";
const REGISTRATION_GRACE_MS = 3000; // A task that disappears from the active-tasks is treated as terminated only after this period
const POLL_INTERVAL_MS = 10_000; // Polling interval for background tasks
const SSE_STALE_MS = 60_000; // After this long without an SSE event, treat SSE as unhealthy and let polling cover the task.

type TerminationKind = "completed" | "failed" | "timeout";

// ============ Helpers ============

function logFetchFailure(error: unknown): null {
    if (error instanceof DOMException && error.name === "AbortError") {
        // Don't log expected aborts from effect cleanup
        return null;
    }
    console.error(`[BackgroundTaskMonitor] Failed to fetch task status:`, error);
    return null;
}

function classifyTaskTermination(status: BackgroundTaskStatusResponse): { type: TerminationKind; message: string } {
    const taskStatus = status.task.status;
    if (taskStatus === "failed" || taskStatus === "error") {
        return { type: "failed", message: status.error_message || "Background task failed" };
    }
    if (taskStatus === "timeout") {
        return { type: "timeout", message: "Background task timed out" };
    }
    return { type: "completed", message: "Background task completed" };
}

// Returns the subset of tracked tasks that should be treated as terminal based on the following criteria:
// * not in current session (unless SSE has gone stale)
// * not in server's list
// * past grace period
export function selectTerminationCandidates(tracked: BackgroundTaskState[], activeTaskIds: Set<string>, activeSessionId: string, now: number): BackgroundTaskState[] {
    const terminals: BackgroundTaskState[] = [];
    for (const task of tracked) {
        if (task.sessionId && task.sessionId === activeSessionId && now - task.lastEventTimestamp < SSE_STALE_MS) continue;
        if (activeTaskIds.has(task.taskId)) continue;
        if (now - task.registeredAt >= REGISTRATION_GRACE_MS) {
            terminals.push(task);
        }
    }
    return terminals;
}

// ============ Hook ============

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
    const [notifications, setNotifications] = useState<BackgroundTaskNotification[]>([]);

    const backgroundTasksRef = useRef<BackgroundTaskState[]>(backgroundTasks);
    const currentSessionIdRef = useRef(currentSessionId);

    useEffect(() => {
        currentSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

    useEffect(() => {
        backgroundTasksRef.current = backgroundTasks;
    }, [backgroundTasks]);

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

    useEffect(() => {
        if (backgroundTasks.length > 0) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(backgroundTasks));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, [backgroundTasks]);

    const registerBackgroundTask = useCallback((taskId: string, sessionId: string, agentName?: string) => {
        const now = Date.now();
        const newTask: BackgroundTaskState = {
            taskId,
            sessionId,
            lastEventTimestamp: now,
            isBackground: true,
            startTime: now,
            registeredAt: now,
            agentName,
        };

        setBackgroundTasks(prev => {
            if (prev.some(t => t.taskId === taskId)) {
                return prev;
            }
            return [...prev, newTask];
        });
    }, []);

    const unregisterBackgroundTask = useCallback((taskId: string) => {
        setBackgroundTasks(prev => {
            const filtered = prev.filter(t => t.taskId !== taskId);
            return filtered;
        });
    }, []);

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
                return logFetchFailure(error);
            }
        },
        [unregisterBackgroundTask]
    );

    const fetchActiveBackgroundTasks = useCallback(
        async (signal?: AbortSignal): Promise<BackgroundTaskState[] | null> => {
            if (!userId) {
                return null;
            }

            try {
                const data: ActiveBackgroundTasksResponse = await api.webui.get(`/api/v1/tasks/background/active?user_id=${encodeURIComponent(userId)}`, { signal });

                const now = Date.now();
                return data.tasks.map(task => ({
                    taskId: task.id,
                    sessionId: task.session_id ?? "",
                    lastEventTimestamp: task.last_activity_time || task.start_time,
                    isBackground: true,
                    startTime: task.start_time,
                    registeredAt: now,
                }));
            } catch (error) {
                return logFetchFailure(error);
            }
        },
        [userId]
    );

    // Dispatch the completion/failure callbacks for a single terminated task.
    // Called once per completion after the batched diff identifies it.
    const handleTerminalTask = useCallback(
        async (task: BackgroundTaskState, signal: AbortSignal) => {
            const status = await checkTaskStatus(task.taskId, signal);
            if (signal.aborted || !status || status.is_running) {
                return;
            }

            // SSE on the task's session is authoritative while alive.
            // Bail if the user is now viewing that session AND SSE is still delivering events there
            if (task.sessionId === currentSessionIdRef.current && Date.now() - task.lastEventTimestamp < SSE_STALE_MS) {
                return;
            }

            const { type: notificationType, message } = classifyTaskTermination(status);

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

    // One polling tick: single batch request, diff against tracked tasks
    const runPollTick = useCallback(
        async (signal: AbortSignal) => {
            const tasks = backgroundTasksRef.current;
            if (tasks.length === 0) {
                return;
            }

            const serverTasks = await fetchActiveBackgroundTasks(signal);
            if (signal.aborted || serverTasks === null) {
                // Request failed or was aborted — do not infer anything about task status, try again on next tick
                return;
            }
            const activeTaskIds = new Set(serverTasks.map(t => t.taskId));
            const taskTerminationCandidates = selectTerminationCandidates(tasks, activeTaskIds, currentSessionIdRef.current, Date.now());

            for (const task of taskTerminationCandidates) {
                if (signal.aborted) return;
                await handleTerminalTask(task, signal);
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

        // Per-effect scope (not useRef) so an interrupted tick can't leave the next re-run's guard stuck on `true`.
        const isPollingRef = { current: false };
        let currentController: AbortController | null = null;

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

    const dismissNotification = useCallback((taskId: string) => {
        setNotifications(prev => prev.filter(n => n.taskId !== taskId));
    }, []);

    const getSessionBackgroundTasks = useCallback(
        (sessionId: string) => {
            return backgroundTasks.filter(t => t.sessionId === sessionId);
        },
        [backgroundTasks]
    );

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
        dismissNotification,
        getSessionBackgroundTasks,
        isTaskRunningInBackground,
    };
}
