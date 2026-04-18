import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateScheduledTaskRequest, UpdateScheduledTaskRequest } from "@/lib/types/scheduled-tasks";

import { scheduledTaskKeys } from "./keys";
import * as scheduledTaskService from "./service";

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

export function useTaskExecutions(taskId: string, pageNumber: number = 1, pageSize: number = 20) {
    return useQuery({
        queryKey: scheduledTaskKeys.executionList(taskId, { pageNumber, pageSize }),
        queryFn: () => scheduledTaskService.fetchExecutions(taskId, pageNumber, pageSize),
        enabled: !!taskId,
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
