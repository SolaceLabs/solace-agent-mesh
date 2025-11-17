/**
 * Full-page view for scheduled task execution history
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MoreHorizontal, FileText, Download, ArrowLeft, ChevronRight, ChevronLeft } from 'lucide-react';
import type { ScheduledTask, TaskExecution, ArtifactInfo } from '@/lib/types/scheduled-tasks';
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
import { ContentRenderer } from '@/lib/components/chat/preview/ContentRenderer';
import { getRenderType } from '@/lib/components/chat/preview/previewUtils';

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
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactInfo | null>(null);
    const [artifactContent, setArtifactContent] = useState<string | null>(null);
    const [loadingArtifact, setLoadingArtifact] = useState(false);
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

    const handlePreviewArtifact = async (artifact: ArtifactInfo) => {
        // Toggle: if clicking the same artifact, close the panel
        if (previewArtifact && previewArtifact.name === artifact.name) {
            setPreviewArtifact(null);
            setArtifactContent(null);
            return;
        }
        
        setPreviewArtifact(artifact);
        setArtifactContent(null);
        
        if (artifact.uri) {
            setLoadingArtifact(true);
            try {
                const response = await authenticatedFetch(artifact.uri, {
                    credentials: 'include',
                });
                
                if (response.ok) {
                    const content = await response.text();
                    setArtifactContent(content);
                } else {
                    addNotification(`Failed to load artifact: ${response.statusText}`, 'error');
                }
            } catch (error) {
                console.error('Failed to load artifact:', error);
                addNotification('Failed to load artifact content', 'error');
            } finally {
                setLoadingArtifact(false);
            }
        }
    };

    const renderArtifacts = (execution: TaskExecution) => {
        // Artifacts can be in execution.artifacts (top-level) or execution.result_summary.artifacts
        const topLevelArtifacts = execution.artifacts || [];
        const summaryArtifacts = execution.result_summary?.artifacts || [];
        
        // Combine and normalize artifacts
        const allArtifacts = [
            ...topLevelArtifacts.map(a => typeof a === 'string' ? { name: a, uri: `artifact://${a}` } : a),
            ...summaryArtifacts
        ];
        
        if (allArtifacts.length === 0) {
            return <p className="text-muted-foreground text-sm">No artifacts generated</p>;
        }

        return (
            <div className="space-y-2">
                {allArtifacts.map((artifact, idx: number) => {
                    const isViewable = artifact.uri?.startsWith('http') || artifact.uri?.startsWith('/');
                    const filename = artifact.name || artifact.uri?.split('/').pop() || `artifact-${idx + 1}`;
                    
                    const artifactInfo: ArtifactInfo = {
                        name: filename,
                        uri: artifact.uri || ''
                    };
                    
                    const isCurrentlyPreviewed = previewArtifact?.name === filename;
                    
                    return (
                        <button
                            key={idx}
                            onClick={() => isViewable && handlePreviewArtifact(artifactInfo)}
                            disabled={!isViewable}
                            className={`w-full flex items-center justify-between p-3 rounded transition-colors text-left group ${
                                isViewable
                                    ? isCurrentlyPreviewed
                                        ? 'bg-primary/10 border border-primary/20'
                                        : 'bg-muted/30 hover:bg-primary/10 cursor-pointer'
                                    : 'bg-muted/20 cursor-not-allowed opacity-60'
                            }`}
                        >
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                <FileText className="size-4 text-muted-foreground flex-shrink-0" />
                                <span className={`text-sm truncate ${isViewable ? isCurrentlyPreviewed ? 'text-primary font-medium' : 'group-hover:text-primary' : ''}`} title={filename}>
                                    {filename}
                                </span>
                            </div>
                            {isViewable && (
                                isCurrentlyPreviewed ? (
                                    <ChevronLeft className="size-4 text-primary transition-colors" />
                                ) : (
                                    <ChevronRight className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
                                )
                            )}
                        </button>
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

                {/* Center Panel - Execution Details */}
                <div className={`flex-1 overflow-y-auto ${previewArtifact ? 'border-r' : ''}`}>
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
                                {((selectedExecution.artifacts && selectedExecution.artifacts.length > 0) ||
                                  (selectedExecution.result_summary?.artifacts && selectedExecution.result_summary.artifacts.length > 0)) && (
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">
                                            Artifacts ({(selectedExecution.artifacts?.length || 0) + (selectedExecution.result_summary?.artifacts?.length || 0)})
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

                {/* Right Panel - Artifact Preview (styled like Files tab) */}
                {previewArtifact && (
                    <div className="w-[450px] flex-shrink-0 bg-background flex flex-col">
                        {/* Header with back button (matching Files tab) */}
                        <div className="flex items-center gap-2 border-b p-2">
                            <Button variant="ghost" onClick={() => setPreviewArtifact(null)}>
                                <ArrowLeft />
                            </Button>
                            <div className="text-md font-semibold">Preview</div>
                        </div>

                        <div className="flex min-h-0 flex-1 flex-col gap-2">
                            {/* Artifact Details (matching ArtifactDetails component style) */}
                            <div className="border-b px-4 py-3">
                                <div className="flex flex-row justify-between gap-1">
                                    <div className="flex min-w-0 items-center gap-4">
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2">
                                                <div className="truncate text-sm" title={previewArtifact.name}>
                                                    {previewArtifact.name}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="whitespace-nowrap">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => window.open(`${previewArtifact.uri}?download=true`, '_blank')}
                                            tooltip="Download"
                                        >
                                            <Download />
                                        </Button>
                                    </div>
                                </div>
                            </div>

                            {/* Preview Content (matching ArtifactPanel structure) */}
                            <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
                                {loadingArtifact ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                                    </div>
                                ) : artifactContent ? (
                                    <div className="relative h-full w-full">
                                        {(() => {
                                            const mimeType = 'text/plain';
                                            const rendererType = getRenderType(previewArtifact.name, mimeType);
                                            return rendererType ? (
                                                <ContentRenderer
                                                    content={artifactContent}
                                                    rendererType={rendererType}
                                                    mime_type={mimeType}
                                                    setRenderError={() => {}}
                                                />
                                            ) : (
                                                <pre className="text-sm whitespace-pre-wrap break-words p-4">{artifactContent}</pre>
                                            );
                                        })()}
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center h-full">
                                        <p className="text-muted-foreground text-sm">No content available</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};