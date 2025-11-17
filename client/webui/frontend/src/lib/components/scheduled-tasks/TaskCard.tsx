import React, { useState } from "react";
import { Pencil, Trash2, Calendar, Clock, MoreHorizontal, Play, Pause, History } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import {
    Button,
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/lib/components/ui";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

interface TaskCardProps {
    task: ScheduledTask;
    isSelected?: boolean;
    onTaskClick: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
    onViewExecutions: (task: ScheduledTask) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({
    task,
    isSelected = false,
    onTaskClick,
    onEdit,
    onDelete,
    onToggleEnabled,
    onViewExecutions,
}) => {
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

    const formatSchedule = (task: ScheduledTask): string => {
        if (task.schedule_type === "cron") {
            // Parse common cron patterns into human-readable format
            const cron = task.schedule_expression;
            const parts = cron.trim().split(/\s+/);
            
            if (parts.length === 5) {
                const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
                
                // Hourly pattern (e.g., "0 */6 * * *")
                if (hour.includes('/')) {
                    const interval = hour.split('/')[1];
                    return `Every ${interval} hours`;
                }
                
                // Weekly pattern (e.g., "0 9 * * 1,3,5")
                if (dayOfWeek !== '*') {
                    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
                    const days = dayOfWeek.split(',').map(d => dayNames[parseInt(d)]).join(', ');
                    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
                    return `${days} at ${time}`;
                }
                
                // Monthly pattern (e.g., "0 9 15 * *")
                if (dayOfMonth !== '*') {
                    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
                    return `Monthly on day ${dayOfMonth} at ${time}`;
                }
                
                // Daily pattern (e.g., "0 9 * * *")
                if (hour !== '*' && minute !== '*') {
                    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
                    return `Daily at ${time}`;
                }
            }
            
            // Fallback to showing cron expression
            return `Cron: ${cron}`;
        } else if (task.schedule_type === "interval") {
            return `Every ${task.schedule_expression}`;
        } else {
            try {
                return `Once at ${new Date(task.schedule_expression).toLocaleString()}`;
            } catch {
                return `Once at ${task.schedule_expression}`;
            }
        }
    };

    const formatNextRun = (timestamp?: number): string => {
        if (!timestamp) return "Not scheduled";
        const date = new Date(timestamp);
        const now = new Date();
        const diff = date.getTime() - now.getTime();

        if (diff < 0) return "Overdue";
        if (diff < 60000) return "In < 1 minute";
        if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
        if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
        return `In ${Math.floor(diff / 86400000)} days`;
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
                        <span
                            className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                                task.enabled
                                    ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                    : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                            }`}
                        >
                            {task.enabled ? "Enabled" : "Disabled"}
                        </span>
                    </div>
                    {task.description && (
                        <div className="mb-3 line-clamp-2 text-sm leading-5">
                            {task.description}
                        </div>
                    )}
                    <div className="mt-auto space-y-1">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            <span className="truncate">{formatSchedule(task)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            <span>Next: {formatNextRun(task.next_run_at)}</span>
                        </div>
                        <div className="text-xs text-muted-foreground">
                            <span className="truncate">Agent: {task.target_agent_name}</span>
                        </div>
                    </div>
                </div>
            </div>
        </GridCard>
    );
};