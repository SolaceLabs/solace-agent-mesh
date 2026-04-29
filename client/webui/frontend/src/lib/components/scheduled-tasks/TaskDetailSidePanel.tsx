import React from "react";
import { X, Calendar, CalendarDays, User, MoreHorizontal, Pencil, Trash2, History, Play, Pause, CheckCircle2, XCircle, Loader2, AlertCircle, Zap } from "lucide-react";
import type { ScheduledTask, TaskExecution } from "@/lib/types/scheduled-tasks";
import { Button, Tooltip, TooltipContent, TooltipTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useTaskExecutions } from "@/lib/api/scheduled-tasks";
import { formatDuration } from "@/lib/utils/format";
import { toEpochMs } from "@/lib/utils/sessionUnseen";
import { formatSchedule } from "./utils";
import { getStatusBadge } from "./ExecutionList";

const RECENT_RUNS_COUNT = 5;

const executionStatusIcon = (status: TaskExecution["status"]): { Icon: React.ComponentType<{ className?: string }>; className: string; label: string } => {
    switch (status) {
        case "completed":
            return { Icon: CheckCircle2, className: "text-(--success-wMain)", label: "Succeeded" };
        case "failed":
            return { Icon: XCircle, className: "text-(--error-wMain)", label: "Failed" };
        case "timeout":
            return { Icon: AlertCircle, className: "text-(--warning-wMain)", label: "Timed out" };
        case "running":
            return { Icon: Loader2, className: "animate-spin text-(--info-wMain)", label: "Running" };
        case "pending":
            return { Icon: Loader2, className: "animate-spin text-(--info-wMain)", label: "Pending" };
        case "skipped":
            return { Icon: AlertCircle, className: "text-(--secondary-text-wMain)", label: "Skipped" };
        case "cancelled":
            return { Icon: XCircle, className: "text-(--secondary-text-wMain)", label: "Cancelled" };
        default:
            return { Icon: AlertCircle, className: "text-(--secondary-text-wMain)", label: String(status) };
    }
};

const ExecutionHistory: React.FC<{ taskId: string; onViewAll: () => void }> = ({ taskId, onViewAll }) => {
    const { data, isLoading } = useTaskExecutions(taskId, 1, RECENT_RUNS_COUNT);
    const executions = data?.executions ?? [];

    return (
        <div>
            <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Execution History</h3>
                <button type="button" onClick={onViewAll} className="text-xs text-(--primary-wMain) hover:underline">
                    View Executions
                </button>
            </div>

            {isLoading ? (
                <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading…
                </div>
            ) : executions.length === 0 ? (
                <div className="text-xs text-(--secondary-text-wMain) italic">No runs yet.</div>
            ) : (
                <ul className="space-y-1">
                    {executions.map(ex => {
                        const { Icon, className, label } = executionStatusIcon(ex.status);
                        const when = toEpochMs(ex.completedAt ?? ex.startedAt ?? ex.scheduledFor);
                        const duration = ex.durationMs ? formatDuration(ex.durationMs) : null;
                        return (
                            <li key={ex.id}>
                                <button type="button" onClick={onViewAll} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-(--secondary-w10)" title={ex.errorMessage ?? label}>
                                    <Icon className={`h-3.5 w-3.5 flex-shrink-0 ${className}`} />
                                    <span className="min-w-0 flex-1 truncate">
                                        <span className="font-medium">{label}</span>
                                        <span className="text-(--secondary-text-wMain)">
                                            {" · "}
                                            {new Date(when).toLocaleString()}
                                            {duration && ` · ${duration}`}
                                        </span>
                                    </span>
                                </button>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
};

interface TaskDetailSidePanelProps {
    task: ScheduledTask | null;
    onClose: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string, taskName: string) => void;
    onViewExecutions: (task: ScheduledTask) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
    onRunNow?: (task: ScheduledTask) => void;
    isRunNowPending?: boolean;
}

const formatTimestamp = (timestamp: number): string => {
    // Auto-detect if timestamp is in seconds or milliseconds
    const ts = timestamp < 10000000000 ? timestamp * 1000 : timestamp;
    return new Date(ts).toLocaleString();
};

export const TaskDetailSidePanel: React.FC<TaskDetailSidePanelProps> = ({ task, onClose, onEdit, onDelete, onViewExecutions, onToggleEnabled, onRunNow, isRunNowPending = false }) => {
    if (!task) return null;

    // One-time tasks are terminal after their run; config-sourced tasks are read-only.
    const canRunNow = !!onRunNow && task.scheduleType !== "one_time" && task.source !== "config";

    const taskMessageText = task.taskMessage?.[0]?.text || "";

    return (
        <div className="flex h-full w-full flex-col border-l bg-(--background-w10)">
            {/* Header */}
            <div className="flex items-center justify-between border-b p-4">
                <div className="flex min-w-0 flex-1 items-center gap-2">
                    <CalendarDays className="h-5 w-5 flex-shrink-0 text-(--secondary-text-wMain)" />
                    <Tooltip delayDuration={300}>
                        <TooltipTrigger asChild>
                            <h2 className="cursor-default truncate text-lg font-semibold">{task.name}</h2>
                        </TooltipTrigger>
                        <TooltipContent side="bottom">
                            <p>{task.name}</p>
                        </TooltipContent>
                    </Tooltip>
                </div>
                <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" tooltip="Actions">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onEdit(task)}>
                                <Pencil size={14} className="mr-2" />
                                Edit Task
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onViewExecutions(task)}>
                                <History size={14} className="mr-2" />
                                View Execution History
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onToggleEnabled(task)}>
                                {task.enabled ? (
                                    <>
                                        <Pause size={14} className="mr-2" />
                                        Pause Task
                                    </>
                                ) : (
                                    <>
                                        <Play size={14} className="mr-2" />
                                        Resume Task
                                    </>
                                )}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onDelete(task.id, task.name)}>
                                <Trash2 size={14} className="mr-2" />
                                Delete Task
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                    <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0" tooltip="Close">
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Task Details card — description, status/schedule, primary actions */}
                <section className="space-y-4 rounded-md bg-(--secondary-w10) p-4">
                    <h3 className="text-sm font-semibold">Task Details</h3>

                    <div className="text-sm leading-relaxed">{task.description || <span className="text-(--secondary-text-wMain) italic">No description</span>}</div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <div className="mb-1 text-xs text-(--secondary-text-wMain)">Status</div>
                            {task.status ? getStatusBadge(task.status) : null}
                        </div>
                        <div>
                            <div className="mb-1 text-xs text-(--secondary-text-wMain)">Schedule</div>
                            <div className="text-sm">{formatSchedule(task)}</div>
                        </div>
                    </div>

                    <div className="space-y-2 pt-2">
                        {canRunNow && (
                            <Button onClick={() => onRunNow!(task)} disabled={isRunNowPending} className="w-full">
                                {isRunNowPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Running…
                                    </>
                                ) : (
                                    <>
                                        <Zap className="mr-2 h-4 w-4" />
                                        Run Now
                                    </>
                                )}
                            </Button>
                        )}
                        <Button variant="outline" onClick={() => onEdit(task)} className="w-full">
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit Task
                        </Button>
                    </div>
                </section>

                {/* Instructions card */}
                <section className="space-y-3 rounded-md bg-(--secondary-w10) p-4">
                    <h3 className="text-sm font-semibold">Instructions</h3>
                    {taskMessageText ? <div className="text-sm break-words whitespace-pre-wrap">{taskMessageText}</div> : <div className="text-sm text-(--secondary-text-wMain) italic">No instructions</div>}
                </section>

                {/* Execution History — compact recent-runs list with link to full page. */}
                <ExecutionHistory taskId={task.id} onViewAll={() => onViewExecutions(task)} />
            </div>

            {/* Metadata footer */}
            <div className="space-y-2 border-t bg-(--background-w10) p-4">
                <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                    <User size={12} />
                    <span>Created by: {task.createdBy || task.userId || "System"}</span>
                </div>
                {task.createdAt && (
                    <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                        <Calendar size={12} />
                        <span>Created: {formatTimestamp(task.createdAt)}</span>
                    </div>
                )}
                {task.updatedAt && task.updatedAt !== task.createdAt && (
                    <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                        <Calendar size={12} />
                        <span>Last updated: {formatTimestamp(task.updatedAt)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};
