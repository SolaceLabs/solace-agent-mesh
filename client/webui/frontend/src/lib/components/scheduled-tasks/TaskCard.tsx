import React, { useState } from "react";
import { Pencil, Trash2, Calendar, Clock, MoreHorizontal, Play, Pause, History } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import type { ScheduledTask, TaskStatus } from "@/lib/types/scheduled-tasks";
import { formatSchedule } from "./utils";

interface TaskCardProps {
    task: ScheduledTask;
    isSelected?: boolean;
    onTaskClick: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
    onViewExecutions: (task: ScheduledTask) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, isSelected = false, onTaskClick, onEdit, onDelete, onToggleEnabled, onViewExecutions }) => {
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

    const statusConfig: Record<TaskStatus, { label: string; className: string }> = {
        active: { label: "Active", className: "bg-(--success-w10) text-(--success-w100)" },
        paused: { label: "Paused", className: "bg-(--warning-w10) text-(--warning-w100)" },
        error: { label: "Error", className: "bg-(--error-w10) text-(--error-w100)" },
    };

    const formatNextRun = (task: ScheduledTask): string => {
        if (task.status === "paused") return "Paused";
        if (!task.nextRunAt) return "Not scheduled";

        const now = Date.now();
        const diff = task.nextRunAt - now;

        if (diff >= 0) {
            if (diff < 60000) return "In < 1 minute";
            if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
            if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
            return `In ${Math.floor(diff / 86400000)} days`;
        }

        // nextRunAt is in the past
        // If lastRunAt is close to or after nextRunAt, the task likely ran (or is running)
        if (task.lastRunAt && task.lastRunAt >= task.nextRunAt - 60000) {
            return task.scheduleType === "one_time" ? "Completed" : "Awaiting next schedule";
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
                                            Disable Task
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
                    {task.description && <div className="mb-3 line-clamp-2 text-sm leading-5">{task.description}</div>}
                    <div className="mt-auto space-y-1">
                        <div className="flex items-center gap-1 text-xs text-(--secondary-text-wMain)">
                            <Clock className="h-3 w-3" />
                            <span className="truncate">{formatSchedule(task)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-(--secondary-text-wMain)">
                            <Calendar className="h-3 w-3" />
                            <span>Next: {formatNextRun(task)}</span>
                        </div>
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
