/**
 * Types for background task execution and reconnection.
 */

export interface BackgroundTaskState {
    taskId: string;
    sessionId: string;
    lastEventTimestamp: number;
    isBackground: boolean;
    startTime: number;
    agentName?: string;
}

export interface BackgroundTaskStatusResponse {
    task: {
        id: string;
        user_id: string;
        parent_task_id: string | null;
        start_time: number;
        end_time: number | null;
        status: string | null;
        initial_request_text: string | null;
        execution_mode: string | null;
        last_activity_time: number | null;
        background_execution_enabled: boolean | null;
        max_execution_time_ms: number | null;
    };
    is_running: boolean;
    is_background: boolean;
    can_reconnect: boolean;
}

export interface BackgroundTaskEvent {
    id: string;
    task_id: string;
    user_id: string | null;
    created_time: number;
    topic: string;
    direction: string;
    payload: Record<string, unknown>;
}

export interface BackgroundTaskEventsResponse {
    task: BackgroundTaskStatusResponse["task"];
    events: BackgroundTaskEvent[];
    total_events: number;
    has_more: boolean;
}

export interface ActiveBackgroundTasksResponse {
    tasks: BackgroundTaskStatusResponse["task"][];
    count: number;
}

export interface BackgroundTaskNotification {
    taskId: string;
    type: "completed" | "failed" | "timeout";
    message: string;
    timestamp: number;
}
