import React, { useState } from "react";
import { Pencil, Trash2, Calendar, Clock, MoreHorizontal, Play, Pause, History, Zap, CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import type { ScheduledTask, TaskStatus, LastExecutionSummary } from "@/lib/types/scheduled-tasks";
import { formatRelativeTime } from "@/lib/utils";
import { formatDuration } from "@/lib/utils/format";
import { formatSchedule } from "./utils";

const renderLastRun = (last: LastExecutionSummary, onView: () => void) => {
    const whenEpoch = last.completedAt ?? last.startedAt ?? last.scheduledFor;
    const when = new Date(whenEpoch).toISOString();
    const duration = last.durationMs ? ` · ${formatDuration(last.durationMs)}` : "";
    let Icon = CheckCircle2;
    let iconClass = "text-(--success-wMain)";
    let label = "Last run";

    switch (last.status) {
        case "completed":
            Icon = CheckCircle2;
            iconClass = "text-(--success-wMain)";
            label = "Succeeded";
            break;
        case "failed":
            Icon = XCircle;
            iconClass = "text-(--error-wMain)";
            label = "Failed";
            break;
        case "timeout":
            Icon = AlertCircle;
            iconClass = "text-(--warning-wMain)";
            label = "Timed out";
            break;
        case "running":
        case "pending":
            Icon = Loader2;
            iconClass = "animate-spin text-(--info-wMain)";
            label = last.status === "running" ? "Running" : "Pending";
            break;
        case "skipped":
            Icon = AlertCircle;
            iconClass = "text-(--secondary-text-wMain)";
            label = "Skipped";
            break;
        case "cancelled":
            Icon = XCircle;
            iconClass = "text-(--secondary-text-wMain)";
            label = "Cancelled";
            break;
    }

    return (
        <button
            type="button"
            onClick={e => {
                e.stopPropagation();
                onView();
            }}
            className="flex w-full items-center gap-1 truncate text-left text-xs text-(--secondary-text-wMain) hover:text-(--primary-text-wMain)"
            title={last.errorMessage ?? `${label} · ${formatRelativeTime(when)}${duration}`}
        >
            <Icon className={`h-3 w-3 flex-shrink-0 ${iconClass}`} />
            <span className="truncate">
                {label} {formatRelativeTime(when)}
                {duration}
            </span>
        </button>
    );
};

interface TaskCardProps {
    task: ScheduledTask;
    isSelected?: boolean;
    onTaskClick: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
    onViewExecutions: (task: ScheduledTask) => void;
    onRunNow?: (task: ScheduledTask) => void;
    isRunNowPending?: boolean;
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, isSelected = false, onTaskClick, onEdit, onDelete, onToggleEnabled, onViewExecutions, onRunNow, isRunNowPending = false }) => {
    const [dropdownOpen, setDropdownOpen] = useState(false);

    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onEdit(task);
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onDelete(task.id);
    };

    const handleToggleEnabled = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onToggleEnabled(task);
    };

    const handleViewExecutions = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onViewExecutions(task);
    };

    const handleRunNow = (e: Event | React.MouseEvent) => {
        (e as React.MouseEvent).stopPropagation?.();
        setDropdownOpen(false);
        onRunNow?.(task);
    };

    // One-time tasks are terminal after their run — rerunning doesn't fit the model.
    // Config-sourced tasks are read-only, so manual Run Now would be surprising.
    const canRunNow = !!onRunNow && task.scheduleType !== "one_time" && task.source !== "config";

    const statusConfig: Record<TaskStatus, { label: string; className: string }> = {
        active: { label: "Active", className: "bg-(--success-w10) text-(--success-w100)" },
        paused: { label: "Paused", className: "bg-(--warning-w10) text-(--warning-w100)" },
        error: { label: "Error", className: "bg-(--error-w10) text-(--error-w100)" },
    };

    const formatNextRun = (task: ScheduledTask): string => {
        if (task.status === "paused") return "Paused";

        if (!task.nextRunAt) {
            // One-time tasks clear nextRunAt after completion
            if (task.scheduleType === "one_time" && task.lastRunAt) return "Completed";
            return "Not scheduled";
        }

        const now = Date.now();
        const diff = task.nextRunAt - now;

        if (diff >= 0) {
            if (diff < 60000) return "In < 1 minute";
            if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
            if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
            return `In ${Math.floor(diff / 86400000)} days`;
        }

        // nextRunAt is in the past — task likely ran or is running
        if (task.lastRunAt && task.lastRunAt >= task.nextRunAt - 60000) {
            return "Ran recently";
        }

        return "Overdue";
    };

    return (
        <GridCard onClick={onTaskClick} isSelected={isSelected}>
            <div className="flex h-full w-full flex-col">
                <div className="flex items-center justify-between px-4">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Calendar className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                        <div className="min-w-0">
                            <h2 className="truncate text-lg font-semibold" title={task.name}>
                                {task.name}
                            </h2>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={e => {
                                        e.stopPropagation();
                                        setDropdownOpen(!dropdownOpen);
                                    }}
                                    tooltip="Actions"
                                    className="cursor-pointer"
                                >
                                    <MoreHorizontal size={16} />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={e => e.stopPropagation()}>
                                {canRunNow && (
                                    <DropdownMenuItem onSelect={handleRunNow} disabled={isRunNowPending}>
                                        <Zap size={14} className="mr-2" />
                                        {isRunNowPending ? "Running…" : "Run Now"}
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={handleEdit}>
                                    <Pencil size={14} className="mr-2" />
                                    Edit Task
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={handleViewExecutions}>
                                    <History size={14} className="mr-2" />
                                    View Execution History
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={handleToggleEnabled}>
                                    {task.enabled ? (
                                        <>
                                            <Pause size={14} className="mr-2" />
                                            Pause Task
                                        </>
                                    ) : (
                                        <>
                                            <Play size={14} className="mr-2" />
                                            Enable Task
                                        </>
                                    )}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={handleDelete}>
                                    <Trash2 size={14} className="mr-2" />
                                    Delete Task
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
                <div className="flex flex-grow flex-col overflow-hidden px-4">
                    <div className="mb-2 flex items-center gap-2">
                        {task.status && (
                            <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusConfig[task.status]?.className ?? "bg-(--secondary-w10) text-(--secondary-text-wMain)"}`}>{statusConfig[task.status]?.label ?? task.status}</span>
                        )}
                        {task.source === "config" && <span className="inline-block rounded-full bg-(--info-w10) px-2 py-0.5 text-xs text-(--info-w100)">Config</span>}
                    </div>
                    {task.description && (
                        <div className="mb-2 line-clamp-1 text-sm leading-5" title={task.description}>
                            {task.description}
                        </div>
                    )}
                    <div className="mt-auto space-y-1">
                        <div className="flex items-center gap-1 text-xs text-(--secondary-text-wMain)">
                            <Clock className="h-3 w-3" />
                            <span className="truncate">{formatSchedule(task)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-(--secondary-text-wMain)">
                            <Calendar className="h-3 w-3" />
                            <span>Next: {formatNextRun(task)}</span>
                        </div>
                        {task.lastExecution && renderLastRun(task.lastExecution, () => onViewExecutions(task))}
                        <div className="text-xs text-(--secondary-text-wMain)">
                            <span className="truncate">
                                {task.targetType === "workflow" ? "Workflow" : "Agent"}: {task.targetAgentName}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </GridCard>
    );
};
