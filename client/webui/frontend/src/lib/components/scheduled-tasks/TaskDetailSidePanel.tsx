import React from "react";
import { X, Calendar, User, MoreHorizontal, Pencil, Trash2, History, Play, Pause } from "lucide-react";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";
import { Button, Tooltip, TooltipContent, TooltipTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Badge } from "@/lib/components/ui";

interface TaskDetailSidePanelProps {
    task: ScheduledTask | null;
    onClose: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string, taskName: string) => void;
    onViewExecutions: (task: ScheduledTask) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
}

// Helper to format schedule in human-readable form
const formatSchedule = (task: ScheduledTask): string => {
    if (task.schedule_type === 'cron') {
        const expr = task.schedule_expression;
        // Parse common cron patterns
        if (expr === '0 9 * * *') return 'Daily at 9:00 AM';
        if (expr === '0 0 * * 0') return 'Weekly on Sunday at midnight';
        if (expr === '0 0 1 * *') return 'Monthly on the 1st at midnight';
        if (expr.startsWith('0 */')) {
            const hours = expr.split(' ')[1].replace('*/', '');
            return `Every ${hours} hours`;
        }
        return `Cron: ${expr}`;
    } else if (task.schedule_type === 'interval') {
        return `Every ${task.schedule_expression}`;
    } else {
        // One-time task - format the ISO timestamp
        try {
            const date = new Date(task.schedule_expression);
            const formatted = date.toLocaleString('en-US', {
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
            return `One time: ${formatted}`;
        } catch {
            return `One time: ${task.schedule_expression}`;
        }
    }
};

// Helper to format timestamp
const formatTimestamp = (timestamp: number): string => {
    // Auto-detect if timestamp is in seconds or milliseconds
    const ts = timestamp < 10000000000 ? timestamp * 1000 : timestamp;
    const date = new Date(ts);
    return date.toLocaleString();
};

export const TaskDetailSidePanel: React.FC<TaskDetailSidePanelProps> = ({
    task,
    onClose,
    onEdit,
    onDelete,
    onViewExecutions,
    onToggleEnabled,
}) => {
    if (!task) return null;

    const handleEdit = () => {
        onEdit(task);
    };

    const handleDelete = () => {
        onDelete(task.id, task.name);
    };

    const handleViewExecutions = () => {
        onViewExecutions(task);
    };

    const handleToggleEnabled = () => {
        onToggleEnabled(task);
    };

    return (
        <div className="bg-background flex h-full w-full flex-col border-l">
            {/* Header */}
            <div className="border-b p-4">
                <div className="mb-2 flex items-center justify-between">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Calendar className="text-muted-foreground h-5 w-5 flex-shrink-0" />
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
                        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0" tooltip="Close">
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant={task.enabled ? "default" : "secondary"}>
                        {task.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Description and Schedule - with background */}
                <div className="bg-muted/50 space-y-6 rounded p-4">
                    {/* Description */}
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Description</h3>
                        <div className="text-sm leading-relaxed">{task.description || "No description provided."}</div>
                    </div>

                    {/* Schedule */}
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Schedule</h3>
                        <div className="text-sm">
                            <div className="font-medium">{formatSchedule(task)}</div>
                            <div className="text-muted-foreground text-xs mt-1">Timezone: {task.timezone}</div>
                        </div>
                    </div>

                    {/* Target Agent */}
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Target Agent</h3>
                        <div className="text-primary bg-primary/10 inline-block rounded px-2 py-0.5 font-mono text-xs">
                            {task.target_agent_name}
                        </div>
                    </div>
                </div>

                {/* Task Message - no background */}
                {task.task_message && task.task_message.length > 0 && (
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Task Message</h3>
                        <div className="bg-muted/30 rounded p-3 font-mono text-xs break-words whitespace-pre-wrap">
                            {task.task_message[0]?.text || "No message"}
                        </div>
                    </div>
                )}

                {/* Execution Stats */}
                {(task.last_run_at || task.next_run_at) && (
                    <div className="bg-muted/50 space-y-4 rounded p-4">
                        <h3 className="text-muted-foreground text-xs font-semibold">Execution Schedule</h3>
                        
                        {task.last_run_at && (
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Last Run:</span>
                                <span className="font-medium">{formatTimestamp(task.last_run_at)}</span>
                            </div>
                        )}
                        
                        {task.next_run_at && (
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Next Run:</span>
                                <span className="font-medium">{formatTimestamp(task.next_run_at)}</span>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Metadata - Sticky at bottom */}
            <div className="bg-background space-y-2 border-t p-4">
                <div className="text-muted-foreground flex items-center gap-2 text-xs">
                    <User size={12} />
                    <span>Created by: {task.created_by || task.user_id || 'System'}</span>
                </div>
                {task.created_at && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Calendar size={12} />
                        <span>Created: {formatTimestamp(task.created_at)}</span>
                    </div>
                )}
                {task.updated_at && task.updated_at !== task.created_at && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Calendar size={12} />
                        <span>Last updated: {formatTimestamp(task.updated_at)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};