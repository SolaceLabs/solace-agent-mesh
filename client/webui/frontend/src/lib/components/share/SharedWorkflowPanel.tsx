/**
 * SharedWorkflowPanel - Read-only workflow visualization for shared sessions
 */

import { useEffect, useMemo } from "react";
import { Network } from "lucide-react";
// Import directly from the file to avoid pulling in context-dependent components
import { processTaskForVisualization } from "@/lib/components/activities/taskVisualizerProcessor";
import { SharedFlowChartPanel } from "./SharedFlowChartPanel";
import type { SharedTaskEvents, SharedTaskEvent } from "@/lib/types/share";
import type { A2AEventSSEPayload, TaskFE, VisualizedTask } from "@/lib/types";

interface SharedWorkflowPanelProps {
    taskEvents: Record<string, SharedTaskEvents> | null | undefined;
    selectedTaskId: string | null;
    onTaskSelect: (taskId: string) => void;
}

/**
 * Convert SharedTaskEvent to A2AEventSSEPayload format
 */
function convertToA2AEvent(event: SharedTaskEvent): A2AEventSSEPayload {
    return {
        event_type: event.event_type,
        timestamp: event.timestamp,
        solace_topic: event.solace_topic,
        direction: event.direction,
        source_entity: event.source_entity,
        target_entity: event.target_entity,
        message_id: event.message_id || undefined,
        task_id: event.task_id,
        payload_summary: event.payload_summary,
        full_payload: event.full_payload,
    } as A2AEventSSEPayload;
}

/**
 * Convert shared task events to TaskFE format for visualization
 */
function convertToTaskFE(taskId: string, taskData: SharedTaskEvents): TaskFE {
    const events = taskData.events.map(convertToA2AEvent);

    return {
        taskId,
        events,
        initialRequestText: taskData.initial_request_text || "",
        firstSeen: new Date(events[0]?.timestamp || Date.now()),
        lastUpdated: new Date(events[events.length - 1]?.timestamp || Date.now()),
    } as TaskFE;
}

/**
 * Build monitoredTasks record from shared task events
 */
function buildMonitoredTasks(taskEvents: Record<string, SharedTaskEvents>): Record<string, TaskFE> {
    const result: Record<string, TaskFE> = {};

    for (const [taskId, taskData] of Object.entries(taskEvents)) {
        result[taskId] = convertToTaskFE(taskId, taskData);
    }

    return result;
}

/**
 * Find the root task (the one that was initiated by the user)
 */
function findRootTaskId(taskEvents: Record<string, SharedTaskEvents>): string | null {
    const taskIds = Object.keys(taskEvents);
    if (taskIds.length === 0) return null;

    // Look for a task that has a request event from "User"
    for (const [taskId, taskData] of Object.entries(taskEvents)) {
        const hasUserRequest = taskData.events.some(event => event.direction === "request" && event.source_entity === "User");
        if (hasUserRequest) {
            return taskId;
        }
    }

    // Fallback to first task
    return taskIds[0];
}

export function SharedWorkflowPanel({ taskEvents, selectedTaskId, onTaskSelect }: SharedWorkflowPanelProps) {
    // Compute rootTaskId and monitoredTasks (independent of selectedTaskId)
    const { rootTaskId, monitoredTasks } = useMemo(() => {
        if (!taskEvents || Object.keys(taskEvents).length === 0) {
            return { rootTaskId: null, monitoredTasks: {} };
        }

        const monitoredTasks = buildMonitoredTasks(taskEvents);
        const rootTaskId = findRootTaskId(taskEvents);

        return { rootTaskId, monitoredTasks };
    }, [taskEvents]);

    // Auto-select root task if nothing selected
    useEffect(() => {
        if (rootTaskId && !selectedTaskId) {
            onTaskSelect(rootTaskId);
        }
    }, [rootTaskId, selectedTaskId, onTaskSelect]);

    // Compute visualized task based on selected task
    const visualizedTask = useMemo(() => {
        if (!taskEvents || Object.keys(taskEvents).length === 0) {
            return null;
        }

        // Use selected task or root task
        const taskIdToVisualize = selectedTaskId || rootTaskId;

        if (!taskIdToVisualize || !monitoredTasks[taskIdToVisualize]) {
            return null;
        }

        const parentTask = monitoredTasks[taskIdToVisualize];
        return processTaskForVisualization(parentTask.events || [], monitoredTasks, parentTask);
    }, [taskEvents, selectedTaskId, rootTaskId, monitoredTasks]);

    if (!taskEvents || Object.keys(taskEvents).length === 0) {
        return (
            <div className="flex h-full items-center justify-center p-4">
                <div className="text-muted-foreground text-center">
                    <Network className="mx-auto mb-4 h-12 w-12" />
                    <div className="text-lg font-medium">Workflow</div>
                    <div className="mt-2 text-sm">No workflow data available for this session</div>
                </div>
            </div>
        );
    }

    if (!visualizedTask) {
        return (
            <div className="flex h-full items-center justify-center p-4">
                <div className="text-muted-foreground text-center">
                    <Network className="mx-auto mb-4 h-12 w-12" />
                    <div className="text-lg font-medium">Workflow</div>
                    <div className="mt-2 text-sm">Unable to process workflow data</div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col">
            {/* Flow chart details (User request and Status) */}
            <SharedFlowChartDetails task={visualizedTask} />

            {/* Flow chart visualization */}
            <div className="min-h-0 flex-1">
                <SharedFlowChartPanel processedSteps={visualizedTask.steps || []} />
            </div>
        </div>
    );
}

/**
 * Simplified FlowChartDetails for shared sessions (read-only, no download button)
 */
function SharedFlowChartDetails({ task }: { task: VisualizedTask }) {
    const getStatusBadge = (status: string) => {
        const statusColors: Record<string, string> = {
            completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
            failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
            canceled: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
            working: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
        };

        const colorClass = statusColors[status] || statusColors.working;

        return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}>{status.charAt(0).toUpperCase() + status.slice(1)}</span>;
    };

    return (
        <div className="grid grid-cols-[auto_1fr] grid-rows-[32px_32px] items-center gap-x-4 border-b p-4">
            <div className="text-muted-foreground text-sm">User</div>
            <div className="truncate text-sm" title={task.initialRequestText}>
                {task.initialRequestText || "No request text"}
            </div>

            <div className="text-muted-foreground text-sm">Status</div>
            <div>{getStatusBadge(task.status)}</div>
        </div>
    );
}
