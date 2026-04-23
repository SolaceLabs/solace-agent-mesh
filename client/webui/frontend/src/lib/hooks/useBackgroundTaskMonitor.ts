import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { BackgroundTaskState, BackgroundTaskStatusResponse, ActiveBackgroundTasksResponse, BackgroundTaskNotification } from "@/lib/types/background-tasks";

const STORAGE_KEY = "sam_background_tasks";
const POLL_INTERVAL_MS = 10_000;
const REGISTRATION_GRACE_MS = 3000; // A task that disappears from the active-tasks is treated as terminated only after this period

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
// * not in current session
// * not in server's list
// * past grace period
function selectTerminationCandidates(tracked: BackgroundTaskState[], activeTaskIds: Set<string>, activeSessionId: string, now: number): BackgroundTaskState[] {
    const terminals: BackgroundTaskState[] = [];
    for (const task of tracked) {
        if (task.sessionId && task.sessionId === activeSessionId) continue;
        if (activeTaskIds.has(task.taskId)) continue;
        if (now - task.startTime >= REGISTRATION_GRACE_MS) {
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
    const backgroundTasksRef = useRef<BackgroundTaskState[]>(backgroundTasks);
    const [notifications, setNotifications] = useState<BackgroundTaskNotification[]>([]);

    // Use ref so polling tick reads the latest session without being rebuilt
    const currentSessionIdRef = useRef(currentSessionId);
    useEffect(() => {
        currentSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

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
        backgroundTasksRef.current = backgroundTasks;
    }, [backgroundTasks]);

    useEffect(() => {
        if (backgroundTasks.length > 0) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(backgroundTasks));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, [backgroundTasks]);

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
                // Request failed or was aborted — do not infer anything about task status, just try again on the next tick
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
        checkAllBackgroundTasks,
        dismissNotification,
        getSessionBackgroundTasks,
        isTaskRunningInBackground,
        fetchActiveBackgroundTasks: fetchActiveBackgroundTasksPublic,
    };
}
