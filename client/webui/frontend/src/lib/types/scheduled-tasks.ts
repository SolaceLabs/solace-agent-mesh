/**
 * TypeScript types for Scheduled Tasks feature
 * Uses camelCase for frontend consistency
 */

export type ScheduleType = "cron" | "interval" | "one_time";
export type ExecutionStatus = "pending" | "running" | "completed" | "failed" | "timeout" | "cancelled";

export interface MessagePart {
    type: "text" | "file";
    text?: string;
    uri?: string;
}

export interface NotificationChannel {
    type: "sse" | "webhook" | "email" | "broker_topic";
    config: Record<string, unknown>;
}

export interface NotificationConfig {
    channels: NotificationChannel[];
    onSuccess: boolean;
    onFailure: boolean;
    includeArtifacts: boolean;
}

export interface ScheduledTask {
    id: string;
    name: string;
    description?: string;

    namespace: string;
    userId?: string;
    createdBy: string;

    scheduleType: ScheduleType;
    scheduleExpression: string;
    timezone: string;

    targetAgentName: string;
    taskMessage: MessagePart[];
    taskMetadata?: Record<string, unknown>;

    enabled: boolean;
    maxRetries: number;
    retryDelaySeconds: number;
    timeoutSeconds: number;

    notificationConfig?: NotificationConfig;

    createdAt: number;
    updatedAt: number;
    nextRunAt?: number;
    lastRunAt?: number;
}

export interface ArtifactInfo {
    name: string;
    uri: string;
}

export interface TaskExecution {
    id: string;
    scheduledTaskId: string;

    status: ExecutionStatus;
    a2aTaskId?: string;

    scheduledFor: number;
    startedAt?: number;
    completedAt?: number;
    durationMs?: number;

    resultSummary?: {
        agentResponse?: string;
        messages?: Array<{ role: string; text: string }>;
        artifacts?: Array<{ name?: string; uri?: string; type?: string }>;
        metadata?: Record<string, unknown>;
        taskStatus?: string;
        errorCode?: number;
        errorData?: unknown;
    };
    errorMessage?: string;
    retryCount: number;

    artifacts?: Array<string | ArtifactInfo>; // Support both string IDs and objects
    notificationsSent?: Array<{
        type: string;
        status: string;
        timestamp: number;
        error?: string;
    }>;
}

export interface ScheduledTaskListResponse {
    tasks: ScheduledTask[];
    total: number;
    skip: number;
    limit: number;
}

export interface ExecutionListResponse {
    executions: TaskExecution[];
    total: number;
    skip: number;
    limit: number;
}

export interface SchedulerStatus {
    instanceId: string;
    namespace: string;
    isLeader: boolean;
    activeTasksCount: number;
    runningExecutionsCount: number;
    pendingResultsCount?: number;
    schedulerRunning: boolean;
    leaderInfo?: {
        leaderId: string;
        leaderNamespace: string;
        acquiredAt: number;
        expiresAt: number;
        heartbeatAt: number;
        isExpired: boolean;
        isSelf: boolean;
    };
}

export interface CreateScheduledTaskRequest {
    name: string;
    description?: string;
    scheduleType: ScheduleType;
    scheduleExpression: string;
    timezone?: string;
    targetAgentName: string;
    taskMessage: MessagePart[];
    taskMetadata?: Record<string, unknown>;
    enabled?: boolean;
    maxRetries?: number;
    retryDelaySeconds?: number;
    timeoutSeconds?: number;
    notificationConfig?: NotificationConfig;
    userLevel?: boolean;
}

export interface UpdateScheduledTaskRequest {
    name?: string;
    description?: string;
    scheduleType?: ScheduleType;
    scheduleExpression?: string;
    timezone?: string;
    targetAgentName?: string;
    taskMessage?: MessagePart[];
    taskMetadata?: Record<string, unknown>;
    enabled?: boolean;
    maxRetries?: number;
    retryDelaySeconds?: number;
    timeoutSeconds?: number;
    notificationConfig?: NotificationConfig;
}

// API response types (snake_case from backend)
// These are used for transforming API responses to frontend types

interface ApiNotificationConfig {
    channels: NotificationChannel[];
    on_success: boolean;
    on_failure: boolean;
    include_artifacts: boolean;
}

interface ApiScheduledTask {
    id: string;
    name: string;
    description?: string;
    namespace: string;
    user_id?: string;
    created_by: string;
    schedule_type: ScheduleType;
    schedule_expression: string;
    timezone: string;
    target_agent_name: string;
    task_message: MessagePart[];
    task_metadata?: Record<string, unknown>;
    enabled: boolean;
    max_retries: number;
    retry_delay_seconds: number;
    timeout_seconds: number;
    notification_config?: ApiNotificationConfig;
    created_at: number;
    updated_at: number;
    next_run_at?: number;
    last_run_at?: number;
}

interface ApiTaskExecution {
    id: string;
    scheduled_task_id: string;
    status: ExecutionStatus;
    a2a_task_id?: string;
    scheduled_for: number;
    started_at?: number;
    completed_at?: number;
    duration_ms?: number;
    result_summary?: {
        agent_response?: string;
        messages?: Array<{ role: string; text: string }>;
        artifacts?: Array<{ name?: string; uri?: string; type?: string }>;
        metadata?: Record<string, unknown>;
        task_status?: string;
        error_code?: number;
        error_data?: unknown;
    };
    error_message?: string;
    retry_count: number;
    artifacts?: Array<string | ArtifactInfo>;
    notifications_sent?: Array<{
        type: string;
        status: string;
        timestamp: number;
        error?: string;
    }>;
}

// Transformation functions

export function transformApiTask(apiTask: ApiScheduledTask): ScheduledTask {
    return {
        id: apiTask.id,
        name: apiTask.name,
        description: apiTask.description,
        namespace: apiTask.namespace,
        userId: apiTask.user_id,
        createdBy: apiTask.created_by,
        scheduleType: apiTask.schedule_type,
        scheduleExpression: apiTask.schedule_expression,
        timezone: apiTask.timezone,
        targetAgentName: apiTask.target_agent_name,
        taskMessage: apiTask.task_message,
        taskMetadata: apiTask.task_metadata,
        enabled: apiTask.enabled,
        maxRetries: apiTask.max_retries,
        retryDelaySeconds: apiTask.retry_delay_seconds,
        timeoutSeconds: apiTask.timeout_seconds,
        notificationConfig: apiTask.notification_config
            ? {
                  channels: apiTask.notification_config.channels,
                  onSuccess: apiTask.notification_config.on_success,
                  onFailure: apiTask.notification_config.on_failure,
                  includeArtifacts: apiTask.notification_config.include_artifacts,
              }
            : undefined,
        createdAt: apiTask.created_at,
        updatedAt: apiTask.updated_at,
        nextRunAt: apiTask.next_run_at,
        lastRunAt: apiTask.last_run_at,
    };
}

export function transformApiExecution(apiExecution: ApiTaskExecution): TaskExecution {
    return {
        id: apiExecution.id,
        scheduledTaskId: apiExecution.scheduled_task_id,
        status: apiExecution.status,
        a2aTaskId: apiExecution.a2a_task_id,
        scheduledFor: apiExecution.scheduled_for,
        startedAt: apiExecution.started_at,
        completedAt: apiExecution.completed_at,
        durationMs: apiExecution.duration_ms,
        resultSummary: apiExecution.result_summary
            ? {
                  agentResponse: apiExecution.result_summary.agent_response,
                  messages: apiExecution.result_summary.messages,
                  artifacts: apiExecution.result_summary.artifacts,
                  metadata: apiExecution.result_summary.metadata,
                  taskStatus: apiExecution.result_summary.task_status,
                  errorCode: apiExecution.result_summary.error_code,
                  errorData: apiExecution.result_summary.error_data,
              }
            : undefined,
        errorMessage: apiExecution.error_message,
        retryCount: apiExecution.retry_count,
        artifacts: apiExecution.artifacts,
        notificationsSent: apiExecution.notifications_sent,
    };
}

// Transform frontend types to API format for requests

export function transformTaskToApi(task: CreateScheduledTaskRequest): Record<string, unknown> {
    return {
        name: task.name,
        description: task.description,
        schedule_type: task.scheduleType,
        schedule_expression: task.scheduleExpression,
        timezone: task.timezone,
        target_agent_name: task.targetAgentName,
        task_message: task.taskMessage,
        task_metadata: task.taskMetadata,
        enabled: task.enabled,
        max_retries: task.maxRetries,
        retry_delay_seconds: task.retryDelaySeconds,
        timeout_seconds: task.timeoutSeconds,
        notification_config: task.notificationConfig
            ? {
                  channels: task.notificationConfig.channels,
                  on_success: task.notificationConfig.onSuccess,
                  on_failure: task.notificationConfig.onFailure,
                  include_artifacts: task.notificationConfig.includeArtifacts,
              }
            : undefined,
        user_level: task.userLevel,
    };
}

export function transformUpdateToApi(update: UpdateScheduledTaskRequest): Record<string, unknown> {
    const result: Record<string, unknown> = {};

    if (update.name !== undefined) result.name = update.name;
    if (update.description !== undefined) result.description = update.description;
    if (update.scheduleType !== undefined) result.schedule_type = update.scheduleType;
    if (update.scheduleExpression !== undefined) result.schedule_expression = update.scheduleExpression;
    if (update.timezone !== undefined) result.timezone = update.timezone;
    if (update.targetAgentName !== undefined) result.target_agent_name = update.targetAgentName;
    if (update.taskMessage !== undefined) result.task_message = update.taskMessage;
    if (update.taskMetadata !== undefined) result.task_metadata = update.taskMetadata;
    if (update.enabled !== undefined) result.enabled = update.enabled;
    if (update.maxRetries !== undefined) result.max_retries = update.maxRetries;
    if (update.retryDelaySeconds !== undefined) result.retry_delay_seconds = update.retryDelaySeconds;
    if (update.timeoutSeconds !== undefined) result.timeout_seconds = update.timeoutSeconds;
    if (update.notificationConfig !== undefined) {
        result.notification_config = {
            channels: update.notificationConfig.channels,
            on_success: update.notificationConfig.onSuccess,
            on_failure: update.notificationConfig.onFailure,
            include_artifacts: update.notificationConfig.includeArtifacts,
        };
    }

    return result;
}
