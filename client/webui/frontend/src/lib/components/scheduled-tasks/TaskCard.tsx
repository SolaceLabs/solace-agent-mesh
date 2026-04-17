import React, { useState } from "react";
import { Bot, Pencil, Trash2, Calendar, CalendarClock, Clock, MoreHorizontal, Play, Pause, History, Zap, Loader2 } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import type { ScheduledTask, TaskStatus, LastExecutionSummary } from "@/lib/types/scheduled-tasks";
import { formatDuration, formatRelativeTime } from "@/lib/utils/format";
import { formatSchedule } from "./utils";

const lastRunLabel = (last: LastExecutionSummary): string => {
    switch (last.status) {
        case "completed":
            return "Succeeded";
        case "failed":
            return "Failed";
        case "timeout":
            return "Timed out";
        case "skipped":
            return "Skipped";
        case "cancelled":
            return "Cancelled";
        case "running":
            return "Running";
        case "pending":
            return "Pending";
        default:
            return "Last run";
    }
};

const renderLastRun = (last: LastExecutionSummary) => {
    const whenEpoch = last.completedAt ?? last.startedAt ?? last.scheduledFor;
    const whenTs = whenEpoch < 10000000000 ? whenEpoch * 1000 : whenEpoch;
    const whenIso = new Date(whenTs).toISOString();
    const relative = formatRelativeTime(whenIso);
    const absolute = new Date(whenTs).toLocaleString();
    const duration = last.durationMs ? ` · ${formatDuration(last.durationMs)}` : "";
    const label = lastRunLabel(last);

    return (
        <span className="truncate text-xs text-(--secondary-text-wMain)" title={last.errorMessage ?? `${label} · ${absolute}${duration}`}>
            {label} {relative}
        </span>
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

    const statusDotConfig: Record<TaskStatus, { label: string; dotClass: string }> = {
        active: { label: "Active", dotClass: "bg-(--success-wMain)" },
        paused: { label: "Paused", dotClass: "bg-(--warning-wMain)" },
        error: { label: "Error", dotClass: "bg-(--error-wMain)" },
    };

    const isRunning = !!task.lastExecution && (task.lastExecution.status === "running" || task.lastExecution.status === "pending");

    const formatNextRun = (task: ScheduledTask): string => {
        if (task.status === "paused") return "Paused";

        if (task.lastExecution && (task.lastExecution.status === "running" || task.lastExecution.status === "pending")) {
            return "Running now";
        }

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

        return "Due now";
    };

    return (
        <GridCard onClick={onTaskClick} isSelected={isSelected}>
            <div className="flex h-full w-full flex-col">
                <div className="flex items-center justify-between px-4">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <CalendarClock className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
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
                    {task.source === "config" && (
                        <div className="mb-2 flex items-center gap-2">
                            <span className="inline-block rounded-full bg-(--info-w10) px-2 py-0.5 text-xs text-(--info-w100)">Config</span>
                        </div>
                    )}
                    {task.description && (
                        <div className="mb-2 line-clamp-1 text-sm leading-5" title={task.description}>
                            {task.description}
                        </div>
                    )}
                    <div className="mt-auto space-y-1">
                        <div className="flex items-center gap-1.5 text-xs text-(--secondary-text-wMain)">
                            <Clock className="h-3 w-3" />
                            <span className="truncate">{formatSchedule(task)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-(--secondary-text-wMain)">
                            <Calendar className="h-3 w-3" />
                            <span className="truncate">{formatNextRun(task)}</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-(--secondary-text-wMain)">
                            <Bot className="h-3 w-3" />
                            <span className="truncate">{task.targetAgentName}</span>
                        </div>
                        <div className="flex items-center justify-between gap-2 pt-2 text-xs">
                            <div className="flex min-w-0 items-center gap-1.5">
                                {isRunning ? (
                                    <>
                                        <Loader2 className="h-3 w-3 flex-shrink-0 animate-spin text-(--brand-wMain)" />
                                        <span className="truncate font-medium text-(--primary-text-wMain)">Running</span>
                                    </>
                                ) : task.status ? (
                                    <>
                                        <span className={`h-2 w-2 flex-shrink-0 rounded-full ${statusDotConfig[task.status]?.dotClass ?? "bg-(--secondary-wMain)"}`} />
                                        <span className="truncate font-medium text-(--primary-text-wMain)">{statusDotConfig[task.status]?.label ?? task.status}</span>
                                    </>
                                ) : null}
                            </div>
                            {task.lastExecution && !isRunning && renderLastRun(task.lastExecution)}
                        </div>
                    </div>
                </div>
            </div>
        </GridCard>
    );
};
