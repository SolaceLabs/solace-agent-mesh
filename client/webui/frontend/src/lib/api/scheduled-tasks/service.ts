import { api } from "@/lib/api/client";
import type { ScheduledTask, ScheduledTaskListResponse, CreateScheduledTaskRequest, UpdateScheduledTaskRequest, ExecutionListResponse, SchedulerStatus } from "@/lib/types/scheduled-tasks";
import { transformApiTask, transformApiExecution, transformTaskToApi, transformUpdateToApi } from "@/lib/types/scheduled-tasks";

export const fetchTasks = async (pageNumber: number = 1, pageSize: number = 20, enabledOnly: boolean = false, includeNamespaceTasks: boolean = true): Promise<ScheduledTaskListResponse> => {
    const params = new URLSearchParams({
        pageNumber: pageNumber.toString(),
        pageSize: pageSize.toString(),
        enabledOnly: enabledOnly.toString(),
        includeNamespaceTasks: includeNamespaceTasks.toString(),
    });

    const data = await api.webui.get(`/api/v1/scheduled-tasks/?${params.toString()}`);
    return {
        ...data,
        tasks: data.tasks.map(transformApiTask),
    };
};

export const fetchTask = async (taskId: string): Promise<ScheduledTask> => {
    const data = await api.webui.get(`/api/v1/scheduled-tasks/${taskId}`);
    return transformApiTask(data);
};

export const createTask = async (taskData: CreateScheduledTaskRequest): Promise<ScheduledTask> => {
    const apiData = transformTaskToApi(taskData);
    const data = await api.webui.post(`/api/v1/scheduled-tasks/`, apiData);
    return transformApiTask(data);
};

export const updateTask = async (taskId: string, updates: UpdateScheduledTaskRequest): Promise<ScheduledTask> => {
    const apiData = transformUpdateToApi(updates);
    const data = await api.webui.patch(`/api/v1/scheduled-tasks/${taskId}`, apiData);
    return transformApiTask(data);
};

export const deleteTask = async (taskId: string): Promise<void> => {
    await api.webui.delete(`/api/v1/scheduled-tasks/${taskId}`);
};

export const enableTask = async (taskId: string): Promise<void> => {
    await api.webui.post(`/api/v1/scheduled-tasks/${taskId}/enable`);
};

export const disableTask = async (taskId: string): Promise<void> => {
    await api.webui.post(`/api/v1/scheduled-tasks/${taskId}/disable`);
};

export const runTaskNow = async (taskId: string): Promise<void> => {
    await api.webui.post(`/api/v1/scheduled-tasks/${taskId}/run`);
};

export const fetchExecutions = async (taskId: string, pageNumber: number = 1, pageSize: number = 20): Promise<ExecutionListResponse> => {
    const params = new URLSearchParams({
        pageNumber: pageNumber.toString(),
        pageSize: pageSize.toString(),
    });

    const data = await api.webui.get(`/api/v1/scheduled-tasks/${taskId}/executions?${params.toString()}`);
    return {
        ...data,
        executions: data.executions.map(transformApiExecution),
    };
};

export const fetchRecentExecutions = async (limit: number = 50): Promise<ExecutionListResponse> => {
    const data = await api.webui.get(`/api/v1/scheduled-tasks/executions/recent?limit=${limit}`);
    return {
        ...data,
        executions: data.executions.map(transformApiExecution),
    };
};

export interface ConflictValidationRequest {
    instructions: string;
    scheduleType: string;
    scheduleExpression: string;
    timezone: string;
    targetAgent?: string | null;
}

export interface ConflictValidationResult {
    conflict: boolean;
    reason: string | null;
    affectedFields: Array<"instructions" | "schedule">;
}

export const validateTaskConflict = async (input: ConflictValidationRequest): Promise<ConflictValidationResult> => {
    const data = await api.webui.post(`/api/v1/scheduled-tasks/builder/validate-conflict`, {
        instructions: input.instructions,
        schedule_type: input.scheduleType,
        schedule_expression: input.scheduleExpression,
        timezone: input.timezone,
        target_agent: input.targetAgent ?? null,
    });
    return {
        conflict: !!data.conflict,
        reason: data.reason ?? null,
        affectedFields: Array.isArray(data.affected_fields) ? data.affected_fields.filter((f: string) => f === "instructions" || f === "schedule") : [],
    };
};

export const fetchSchedulerStatus = async (): Promise<SchedulerStatus> => {
    const data = await api.webui.get(`/api/v1/scheduled-tasks/scheduler/status`);
    return {
        instanceId: data.instance_id,
        namespace: data.namespace,
        isLeader: data.is_leader,
        activeTasksCount: data.active_tasks_count,
        runningExecutionsCount: data.running_executions_count,
        pendingResultsCount: data.pending_results_count,
        schedulerRunning: data.scheduler_running,
        leaderInfo: data.leader_info
            ? {
                  leaderId: data.leader_info.leader_id,
                  leaderNamespace: data.leader_info.leader_namespace,
                  acquiredAt: data.leader_info.acquired_at,
                  expiresAt: data.leader_info.expires_at,
                  heartbeatAt: data.leader_info.heartbeat_at,
                  isExpired: data.leader_info.is_expired,
                  isSelf: data.leader_info.is_self,
              }
            : undefined,
    };
};
