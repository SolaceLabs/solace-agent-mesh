import React from "react";
import { X, CalendarDays, MoreHorizontal, Pencil, Trash2, History, Play, Pause, CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";
import type { ScheduledTask, TaskExecution } from "@/lib/types/scheduled-tasks";
import { Button, Tooltip, TooltipContent, TooltipTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useTaskExecutions } from "@/lib/api/scheduled-tasks";
import { toEpochMs } from "@/lib/utils/sessionUnseen";
import { formatSchedule } from "./utils";
import { getStatusBadge } from "./StatusBadge";

/** "5 minutes ago", "Yesterday", "YYYY-MM-DD HH:MM" — long-form relative time. */
const formatRelativeLong = (epochMs: number): string => {
    const diffSec = Math.floor((Date.now() - epochMs) / 1000);
    if (diffSec < 60) return `${diffSec} second${diffSec === 1 ? "" : "s"} ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? "" : "s"} ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? "" : "s"} ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay === 1) return "Yesterday";
    if (diffDay < 7) return `${diffDay} days ago`;
    const d = new Date(epochMs);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

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
            <h3 className="mb-3 text-sm font-semibold">Execution History</h3>

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
                        const isInFlight = ex.status === "running" || ex.status === "pending";
                        // Running rows show "Started X ago" (anchored on startedAt);
                        // terminal rows show "X ago" (anchored on completedAt).
                        const anchorMs = toEpochMs(isInFlight ? (ex.startedAt ?? ex.scheduledFor) : (ex.completedAt ?? ex.startedAt ?? ex.scheduledFor));
                        const relative = formatRelativeLong(anchorMs);
                        const timeText = isInFlight ? `Started ${relative}` : relative;
                        return (
                            <li key={ex.id}>
                                <button type="button" onClick={onViewAll} className="flex w-full items-center gap-2 rounded py-1.5 text-left text-sm hover:bg-(--secondary-w10)" title={ex.errorMessage ?? label}>
                                    <Icon className={`h-4 w-4 flex-shrink-0 ${className}`} />
                                    <span className="min-w-0 flex-1 truncate">{timeText}</span>
                                    <span className={`flex-shrink-0 text-xs ${className}`}>{label}</span>
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

export const TaskDetailSidePanel: React.FC<TaskDetailSidePanelProps> = ({ task, onClose, onEdit, onDelete, onViewExecutions, onToggleEnabled, onRunNow, isRunNowPending = false }) => {
    if (!task) return null;

    // One-time tasks are terminal after their run; config-sourced tasks are read-only.
    const canRunNow = !!onRunNow && task.scheduleType !== "one_time" && task.source !== "config";

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
                                    "Run Now"
                                )}
                            </Button>
                        )}
                        <Button variant="outline" onClick={() => onViewExecutions(task)} className="w-full">
                            Task Details
                        </Button>
                    </div>
                </section>

                {/* Execution History — compact recent-runs list with link to full page. */}
                <ExecutionHistory taskId={task.id} onViewAll={() => onViewExecutions(task)} />
            </div>
        </div>
    );
};
