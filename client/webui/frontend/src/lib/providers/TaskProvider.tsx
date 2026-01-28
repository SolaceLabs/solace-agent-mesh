import React, { type ReactNode, useState, useRef, useEffect, useCallback } from "react";

import type { A2AEventSSEPayload, TaskFE } from "@/lib/types";
import { TaskContext, type TaskContextValue } from "@/lib/contexts/TaskContext";
import { getApiBearerToken } from "@/lib/utils/api";
import { api } from "@/lib/api";

// Helper to strip gateway timestamp prefix from request text
const stripGatewayTimestamp = (text: string): string => {
    const gatewayTimestampPattern = /^Request received by gateway at:[^\n]*\n?/;
    return text.replace(gatewayTimestampPattern, '').trim();
};

interface SubscriptionResponse {
    stream_id: string;
    sse_endpoint_url: string;
}

interface TaskProviderProps {
    children: ReactNode;
}

export const TaskProvider: React.FC<TaskProviderProps> = ({ children }) => {
    const [taskMonitorSseStreamId, setTaskMonitorSseStreamId] = useState<string | null>(null);
    const [isTaskMonitorConnecting, setIsTaskMonitorConnecting] = useState<boolean>(false);
    const [isTaskMonitorConnected, setIsTaskMonitorConnected] = useState<boolean>(false);
    const [taskMonitorSseError, setTaskMonitorSseError] = useState<string | null>(null);
    const [monitoredTasks, setMonitoredTasks] = useState<Record<string, TaskFE>>({});
    const [monitoredTaskOrder, setMonitoredTaskOrder] = useState<string[]>([]);
    const [highlightedStepId, setHighlightedStepIdState] = useState<string | null>(null);

    // Reconnection state management
    const [reconnectionAttempts, setReconnectionAttempts] = useState<number>(0);
    const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
    const maxReconnectionAttempts = 10;

    const taskMonitorEventSourceRef = useRef<EventSource | null>(null);
    const taskMonitorSseStreamIdRef = useRef<string | null>(null);
    const reconnectionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        taskMonitorSseStreamIdRef.current = taskMonitorSseStreamId;
    }, [taskMonitorSseStreamId]);

    const addOrUpdateMonitoredTask = useCallback((event: A2AEventSSEPayload) => {
        setMonitoredTasks(prevTasks => {
            const taskId = event.task_id;
            if (!taskId) {
                // If it's a discovery event, it's normal for it not to have a task_id.
                // We don't want to treat these as tasks in the monitor.
                if (event.direction === "discovery") {
                    // Optionally, log discovery events differently if needed for debugging, or just skip silently.
                    // console.debug("TaskMonitorContext: Received discovery event, skipping task update:", event);
                } else {
                    // For other event types, a missing task_id is unexpected.
                    console.warn("TaskMonitorContext: Received event without task_id, skipping:", event);
                }
                return prevTasks;
            }
            const existingTask = prevTasks[taskId];
            const eventTimestamp = new Date(event.timestamp);
            if (existingTask) {
                const updatedEvents = [...existingTask.events, event].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
                return { ...prevTasks, [taskId]: { ...existingTask, events: updatedEvents, lastUpdated: eventTimestamp } };
            } else {
                let initialRequestText = "Task started...";
                if (event.direction === "request" && event.full_payload?.method?.startsWith("message/")) {
                    const params = event.full_payload.params as { message: { parts: { kind: string; text: string }[] } };
                    if (params?.message?.parts) {
                        const textParts = params.message.parts.filter(p => p.kind === "text" && p.text);
                        if (textParts.length > 0) {
                            // Join all text parts and strip any gateway timestamp prefix
                            const combinedText = textParts.map(p => p.text).join("\n");
                            initialRequestText = stripGatewayTimestamp(combinedText);
                        }
                    }
                }
                const newTask: TaskFE = {
                    taskId,
                    initialRequestText,
                    events: [event],
                    firstSeen: eventTimestamp,
                    lastUpdated: eventTimestamp,
                };
                setMonitoredTaskOrder(prevOrder => [taskId, ...prevOrder.filter(id => id !== taskId)]);
                return { ...prevTasks, [taskId]: newTask };
            }
        });
    }, []);

    const handleTaskMonitorSseOpen = useCallback(() => {
        console.log("TaskMonitorContext: SSE connection opened.");
        setIsTaskMonitorConnecting(false);
        setIsTaskMonitorConnected(true);
        setTaskMonitorSseError(null);

        // Reset reconnection state on successful connection
        setReconnectionAttempts(0);
        setIsReconnecting(false);
        if (reconnectionTimeoutRef.current) {
            clearTimeout(reconnectionTimeoutRef.current);
            reconnectionTimeoutRef.current = null;
        }
    }, []);

    const handleTaskMonitorSseMessage = useCallback(
        (event: MessageEvent) => {
            try {
                const parsedData: A2AEventSSEPayload = JSON.parse(event.data);
                addOrUpdateMonitoredTask(parsedData);
            } catch (parseError) {
                console.error("TaskMonitorContext: Failed to parse SSE 'a2a_message' event data:", parseError, "Raw data:", event.data);
                setTaskMonitorSseError("Received unparseable 'a2a_message' event from server.");
            }
        },
        [addOrUpdateMonitoredTask]
    );

    const handleTaskMonitorSseError = useCallback((errorEvent: Event) => {
        console.error("TaskMonitorContext: SSE connection error:", errorEvent);
        setIsTaskMonitorConnecting(false);
        setIsTaskMonitorConnected(false);
        if (taskMonitorEventSourceRef.current && taskMonitorEventSourceRef.current.readyState === EventSource.CLOSED) {
            setTaskMonitorSseError("Task Monitor SSE connection closed by server or network issue.");
        } else {
            setTaskMonitorSseError("Task Monitor SSE connection error occurred.");
        }
        if (taskMonitorEventSourceRef.current) {
            taskMonitorEventSourceRef.current.close();
            taskMonitorEventSourceRef.current = null;
        }

        if (reconnectionTimeoutRef.current) {
            clearTimeout(reconnectionTimeoutRef.current);
            reconnectionTimeoutRef.current = null;
        }
    }, []);

    const connectTaskMonitorStream = useCallback(async () => {
        if (isTaskMonitorConnected || isTaskMonitorConnecting) {
            console.warn("TaskMonitorContext: Stream is already active or connecting.");
            return;
        }
        console.log("TaskMonitorContext: Attempting to connect stream...");
        setIsTaskMonitorConnecting(true);
        try {
            const subscribeResponse = await api.webui.post("/api/v1/visualization/subscribe", { subscription_targets: [{ type: "my_a2a_messages" }] }, { fullResponse: true });
            if (!subscribeResponse.ok) {
                const errorData = await subscribeResponse.json().catch(() => ({ detail: "Failed to subscribe" }));
                if (errorData.error_type === "authorization_failure") {
                    const message = errorData.message || "Access denied: insufficient permissions";
                    const suggestion = errorData.suggested_action ? ` ${errorData.suggested_action}` : "";
                    throw new Error(`${message}${suggestion}`);
                } else if (errorData.error_type === "subscription_failure") {
                    const message = errorData.message || "Subscription failed";
                    const suggestion = errorData.suggested_action ? ` ${errorData.suggested_action}` : "";
                    throw new Error(`${message}${suggestion}`);
                } else {
                    throw new Error(errorData.detail || errorData.message || `Subscription failed: ${subscribeResponse.statusText}`);
                }
            }
            const subscriptionData: SubscriptionResponse = await subscribeResponse.json();
            setTaskMonitorSseStreamId(subscriptionData.stream_id);
            const sseUrl = subscriptionData.sse_endpoint_url.startsWith("/") ? api.webui.getFullUrl(subscriptionData.sse_endpoint_url) : subscriptionData.sse_endpoint_url;

            if (taskMonitorEventSourceRef.current) taskMonitorEventSourceRef.current.close();
            const accessToken = getApiBearerToken();
            const finalSseUrl = `${sseUrl}${accessToken ? `?token=${accessToken}` : ""}`;
            const newEventSource = new EventSource(finalSseUrl, { withCredentials: true });
            taskMonitorEventSourceRef.current = newEventSource;
            newEventSource.onopen = handleTaskMonitorSseOpen;
            newEventSource.addEventListener("a2a_message", handleTaskMonitorSseMessage);
            newEventSource.onerror = handleTaskMonitorSseError;
        } catch (error) {
            console.error("TaskMonitorContext: Error connecting stream:", error);
            setTaskMonitorSseError(error instanceof Error ? error.message : String(error));
            setIsTaskMonitorConnecting(false);
            setIsTaskMonitorConnected(false);
            setTaskMonitorSseStreamId(null);
            if (taskMonitorEventSourceRef.current) {
                taskMonitorEventSourceRef.current.close();
                taskMonitorEventSourceRef.current = null;
            }

            if (reconnectionTimeoutRef.current) {
                clearTimeout(reconnectionTimeoutRef.current);
                reconnectionTimeoutRef.current = null;
            }
        }
    }, [isTaskMonitorConnected, isTaskMonitorConnecting, handleTaskMonitorSseOpen, handleTaskMonitorSseMessage, handleTaskMonitorSseError]);

    const attemptReconnection = useCallback(() => {
        // Prevent multiple concurrent reconnection attempts
        if (reconnectionTimeoutRef.current) {
            console.log("TaskMonitorContext: Reconnection already in progress, skipping...");
            return;
        }

        if (reconnectionAttempts >= maxReconnectionAttempts) {
            console.warn("TaskMonitorContext: Max reconnection attempts reached. Stopping auto-reconnection.");
            setIsReconnecting(false);
            setTaskMonitorSseError(`Connection lost. Max reconnection attempts (${maxReconnectionAttempts}) reached.`);
            return;
        }

        const delay = 2000;
        console.log(`TaskMonitorContext: Attempting reconnection ${reconnectionAttempts + 1}/${maxReconnectionAttempts} in ${delay}ms...`);

        setIsReconnecting(true);
        setReconnectionAttempts(prev => prev + 1);

        reconnectionTimeoutRef.current = setTimeout(() => {
            connectTaskMonitorStream();
        }, delay);
    }, [reconnectionAttempts, connectTaskMonitorStream]);

    const disconnectTaskMonitorStream = useCallback(async () => {
        console.log("TaskMonitorContext: Disconnecting stream...");

        if (reconnectionTimeoutRef.current) {
            clearTimeout(reconnectionTimeoutRef.current);
            reconnectionTimeoutRef.current = null;
        }

        if (taskMonitorEventSourceRef.current) {
            taskMonitorEventSourceRef.current.close();
            taskMonitorEventSourceRef.current = null;
        }
        const streamIdToUnsubscribe = taskMonitorSseStreamIdRef.current;
        if (streamIdToUnsubscribe) {
            try {
                await api.webui.delete(`/api/v1/visualization/${streamIdToUnsubscribe}/unsubscribe`);
            } catch (error) {
                console.error(`TaskMonitorContext: Error unsubscribing from stream ID: ${streamIdToUnsubscribe}`, error);
            }
        }
        setTaskMonitorSseStreamId(null);
        setIsTaskMonitorConnecting(false);
        setIsTaskMonitorConnected(false);
        setTaskMonitorSseError(null);
        setMonitoredTasks({});
        setMonitoredTaskOrder([]);
        setHighlightedStepIdState(null);
        setReconnectionAttempts(0);
        setIsReconnecting(false);
    }, []);

    useEffect(() => {
        return () => {
            console.log("TaskMonitorProvider: Unmounting. Cleaning up Task Monitor SSE connection.");
            if (taskMonitorEventSourceRef.current) {
                taskMonitorEventSourceRef.current.close();
                taskMonitorEventSourceRef.current = null;
            }
            const streamIdForUnsubscribe = taskMonitorSseStreamIdRef.current;
            if (streamIdForUnsubscribe) {
                const unsubscribeUrl = api.webui.getFullUrl(`/api/v1/visualization/${streamIdForUnsubscribe}/unsubscribe`);
                if (navigator.sendBeacon) {
                    const formData = new FormData();
                    navigator.sendBeacon(unsubscribeUrl, formData);
                } else {
                    api.webui
                        .delete(`/api/v1/visualization/${streamIdForUnsubscribe}/unsubscribe`, {
                            credentials: "include",
                            keepalive: true,
                        })
                        .catch((err: Error) => console.error("TaskMonitorProvider: Error in final unsubscribe on unmount (fetch):", err));
                }
            }
        };
    }, []);

    useEffect(() => {
        if (!isTaskMonitorConnected && !isTaskMonitorConnecting) {
            console.log("TaskProvider: Auto-connecting to task monitor stream...");
            connectTaskMonitorStream();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Empty dependency array for one-time initialization

    useEffect(() => {
        if (!isTaskMonitorConnected && !isTaskMonitorConnecting && taskMonitorSseError) {
            console.log("TaskMonitorContext: Connection lost, initiating auto-reconnection...");
            attemptReconnection();
        }
    }, [isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, attemptReconnection]);

    useEffect(() => {
        return () => {
            if (reconnectionTimeoutRef.current) {
                clearTimeout(reconnectionTimeoutRef.current);
                reconnectionTimeoutRef.current = null;
            }
        };
    }, []);

    const setHighlightedStepId = useCallback((stepId: string | null) => {
        setHighlightedStepIdState(stepId);
    }, []);

    const loadTaskFromBackend = useCallback(async (taskId: string): Promise<TaskFE | null> => {
        try {
            const data = await api.webui.get(`/api/v1/tasks/${taskId}/events`);

            const allTasks = data.tasks as Record<string, { events: A2AEventSSEPayload[]; initial_request_text: string }>;
            const loadedTasks: Record<string, TaskFE> = {};

            for (const [tid, taskData] of Object.entries(allTasks)) {
                const events = taskData.events;
                const rawRequestText = taskData.initial_request_text || "Task loaded from history";
                const taskFE: TaskFE = {
                    taskId: tid,
                    initialRequestText: stripGatewayTimestamp(rawRequestText),
                    events: events,
                    firstSeen: new Date(events[0]?.timestamp || Date.now()),
                    lastUpdated: new Date(events[events.length - 1]?.timestamp || Date.now()),
                };
                loadedTasks[tid] = taskFE;
            }

            setMonitoredTasks(prevTasks => ({
                ...prevTasks,
                ...loadedTasks,
            }));

            setMonitoredTaskOrder(prevOrder => {
                if (prevOrder.includes(taskId)) {
                    return prevOrder;
                }
                return [taskId, ...prevOrder];
            });

            return loadedTasks[taskId] || null;
        } catch (error) {
            console.error(`TaskProvider: Error loading task ${taskId} from backend:`, error);
            return null;
        }
    }, []);

    const registerTaskEarly = useCallback((taskId: string, initialRequestText: string) => {
        console.log(`TaskProvider: Pre-registering task ${taskId} before SSE events arrive`);
        setMonitoredTasks(prevTasks => {
            // Only register if not already present
            if (prevTasks[taskId]) {
                console.log(`TaskProvider: Task ${taskId} already exists, skipping pre-registration`);
                return prevTasks;
            }

            const now = new Date();
            const newTask: TaskFE = {
                taskId,
                initialRequestText,
                events: [],
                firstSeen: now,
                lastUpdated: now,
            };

            setMonitoredTaskOrder(prevOrder => [taskId, ...prevOrder.filter(id => id !== taskId)]);
            return { ...prevTasks, [taskId]: newTask };
        });
    }, []);

    const contextValue: TaskContextValue = {
        isTaskMonitorConnecting,
        isTaskMonitorConnected,
        taskMonitorSseError,
        monitoredTasks,
        monitoredTaskOrder,
        highlightedStepId,
        isReconnecting,
        reconnectionAttempts,
        connectTaskMonitorStream,
        disconnectTaskMonitorStream,
        setHighlightedStepId,
        loadTaskFromBackend,
        registerTaskEarly,
    };

    return <TaskContext.Provider value={contextValue}>{children}</TaskContext.Provider>;
};
