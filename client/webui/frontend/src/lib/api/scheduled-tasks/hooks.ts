import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateScheduledTaskRequest, UpdateScheduledTaskRequest } from "@/lib/types/scheduled-tasks";
import { IN_PROGRESS_STATUSES } from "@/lib/types/scheduled-tasks";

import { scheduledTaskKeys } from "./keys";
import * as scheduledTaskService from "./service";
import type { ConflictValidationRequest, ConflictValidationResult } from "./service";

export function useScheduledTasks(pageNumber: number = 1, pageSize: number = 100, enabledOnly: boolean = false, includeNamespaceTasks: boolean = true) {
    return useQuery({
        queryKey: scheduledTaskKeys.list({ pageNumber, pageSize, enabledOnly, includeNamespaceTasks }),
        queryFn: () => scheduledTaskService.fetchTasks(pageNumber, pageSize, enabledOnly, includeNamespaceTasks),
        refetchOnMount: "always",
    });
}

export function useScheduledTask(taskId: string) {
    return useQuery({
        queryKey: scheduledTaskKeys.detail(taskId),
        queryFn: () => scheduledTaskService.fetchTask(taskId),
        enabled: !!taskId,
    });
}

export function useCreateScheduledTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskData: CreateScheduledTaskRequest) => scheduledTaskService.createTask(taskData),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
        },
    });
}

export function useUpdateScheduledTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskId, updates }: { taskId: string; updates: UpdateScheduledTaskRequest }) => scheduledTaskService.updateTask(taskId, updates),
        onSuccess: (_, { taskId }) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
        },
    });
}

export function useDeleteScheduledTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) => scheduledTaskService.deleteTask(taskId),
        onSuccess: (_, taskId) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
        },
    });
}

export function useEnableScheduledTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) => scheduledTaskService.enableTask(taskId),
        onSuccess: (_, taskId) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
        },
    });
}

export function useDisableScheduledTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) => scheduledTaskService.disableTask(taskId),
        onSuccess: (_, taskId) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
        },
    });
}

export function useRunScheduledTaskNow() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) => scheduledTaskService.runTaskNow(taskId),
        // Proactively refresh execution history so the new run appears.
        onSuccess: (_, taskId) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.executions(taskId) });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
        },
    });
}

const ACTIVE_REFETCH_MS = 5_000;
const IDLE_REFETCH_MS = 30_000;

interface UseTaskExecutionsOptions {
    /** Enable adaptive polling: 5s while any execution is pending/running, 30s otherwise. */
    poll?: boolean;
}

export function useTaskExecutions(taskId: string, pageNumber: number = 1, pageSize: number = 20, scheduledAfter?: number | null, scheduledBefore?: number | null, options: UseTaskExecutionsOptions = {}) {
    return useQuery({
        queryKey: [...scheduledTaskKeys.executionList(taskId, { pageNumber, pageSize }), { scheduledAfter, scheduledBefore }],
        queryFn: () => scheduledTaskService.fetchExecutions(taskId, pageNumber, pageSize, scheduledAfter, scheduledBefore),
        enabled: !!taskId,
        // Adaptive polling — fast while a run is in flight, slow otherwise.
        // TanStack pauses these intervals automatically when the tab is hidden
        // and resumes on focus (via refetchOnWindowFocus). Returning false
        // disables the timer entirely when the caller hasn't opted in.
        refetchInterval: options.poll
            ? query => {
                  const data = query.state.data;
                  const hasActive = data?.executions?.some(e => IN_PROGRESS_STATUSES.has(e.status));
                  return hasActive ? ACTIVE_REFETCH_MS : IDLE_REFETCH_MS;
              }
            : false,
        refetchOnWindowFocus: options.poll ? "always" : false,
    });
}

export function useExecution(executionId: string | null, options: { poll?: boolean } = {}) {
    return useQuery({
        queryKey: executionId ? scheduledTaskKeys.execution(executionId) : [...scheduledTaskKeys.all, "execution", "empty"],
        queryFn: () => scheduledTaskService.fetchExecution(executionId!),
        enabled: !!executionId,
        // Adaptive polling — fast while this execution is in flight, slow otherwise.
        refetchInterval: options.poll
            ? query => {
                  const data = query.state.data;
                  if (!data) return IDLE_REFETCH_MS;
                  return IN_PROGRESS_STATUSES.has(data.status) ? ACTIVE_REFETCH_MS : IDLE_REFETCH_MS;
              }
            : false,
        refetchOnWindowFocus: options.poll ? "always" : false,
    });
}

export function useDeleteExecution(taskId: string) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (executionId: string) => scheduledTaskService.deleteExecution(executionId),
        onSuccess: (_, executionId) => {
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.executions(taskId) });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(taskId) });
            queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
            // Drop the deleted execution's caches so a future execution that
            // reuses the same id can't serve stale data.
            queryClient.removeQueries({ queryKey: scheduledTaskKeys.execution(executionId) });
            queryClient.removeQueries({ queryKey: scheduledTaskKeys.executionArtifacts(executionId) });
        },
    });
}

export function useExecutionArtifacts(executionId: string | null) {
    return useQuery({
        queryKey: executionId ? scheduledTaskKeys.executionArtifacts(executionId) : ["execution-artifacts", "empty"],
        queryFn: () => scheduledTaskService.fetchExecutionArtifacts(executionId!),
        enabled: !!executionId,
    });
}

export function useRecentExecutions(limit: number = 50) {
    return useQuery({
        queryKey: scheduledTaskKeys.recentExecutions(limit),
        queryFn: () => scheduledTaskService.fetchRecentExecutions(limit),
    });
}

export function useSchedulerStatus() {
    return useQuery({
        queryKey: scheduledTaskKeys.schedulerStatus(),
        queryFn: scheduledTaskService.fetchSchedulerStatus,
    });
}

// Mutation hook wrapping scheduledTaskService.validateTaskConflict so callers
// can use mutateAsync/isPending instead of calling the service directly and
// managing their own loading flag.
export function useValidateTaskConflict() {
    return useMutation<ConflictValidationResult, Error, ConflictValidationRequest>({
        mutationFn: input => scheduledTaskService.validateTaskConflict(input),
    });
}
