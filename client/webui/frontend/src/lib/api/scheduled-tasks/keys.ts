/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const scheduledTaskKeys = {
    all: ["scheduled-tasks"] as const,
    lists: () => [...scheduledTaskKeys.all, "list"] as const,
    list: (filters?: { pageNumber?: number; pageSize?: number; enabledOnly?: boolean; includeNamespaceTasks?: boolean }) => [...scheduledTaskKeys.lists(), { filters }] as const,
    details: () => [...scheduledTaskKeys.all, "detail"] as const,
    detail: (id: string) => [...scheduledTaskKeys.details(), id] as const,
    executions: (taskId: string) => [...scheduledTaskKeys.detail(taskId), "executions"] as const,
    executionList: (taskId: string, filters?: { pageNumber?: number; pageSize?: number }) => [...scheduledTaskKeys.executions(taskId), { filters }] as const,
    recentExecutions: (limit: number) => [...scheduledTaskKeys.all, "recent-executions", limit] as const,
    executionArtifacts: (executionId: string) => [...scheduledTaskKeys.all, "execution-artifacts", executionId] as const,
    schedulerStatus: () => [...scheduledTaskKeys.all, "scheduler-status"] as const,
};
