import React from "react";
import { X, Calendar, User, MoreHorizontal, Pencil, Trash2, History, Play, Pause } from "lucide-react";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";
import { Button, Tooltip, TooltipContent, TooltipTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Badge } from "@/lib/components/ui";
import { formatSchedule } from "./utils";

interface TaskDetailSidePanelProps {
    task: ScheduledTask | null;
    onClose: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string, taskName: string) => void;
    onViewExecutions: (task: ScheduledTask) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
}

// Helper to format timestamp
const formatTimestamp = (timestamp: number): string => {
    // Auto-detect if timestamp is in seconds or milliseconds
    const ts = timestamp < 10000000000 ? timestamp * 1000 : timestamp;
    const date = new Date(ts);
    return date.toLocaleString();
};

export const TaskDetailSidePanel: React.FC<TaskDetailSidePanelProps> = ({ task, onClose, onEdit, onDelete, onViewExecutions, onToggleEnabled }) => {
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
                        <Calendar className="h-5 w-5 flex-shrink-0 text-(--secondary-text-wMain)" />
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
                    <Badge variant={task.status === "active" ? "default" : task.status === "error" ? "destructive" : "secondary"}>
                        {task.status === "active" ? "Active" : task.status === "paused" ? "Paused" : task.status === "error" ? "Error" : task.status}
                    </Badge>
                    {task.source === "config" && <Badge variant="outline">Config</Badge>}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Description and Schedule - with background */}
                <div className="space-y-6 rounded bg-(--secondary-w20) p-4">
                    {/* Description */}
                    <div>
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Description</h3>
                        <div className="text-sm leading-relaxed">{task.description || "No description provided."}</div>
                    </div>

                    {/* Schedule */}
                    <div>
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Schedule</h3>
                        <div className="text-sm">
                            <div className="font-medium">{formatSchedule(task)}</div>
                            <div className="mt-1 text-xs text-(--secondary-text-wMain)">Timezone: {task.timezone}</div>
                        </div>
                    </div>

                    {/* Target Agent/Workflow */}
                    <div>
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Target {task.targetType === "workflow" ? "Workflow" : "Agent"}</h3>
                        <div className="text-primary bg-primary/10 inline-block rounded px-2 py-0.5 font-mono text-xs">{task.targetAgentName}</div>
                    </div>
                </div>

                {/* Task Message - no background */}
                {task.taskMessage && task.taskMessage.length > 0 && (
                    <div>
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Task Message</h3>
                        <div className="rounded bg-(--secondary-w10) p-3 font-mono text-xs break-words whitespace-pre-wrap">{task.taskMessage[0]?.text || "No message"}</div>
                    </div>
                )}

                {/* Execution Stats */}
                {(task.lastRunAt || task.nextRunAt) && (
                    <div className="space-y-4 rounded bg-(--secondary-w20) p-4">
                        <h3 className="text-xs font-semibold text-(--secondary-text-wMain)">Execution Schedule</h3>

                        {task.lastRunAt && (
                            <div className="flex justify-between text-sm">
                                <span className="text-(--secondary-text-wMain)">Last Run:</span>
                                <span className="font-medium">{formatTimestamp(task.lastRunAt)}</span>
                            </div>
                        )}

                        {task.nextRunAt && (
                            <div className="flex justify-between text-sm">
                                <span className="text-(--secondary-text-wMain)">Next Run:</span>
                                <span className="font-medium">{formatTimestamp(task.nextRunAt)}</span>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Metadata - Sticky at bottom */}
            <div className="bg-background space-y-2 border-t p-4">
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
