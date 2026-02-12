import { useContext } from "react";

import { SSEContext } from "../contexts/SSEContext";

/**
 * Hook to access the SSE task registry.
 *
 * The task registry tracks active SSE tasks with metadata, persisted to sessionStorage.
 * Useful for tracking which tasks are running, querying by project/feature, etc.
 *
 * @returns Task registry methods
 *
 * @example Register and query tasks
 * ```tsx
 * function ProjectTasks({ projectId }: { projectId: string }) {
 *   const { registerTask, getTasksByMetadata } = useSSEContext();
 *
 *   const projectTasks = getTasksByMetadata('projectId', projectId);
 *
 *   const startTask = async () => {
 *     const { task_id, sse_url } = await api.startTask();
 *     registerTask({
 *       taskId: task_id,
 *       sseUrl: sse_url,
 *       metadata: { projectId, feature: 'build' }
 *     });
 *   };
 *
 *   return <div>{projectTasks.length} active tasks</div>;
 * }
 * ```
 */
export function useSSEContext() {
    const context = useContext(SSEContext);
    if (!context) {
        throw new Error("useSSEContext must be used within SSEProvider");
    }

    return {
        registerTask: context.registerTask,
        unregisterTask: context.unregisterTask,
        getTask: context.getTask,
        getTasks: context.getTasks,
        getTasksByMetadata: context.getTasksByMetadata,
    };
}
