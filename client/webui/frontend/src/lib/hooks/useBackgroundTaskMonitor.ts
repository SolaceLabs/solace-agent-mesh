/**
 * Hook for monitoring and reconnecting to background tasks.
 * Stores active background tasks in localStorage and automatically reconnects on session load.
 */

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { BackgroundTaskState, BackgroundTaskStatusResponse, ActiveBackgroundTasksResponse, BackgroundTaskNotification } from "@/lib/types/background-tasks";

const STORAGE_KEY = "sam_background_tasks";

interface UseBackgroundTaskMonitorProps {
    userId: string | null;
    currentSessionId: string;
    onTaskCompleted?: (taskId: string, sessionId: string) => void;
    onTaskFailed?: (taskId: string, error: string, sessionId: string) => void;
}

export function useBackgroundTaskMonitor({ userId, onTaskCompleted, onTaskFailed }: UseBackgroundTaskMonitorProps) {
    const [backgroundTasks, setBackgroundTasks] = useState<BackgroundTaskState[]>([]);
    const [notifications, setNotifications] = useState<BackgroundTaskNotification[]>([]);

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
        async (taskId: string): Promise<BackgroundTaskStatusResponse | null> => {
            try {
                const response = await api.webui.get(`/api/v1/tasks/${taskId}/status`, { fullResponse: true });
                if (!response.ok) {
                    if (response.status === 404) {
                        unregisterBackgroundTask(taskId);
                    }
                    return null;
                }
                return await response.json();
            } catch (error: unknown) {
                console.error(`[BackgroundTaskMonitor] Failed to check status for task ${taskId}:`, error);
                return null;
            }
        },
        [unregisterBackgroundTask]
    );

    // Check all background tasks and update their status
    const checkAllBackgroundTasks = useCallback(async () => {
        if (backgroundTasks.length === 0) {
            return;
        }

        for (const task of backgroundTasks) {
            const status = await checkTaskStatus(task.taskId);

            if (!status) {
                continue;
            }

            // If task is no longer running, handle completion
            if (!status.is_running) {
                const taskStatus = status.task.status;

                // Create notification
                let notificationType: "completed" | "failed" | "timeout" = "completed";
                let message = `Background task completed`;

                if (taskStatus === "failed" || taskStatus === "error") {
                    notificationType = "failed";
                    message = `Background task failed`;
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

                // Call callbacks with session ID so caller can decide whether to show notification
                if (notificationType === "completed" && onTaskCompleted) {
                    onTaskCompleted(task.taskId, task.sessionId);
                } else if (notificationType !== "completed" && onTaskFailed) {
                    onTaskFailed(task.taskId, message, task.sessionId);
                }

                // Remove from tracking
                unregisterBackgroundTask(task.taskId);
            }
        }
    }, [backgroundTasks, checkTaskStatus, onTaskCompleted, onTaskFailed, unregisterBackgroundTask]);

    const fetchActiveBackgroundTasks = useCallback(async (): Promise<BackgroundTaskState[]> => {
        if (!userId) {
            return [];
        }

        try {
            const data: ActiveBackgroundTasksResponse = await api.webui.get(`/api/v1/tasks/background/active?user_id=${encodeURIComponent(userId)}`);

            return data.tasks.map(task => ({
                taskId: task.id,
                sessionId: "",
                lastEventTimestamp: task.last_activity_time || task.start_time,
                isBackground: true,
                startTime: task.start_time,
            }));
        } catch (error) {
            console.error("[BackgroundTaskMonitor] Failed to fetch active background tasks:", error);
            return [];
        }
    }, [userId]);

    // Check for running background tasks on mount and when userId changes
    useEffect(() => {
        if (!userId) {
            return;
        }

        const checkForRunningTasks = async () => {
            const serverTasks = await fetchActiveBackgroundTasks();

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
    }, [userId, fetchActiveBackgroundTasks]);

    // Periodic checking to detect background task completion when not connected to SSE
    // This handles the case where a task completes while the user is on a different session
    useEffect(() => {
        if (backgroundTasks.length === 0) {
            return;
        }

        // Check immediately on mount/change
        checkAllBackgroundTasks();

        // Then check periodically (every 5 seconds)
        const intervalId = setInterval(() => {
            checkAllBackgroundTasks();
        }, 5000);

        return () => {
            clearInterval(intervalId);
        };
    }, [backgroundTasks.length, checkAllBackgroundTasks]);

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
        fetchActiveBackgroundTasks,
    };
}
