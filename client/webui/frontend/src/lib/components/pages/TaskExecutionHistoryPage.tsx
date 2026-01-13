/**
 * Full-page view for scheduled task execution history
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { MoreHorizontal, FileText, Download, ArrowLeft, ChevronRight, ChevronLeft } from "lucide-react";
import type { ScheduledTask, TaskExecution, ArtifactInfo } from "@/lib/types/scheduled-tasks";
import { transformApiExecution } from "@/lib/types/scheduled-tasks";
import { Header } from "@/lib/components/header";
import { Button, Label } from "@/lib/components/ui";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api/client";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { getRenderType } from "@/lib/components/chat/preview/previewUtils";

interface TaskExecutionHistoryPageProps {
    task: ScheduledTask;
    onBack: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (id: string, name: string) => void;
}

export const TaskExecutionHistoryPage: React.FC<TaskExecutionHistoryPageProps> = ({ task, onBack, onEdit, onDelete }) => {
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
            const data = await api.webui.get(`/api/v1/scheduled-tasks/${task.id}/executions`);
            // API returns { executions: [], total: number, skip: number, limit: number }
            // Transform from snake_case to camelCase
            const executionsList = (data.executions || []).map(transformApiExecution);
            setExecutions(executionsList);

            // Auto-select the first execution on initial load
            if (executionsList.length > 0 && !hasInitializedRef.current) {
                hasInitializedRef.current = true;
                setSelectedExecution(executionsList[0]);
            }
        } catch (error) {
            console.error("Failed to fetch executions:", error);
            const errorMsg = error instanceof Error ? error.message : "Failed to load execution history";
            addNotification(errorMsg, "warning");
        } finally {
            setIsLoading(false);
        }
    }, [task.id, addNotification]);

    useEffect(() => {
        fetchExecutions();
    }, [fetchExecutions]);

    const formatTimestamp = (timestamp: number) => {
        // Check if timestamp is in seconds (< year 3000 in seconds) or milliseconds
        const date =
            timestamp < 10000000000
                ? new Date(timestamp * 1000) // Convert seconds to milliseconds
                : new Date(timestamp); // Already in milliseconds
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
            completed: { bg: "bg-[var(--color-success-w20)]", text: "text-[var(--color-success-wMain)]", label: "Completed" },
            failed: { bg: "bg-[var(--color-error-w20)]", text: "text-[var(--color-error-wMain)]", label: "Failed" },
            running: { bg: "bg-[var(--color-info-w20)]", text: "text-[var(--color-info-wMain)]", label: "Running" },
            timeout: { bg: "bg-[var(--color-warning-w20)]", text: "text-[var(--color-warning-wMain)]", label: "Timeout" },
        };
        const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.failed;
        return <span className={`rounded-full px-2 py-0.5 text-xs ${config.bg} ${config.text}`}>{config.label}</span>;
    };

    const renderResponse = (execution: TaskExecution) => {
        const summary = execution.resultSummary;
        if (!summary) return <p className="text-muted-foreground">No response available</p>;

        // For RUN_BASED sessions, show agentResponse
        if (summary.agentResponse) {
            return (
                <div className="space-y-2">
                    <div className="bg-muted/30 rounded p-3 text-sm break-words whitespace-pre-wrap">{summary.agentResponse}</div>
                </div>
            );
        }

        // For PERSISTENT sessions, show message history
        if (summary.messages && Array.isArray(summary.messages) && summary.messages.length > 0) {
            return (
                <div className="space-y-3">
                    {summary.messages.map((msg: { role: string; text: string }, idx: number) => (
                        <div key={idx} className="space-y-1">
                            <div className="text-muted-foreground text-xs font-medium capitalize">{msg.role || "Unknown"}</div>
                            <div className="bg-muted/30 rounded p-3 text-sm break-words whitespace-pre-wrap">{msg.text || "No content"}</div>
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
                const response = await api.webui.get(artifact.uri, { fullResponse: true });

                const content = await response.text();
                setArtifactContent(content);
            } catch (error) {
                console.error("Failed to load artifact:", error);
                const errorMsg = error instanceof Error ? error.message : "Failed to load artifact content";
                addNotification(errorMsg, "warning");
            } finally {
                setLoadingArtifact(false);
            }
        }
    };

    const renderArtifacts = (execution: TaskExecution) => {
        // Artifacts can be in execution.artifacts (top-level) or execution.resultSummary.artifacts
        const topLevelArtifacts = execution.artifacts || [];
        const summaryArtifacts = execution.resultSummary?.artifacts || [];

        // Combine and normalize artifacts
        const allArtifacts = [...topLevelArtifacts.map(a => (typeof a === "string" ? { name: a, uri: `artifact://${a}` } : a)), ...summaryArtifacts];

        if (allArtifacts.length === 0) {
            return <p className="text-muted-foreground text-sm">No artifacts generated</p>;
        }

        return (
            <div className="space-y-2">
                {allArtifacts.map((artifact, idx: number) => {
                    const isViewable = artifact.uri?.startsWith("http") || artifact.uri?.startsWith("/");
                    const filename = artifact.name || artifact.uri?.split("/").pop() || `artifact-${idx + 1}`;

                    const artifactInfo: ArtifactInfo = {
                        name: filename,
                        uri: artifact.uri || "",
                    };

                    const isCurrentlyPreviewed = previewArtifact?.name === filename;

                    return (
                        <button
                            key={idx}
                            onClick={() => isViewable && handlePreviewArtifact(artifactInfo)}
                            disabled={!isViewable}
                            className={`group flex w-full items-center justify-between rounded p-3 text-left transition-colors ${
                                isViewable ? (isCurrentlyPreviewed ? "bg-primary/10 border-primary/20 border" : "bg-muted/30 hover:bg-primary/10 cursor-pointer") : "bg-muted/20 cursor-not-allowed opacity-60"
                            }`}
                        >
                            <div className="flex min-w-0 flex-1 items-center gap-2">
                                <FileText className="text-muted-foreground size-4 flex-shrink-0" />
                                <span className={`truncate text-sm ${isViewable ? (isCurrentlyPreviewed ? "text-primary font-medium" : "group-hover:text-primary") : ""}`} title={filename}>
                                    {filename}
                                </span>
                            </div>
                            {isViewable && (isCurrentlyPreviewed ? <ChevronLeft className="text-primary size-4 transition-colors" /> : <ChevronRight className="text-muted-foreground group-hover:text-primary size-4 transition-colors" />)}
                        </button>
                    );
                })}
            </div>
        );
    };

    const formatScheduleExpression = (task: ScheduledTask) => {
        if (task.scheduleType === "cron") {
            return task.scheduleExpression;
        } else if (task.scheduleType === "interval") {
            return `Every ${task.scheduleExpression}`;
        } else if (task.scheduleType === "one_time") {
            // Parse ISO timestamp and format it
            try {
                const date = new Date(task.scheduleExpression);
                return date.toLocaleString();
            } catch {
                return task.scheduleExpression;
            }
        }
        return task.scheduleExpression;
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header with Breadcrumbs */}
            <Header
                title={task.name}
                breadcrumbs={[{ label: "Scheduled Tasks", onClick: onBack }, { label: task.name }]}
                buttons={[
                    <DropdownMenu key="actions-menu">
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onEdit(task)}>Edit Task</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onDelete(task.id, task.name)}>Delete Task</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>,
                ]}
            />

            {/* Content */}
            <div className="flex min-h-0 flex-1">
                {/* Left Sidebar - Execution List */}
                <div className="w-[300px] overflow-y-auto border-r">
                    <div className="p-4">
                        <h3 className="text-muted-foreground mb-3 text-sm font-semibold">Executions ({executions.length})</h3>
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="border-primary size-6 animate-spin rounded-full border-2 border-t-transparent" />
                            </div>
                        ) : executions.length === 0 ? (
                            <p className="text-muted-foreground p-4 text-center text-sm">No executions yet</p>
                        ) : (
                            <div className="space-y-2">
                                {executions.map(execution => {
                                    const isSelected = selectedExecution?.id === execution.id;

                                    return (
                                        <button
                                            key={execution.id}
                                            onClick={() => setSelectedExecution(execution)}
                                            className={`w-full rounded p-3 text-left transition-colors ${isSelected ? "bg-primary/5 border-primary/20 border" : "hover:bg-muted/50"}`}
                                        >
                                            <div className="mb-2 flex items-center justify-between">
                                                {getStatusBadge(execution.status)}
                                                <span className="text-muted-foreground text-xs">{execution.durationMs ? formatDuration(execution.durationMs) : "-"}</span>
                                            </div>
                                            <span className="text-muted-foreground block text-xs">{execution.startedAt ? formatTimestamp(execution.startedAt) : "Pending"}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Center Panel - Execution Details */}
                <div className={`flex-1 overflow-y-auto ${previewArtifact ? "border-r" : ""}`}>
                    {selectedExecution ? (
                        <div className="p-6">
                            <div className="mx-auto max-w-4xl space-y-6">
                                {/* Header */}
                                <div className="flex items-center justify-between">
                                    <h2 className="text-lg font-semibold">Execution Details</h2>
                                    {getStatusBadge(selectedExecution.status)}
                                </div>

                                {/* Execution Metadata */}
                                <div className="bg-muted/30 grid grid-cols-2 gap-4 rounded p-4">
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Started</Label>
                                        <div className="mt-1 text-sm">{selectedExecution.startedAt ? formatTimestamp(selectedExecution.startedAt) : "Pending"}</div>
                                    </div>
                                    {selectedExecution.completedAt && (
                                        <div>
                                            <Label className="text-muted-foreground text-xs">Completed</Label>
                                            <div className="mt-1 text-sm">{formatTimestamp(selectedExecution.completedAt)}</div>
                                        </div>
                                    )}
                                    {selectedExecution.durationMs && (
                                        <div>
                                            <Label className="text-muted-foreground text-xs">Duration</Label>
                                            <div className="mt-1 text-sm">{formatDuration(selectedExecution.durationMs)}</div>
                                        </div>
                                    )}
                                    {selectedExecution.retryCount > 0 && (
                                        <div>
                                            <Label className="text-muted-foreground text-xs">Retries</Label>
                                            <div className="mt-1 text-sm">{selectedExecution.retryCount}</div>
                                        </div>
                                    )}
                                </div>

                                {/* Error Message */}
                                {selectedExecution.errorMessage && (
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Error</Label>
                                        <div className="rounded bg-[var(--color-error-w20)] p-3 text-sm break-words whitespace-pre-wrap text-[var(--color-error-wMain)]">{selectedExecution.errorMessage}</div>
                                    </div>
                                )}

                                {/* Agent Response */}
                                <div className="space-y-2">
                                    <Label className="text-[var(--color-secondaryText-wMain)]">Response</Label>
                                    {renderResponse(selectedExecution)}
                                </div>

                                {/* Artifacts */}
                                {((selectedExecution.artifacts && selectedExecution.artifacts.length > 0) || (selectedExecution.resultSummary?.artifacts && selectedExecution.resultSummary.artifacts.length > 0)) && (
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Artifacts ({(selectedExecution.artifacts?.length || 0) + (selectedExecution.resultSummary?.artifacts?.length || 0)})</Label>
                                        {renderArtifacts(selectedExecution)}
                                    </div>
                                )}

                                {/* Task Configuration */}
                                <div className="space-y-4 border-t pt-4">
                                    <h3 className="text-sm font-semibold">Task Configuration</h3>

                                    <div className="space-y-2">
                                        <Label className="text-muted-foreground text-xs">Agent</Label>
                                        <div className="text-sm">{task.targetAgentName}</div>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-muted-foreground text-xs">Schedule</Label>
                                        <div className="text-sm">{formatScheduleExpression(task)}</div>
                                    </div>

                                    {task.taskMessage && task.taskMessage.length > 0 && (
                                        <div className="space-y-2">
                                            <Label className="text-muted-foreground text-xs">Message</Label>
                                            <div className="bg-muted/30 rounded p-3 text-sm break-words whitespace-pre-wrap">{task.taskMessage.map((part: { text?: string }) => part.text).join("\n")}</div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex h-full items-center justify-center">
                            <p className="text-muted-foreground">Select an execution to view details</p>
                        </div>
                    )}
                </div>

                {/* Right Panel - Artifact Preview (styled like Files tab) */}
                {previewArtifact && (
                    <div className="bg-background flex w-[450px] flex-shrink-0 flex-col">
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
                                        <Button variant="ghost" size="sm" onClick={() => window.open(`${previewArtifact.uri}?download=true`, "_blank")} tooltip="Download">
                                            <Download />
                                        </Button>
                                    </div>
                                </div>
                            </div>

                            {/* Preview Content (matching ArtifactPanel structure) */}
                            <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
                                {loadingArtifact ? (
                                    <div className="flex h-full items-center justify-center">
                                        <div className="border-primary size-8 animate-spin rounded-full border-2 border-t-transparent" />
                                    </div>
                                ) : artifactContent ? (
                                    <div className="relative h-full w-full">
                                        {(() => {
                                            const mimeType = "text/plain";
                                            const rendererType = getRenderType(previewArtifact.name, mimeType);
                                            return rendererType ? (
                                                <ContentRenderer content={artifactContent} rendererType={rendererType} mime_type={mimeType} setRenderError={() => {}} />
                                            ) : (
                                                <pre className="p-4 text-sm break-words whitespace-pre-wrap">{artifactContent}</pre>
                                            );
                                        })()}
                                    </div>
                                ) : (
                                    <div className="flex h-full items-center justify-center">
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
