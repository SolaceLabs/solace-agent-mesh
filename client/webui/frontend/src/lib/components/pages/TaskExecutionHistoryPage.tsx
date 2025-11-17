/**
 * Full-page view for scheduled task execution history
 * Shows execution list on left, details on right (similar to VersionHistoryPage)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MoreHorizontal, FileText, ExternalLink } from 'lucide-react';
import type { ScheduledTask, TaskExecution } from '@/lib/types/scheduled-tasks';
import { Header } from '@/lib/components/header';
import { Button, Label } from '@/lib/components/ui';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/lib/components/ui';
import { useChatContext } from '@/lib/hooks';
import { authenticatedFetch } from '@/lib/utils/api';

interface TaskExecutionHistoryPageProps {
    task: ScheduledTask;
    onBack: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (id: string, name: string) => void;
}

export const TaskExecutionHistoryPage: React.FC<TaskExecutionHistoryPageProps> = ({
    task,
    onBack,
    onEdit,
    onDelete,
}) => {
    const { addNotification } = useChatContext();
    const [executions, setExecutions] = useState<TaskExecution[]>([]);
    const [selectedExecution, setSelectedExecution] = useState<TaskExecution | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const hasInitializedRef = useRef(false);

    const fetchExecutions = useCallback(async () => {
        setIsLoading(true);
        try {
            const response = await authenticatedFetch(`/api/v1/scheduled-tasks/${task.id}/executions`, {
                credentials: 'include',
            });
            
            if (response.ok) {
                const data = await response.json();
                // API returns { executions: [], total: number, skip: number, limit: number }
                const executionsList = data.executions || [];
                setExecutions(executionsList);
                
                // Auto-select the first execution on initial load
                if (executionsList.length > 0 && !hasInitializedRef.current) {
                    hasInitializedRef.current = true;
                    setSelectedExecution(executionsList[0]);
                }
            } else {
                console.error('Failed to fetch executions:', response.status, response.statusText);
                addNotification(`Failed to load execution history: ${response.statusText}`, 'error');
            }
        } catch (error) {
            console.error('Failed to fetch executions:', error);
            addNotification('Failed to load execution history', 'error');
        } finally {
            setIsLoading(false);
        }
    }, [task.id, addNotification]);

    useEffect(() => {
        fetchExecutions();
    }, [fetchExecutions]);

    const formatTimestamp = (timestamp: number) => {
        // Check if timestamp is in seconds (< year 3000 in seconds) or milliseconds
        const date = timestamp < 10000000000
            ? new Date(timestamp * 1000)  // Convert seconds to milliseconds
            : new Date(timestamp);         // Already in milliseconds
        return date.toLocaleString();
    };

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
        return `${(ms / 3600000).toFixed(1)}h`;
    };

    const getStatusBadge = (status: string) => {
        const statusConfig = {
            completed: { bg: 'bg-[var(--color-success-w20)]', text: 'text-[var(--color-success-wMain)]', label: 'Completed' },
            failed: { bg: 'bg-[var(--color-error-w20)]', text: 'text-[var(--color-error-wMain)]', label: 'Failed' },
            running: { bg: 'bg-[var(--color-info-w20)]', text: 'text-[var(--color-info-wMain)]', label: 'Running' },
            timeout: { bg: 'bg-[var(--color-warning-w20)]', text: 'text-[var(--color-warning-wMain)]', label: 'Timeout' },
        };
        const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.failed;
        return (
            <span className={`text-xs px-2 py-0.5 rounded-full ${config.bg} ${config.text}`}>
                {config.label}
            </span>
        );
    };

    const renderResponse = (execution: TaskExecution) => {
        const summary = execution.result_summary;
        if (!summary) return <p className="text-muted-foreground">No response available</p>;

        // For RUN_BASED sessions, show agent_response
        if (summary.agent_response) {
            return (
                <div className="space-y-2">
                    <div className="p-3 rounded bg-muted/30 text-sm whitespace-pre-wrap break-words">
                        {summary.agent_response}
                    </div>
                </div>
            );
        }

        // For PERSISTENT sessions, show message history
        if (summary.messages && Array.isArray(summary.messages) && summary.messages.length > 0) {
            return (
                <div className="space-y-3">
                    {summary.messages.map((msg, idx: number) => (
                        <div key={idx} className="space-y-1">
                            <div className="text-xs font-medium text-muted-foreground capitalize">
                                {msg.role || 'Unknown'}
                            </div>
                            <div className="p-3 rounded bg-muted/30 text-sm whitespace-pre-wrap break-words">
                                {msg.text || 'No content'}
                            </div>
                        </div>
                    ))}
                </div>
            );
        }

        return <p className="text-muted-foreground">No response data available</p>;
    };

    const renderArtifacts = (execution: TaskExecution) => {
        const artifacts = execution.result_summary?.artifacts;
        if (!artifacts || artifacts.length === 0) {
            return <p className="text-muted-foreground text-sm">No artifacts generated</p>;
        }

        return (
            <div className="space-y-2">
                {artifacts.map((artifact, idx: number) => {
                    const isViewable = artifact.uri?.startsWith('http') || artifact.uri?.startsWith('/');
                    const filename = artifact.name || artifact.uri?.split('/').pop() || `artifact-${idx + 1}`;
                    
                    return (
                        <div key={idx} className="flex items-center justify-between p-3 rounded bg-muted/30">
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                <FileText className="size-4 text-muted-foreground flex-shrink-0" />
                                <span className="text-sm truncate" title={filename}>
                                    {filename}
                                </span>
                            </div>
                            {isViewable && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => window.open(artifact.uri, '_blank')}
                                    className="flex-shrink-0"
                                >
                                    <ExternalLink className="size-3 mr-1" />
                                    View
                                </Button>
                            )}
                        </div>
                    );
                })}
            </div>
        );
    };

    const formatScheduleExpression = (task: ScheduledTask) => {
        if (task.schedule_type === 'cron') {
            return task.schedule_expression;
        } else if (task.schedule_type === 'interval') {
            return `Every ${task.schedule_expression}`;
        } else if (task.schedule_type === 'one_time') {
            // Parse ISO timestamp and format it
            try {
                const date = new Date(task.schedule_expression);
                return date.toLocaleString();
            } catch {
                return task.schedule_expression;
            }
        }
        return task.schedule_expression;
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header with Breadcrumbs */}
            <Header
                title={task.name}
                breadcrumbs={[
                    { label: "Scheduled Tasks", onClick: onBack },
                    { label: task.name }
                ]}
                buttons={[
                    <DropdownMenu key="actions-menu">
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onEdit(task)}>
                                Edit Task
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onDelete(task.id, task.name)}>
                                Delete Task
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                ]}
            />

            {/* Content */}
            <div className="flex flex-1 min-h-0">
                {/* Left Sidebar - Execution List */}
                <div className="w-[300px] border-r overflow-y-auto">
                    <div className="p-4">
                        <h3 className="text-sm font-semibold text-muted-foreground mb-3">
                            Executions ({executions.length})
                        </h3>
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                            </div>
                        ) : executions.length === 0 ? (
                            <p className="text-sm text-muted-foreground p-4 text-center">
                                No executions yet
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {executions.map((execution) => {
                                    const isSelected = selectedExecution?.id === execution.id;
                                    
                                    return (
                                        <button
                                            key={execution.id}
                                            onClick={() => setSelectedExecution(execution)}
                                            className={`w-full text-left p-3 rounded transition-colors ${
                                                isSelected
                                                    ? 'bg-primary/5 border border-primary/20'
                                                    : 'hover:bg-muted/50'
                                            }`}
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                {getStatusBadge(execution.status)}
                                                <span className="text-xs text-muted-foreground">
                                                    {execution.duration_ms ? formatDuration(execution.duration_ms) : '-'}
                                                </span>
                                            </div>
                                            <span className="text-xs text-muted-foreground block">
                                                {execution.started_at ? formatTimestamp(execution.started_at) : 'Pending'}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Panel - Execution Details */}
                <div className="flex-1 overflow-y-auto">
                    {selectedExecution ? (
                        <div className="p-6">
                            <div className="max-w-4xl mx-auto space-y-6">
                                {/* Header */}
                                <div className="flex items-center justify-between">
                                    <h2 className="text-lg font-semibold">
                                        Execution Details
                                    </h2>
                                    {getStatusBadge(selectedExecution.status)}
                                </div>

                                {/* Execution Metadata */}
                                <div className="grid grid-cols-2 gap-4 p-4 rounded bg-muted/30">
                                    <div>
                                        <Label className="text-xs text-muted-foreground">Started</Label>
                                        <div className="text-sm mt-1">
                                            {selectedExecution.started_at ? formatTimestamp(selectedExecution.started_at) : 'Pending'}
                                        </div>
                                    </div>
                                    {selectedExecution.completed_at && (
                                        <div>
                                            <Label className="text-xs text-muted-foreground">Completed</Label>
                                            <div className="text-sm mt-1">
                                                {formatTimestamp(selectedExecution.completed_at)}
                                            </div>
                                        </div>
                                    )}
                                    {selectedExecution.duration_ms && (
                                        <div>
                                            <Label className="text-xs text-muted-foreground">Duration</Label>
                                            <div className="text-sm mt-1">
                                                {formatDuration(selectedExecution.duration_ms)}
                                            </div>
                                        </div>
                                    )}
                                    {selectedExecution.retry_count > 0 && (
                                        <div>
                                            <Label className="text-xs text-muted-foreground">Retries</Label>
                                            <div className="text-sm mt-1">
                                                {selectedExecution.retry_count}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Error Message */}
                                {selectedExecution.error_message && (
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Error</Label>
                                        <div className="p-3 rounded bg-[var(--color-error-w20)] text-[var(--color-error-wMain)] text-sm whitespace-pre-wrap break-words">
                                            {selectedExecution.error_message}
                                        </div>
                                    </div>
                                )}

                                {/* Agent Response */}
                                <div className="space-y-2">
                                    <Label className="text-[var(--color-secondaryText-wMain)]">Response</Label>
                                    {renderResponse(selectedExecution)}
                                </div>

                                {/* Artifacts */}
                                {selectedExecution.result_summary?.artifacts && selectedExecution.result_summary.artifacts.length > 0 && (
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">
                                            Artifacts ({selectedExecution.result_summary.artifacts.length})
                                        </Label>
                                        {renderArtifacts(selectedExecution)}
                                    </div>
                                )}

                                {/* Task Configuration */}
                                <div className="pt-4 border-t space-y-4">
                                    <h3 className="text-sm font-semibold">Task Configuration</h3>
                                    
                                    <div className="space-y-2">
                                        <Label className="text-xs text-muted-foreground">Agent</Label>
                                        <div className="text-sm">{task.target_agent_name}</div>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-xs text-muted-foreground">Schedule</Label>
                                        <div className="text-sm">{formatScheduleExpression(task)}</div>
                                    </div>

                                    {task.task_message && task.task_message.length > 0 && (
                                        <div className="space-y-2">
                                            <Label className="text-xs text-muted-foreground">Message</Label>
                                            <div className="text-sm p-3 rounded bg-muted/30 whitespace-pre-wrap break-words">
                                                {task.task_message.map(part => part.text).join('\n')}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-muted-foreground">Select an execution to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};