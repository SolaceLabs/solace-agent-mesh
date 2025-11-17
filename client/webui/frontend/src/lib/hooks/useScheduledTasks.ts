/**
 * Hook for managing scheduled tasks
 */

import { useState, useCallback } from "react";
import { authenticatedFetch } from "@/lib/utils/api";
import { useConfigContext } from "./useConfigContext";
import type {
  ScheduledTask,
  ScheduledTaskListResponse,
  CreateScheduledTaskRequest,
  UpdateScheduledTaskRequest,
  ExecutionListResponse,
  SchedulerStatus,
} from "@/lib/types/scheduled-tasks";

export function useScheduledTasks() {
  const { configServerUrl } = useConfigContext();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiPrefix = `${configServerUrl}/api/v1`;

  /**
   * Fetch all scheduled tasks
   */
  const fetchTasks = useCallback(
    async (
      pageNumber: number = 1,
      pageSize: number = 20,
      enabledOnly: boolean = false,
      includeNamespaceTasks: boolean = true
    ): Promise<ScheduledTaskListResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          pageNumber: pageNumber.toString(),
          pageSize: pageSize.toString(),
          enabledOnly: enabledOnly.toString(),
          includeNamespaceTasks: includeNamespaceTasks.toString(),
        });

        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/?${params.toString()}`,
          { credentials: "include" }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch tasks: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to fetch tasks";
        setError(errorMsg);
        console.error("Error fetching scheduled tasks:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Fetch a single scheduled task
   */
  const fetchTask = useCallback(
    async (taskId: string): Promise<ScheduledTask | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/${taskId}`,
          { credentials: "include" }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch task: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to fetch task";
        setError(errorMsg);
        console.error("Error fetching scheduled task:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Create a new scheduled task
   */
  const createTask = useCallback(
    async (taskData: CreateScheduledTaskRequest): Promise<ScheduledTask | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(`${apiPrefix}/scheduled-tasks/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(taskData),
          credentials: "include",
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Failed to create task: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to create task";
        setError(errorMsg);
        console.error("Error creating scheduled task:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Update a scheduled task
   */
  const updateTask = useCallback(
    async (taskId: string, updates: UpdateScheduledTaskRequest): Promise<ScheduledTask | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(`${apiPrefix}/scheduled-tasks/${taskId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
          credentials: "include",
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Failed to update task: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to update task";
        setError(errorMsg);
        console.error("Error updating scheduled task:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Delete a scheduled task
   */
  const deleteTask = useCallback(
    async (taskId: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(`${apiPrefix}/scheduled-tasks/${taskId}`, {
          method: "DELETE",
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error(`Failed to delete task: ${response.statusText}`);
        }

        return true;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to delete task";
        setError(errorMsg);
        console.error("Error deleting scheduled task:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Enable a scheduled task
   */
  const enableTask = useCallback(
    async (taskId: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/${taskId}/enable`,
          {
            method: "POST",
            credentials: "include",
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to enable task: ${response.statusText}`);
        }

        return true;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to enable task";
        setError(errorMsg);
        console.error("Error enabling scheduled task:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Disable a scheduled task
   */
  const disableTask = useCallback(
    async (taskId: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/${taskId}/disable`,
          {
            method: "POST",
            credentials: "include",
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to disable task: ${response.statusText}`);
        }

        return true;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to disable task";
        setError(errorMsg);
        console.error("Error disabling scheduled task:", err);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Fetch execution history for a task
   */
  const fetchExecutions = useCallback(
    async (
      taskId: string,
      pageNumber: number = 1,
      pageSize: number = 20
    ): Promise<ExecutionListResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          pageNumber: pageNumber.toString(),
          pageSize: pageSize.toString(),
        });

        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/${taskId}/executions?${params.toString()}`,
          { credentials: "include" }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch executions: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to fetch executions";
        setError(errorMsg);
        console.error("Error fetching executions:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Fetch recent executions across all tasks
   */
  const fetchRecentExecutions = useCallback(
    async (limit: number = 50): Promise<ExecutionListResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${apiPrefix}/scheduled-tasks/executions/recent?limit=${limit}`,
          { credentials: "include" }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch recent executions: ${response.statusText}`);
        }

        const data = await response.json();
        return data;
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Failed to fetch recent executions";
        setError(errorMsg);
        console.error("Error fetching recent executions:", err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [apiPrefix]
  );

  /**
   * Fetch scheduler status
   */
  const fetchSchedulerStatus = useCallback(async (): Promise<SchedulerStatus | null> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authenticatedFetch(
        `${apiPrefix}/scheduled-tasks/scheduler/status`,
        { credentials: "include" }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch scheduler status: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to fetch scheduler status";
      setError(errorMsg);
      console.error("Error fetching scheduler status:", err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [apiPrefix]);

  return {
    isLoading,
    error,
    fetchTasks,
    fetchTask,
    createTask,
    updateTask,
    deleteTask,
    enableTask,
    disableTask,
    fetchExecutions,
    fetchRecentExecutions,
    fetchSchedulerStatus,
  };
}