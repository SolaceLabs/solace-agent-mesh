import React from "react";
import { FileText, ChevronRight, ChevronLeft, MessageCircle } from "lucide-react";
import type { ScheduledTask, TaskExecution, ArtifactInfo } from "@/lib/types/scheduled-tasks";
import { Button, Label } from "@/lib/components/ui";
import { MarkdownHTMLConverter } from "@/lib/components/common/MarkdownHTMLConverter";
import { formatEpochTimestamp, formatDuration } from "@/lib/utils/format";
import { getStatusBadge } from "./ExecutionList";

interface ExecutionDetailProps {
    execution: TaskExecution | null;
    task: ScheduledTask;
    previewArtifact: ArtifactInfo | null;
    onPreviewArtifact: (artifact: ArtifactInfo) => void;
    onGoToChat: (executionId: string) => void;
}

const renderResponse = (execution: TaskExecution) => {
    const summary = execution.resultSummary;
    if (!summary) return <p className="text-(--secondary-text-wMain)">No response available</p>;

    if (summary.agentResponse) {
        return (
            <div className="rounded bg-(--secondary-w10) p-3 text-sm">
                <MarkdownHTMLConverter>{summary.agentResponse}</MarkdownHTMLConverter>
            </div>
        );
    }

    if (summary.messages && Array.isArray(summary.messages) && summary.messages.length > 0) {
        return (
            <div className="space-y-3">
                {summary.messages.map((msg: { role: string; text: string }, idx: number) => (
                    <div key={idx} className="space-y-1">
                        <div className="text-xs font-medium text-(--secondary-text-wMain) capitalize">{msg.role || "Unknown"}</div>
                        <div className="rounded bg-(--secondary-w10) p-3 text-sm">
                            <MarkdownHTMLConverter>{msg.text || "No content"}</MarkdownHTMLConverter>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    return <p className="text-(--secondary-text-wMain)">No response data available</p>;
};

const renderArtifacts = (execution: TaskExecution, previewArtifact: ArtifactInfo | null, onPreviewArtifact: (artifact: ArtifactInfo) => void) => {
    const topLevelArtifacts = execution.artifacts || [];
    const summaryArtifacts = execution.resultSummary?.artifacts || [];

    const allArtifacts = [...topLevelArtifacts.map(a => (typeof a === "string" ? { name: a, uri: `artifact://${a}` } : a)), ...summaryArtifacts];

    if (allArtifacts.length === 0) {
        return <p className="text-sm text-(--secondary-text-wMain)">No artifacts generated</p>;
    }

    return (
        <div className="space-y-2">
            {allArtifacts.map((artifact, idx: number) => {
                const isViewable = artifact.uri?.startsWith("http") || artifact.uri?.startsWith("/") || artifact.uri?.startsWith("artifact://");
                const filename = artifact.name || artifact.uri?.split("/").pop() || `artifact-${idx + 1}`;

                const artifactInfo: ArtifactInfo = {
                    name: filename,
                    uri: artifact.uri || "",
                };

                const isCurrentlyPreviewed = previewArtifact?.name === filename;

                return (
                    <button
                        key={idx}
                        onClick={() => isViewable && onPreviewArtifact(artifactInfo)}
                        disabled={!isViewable}
                        className={`group flex w-full items-center justify-between rounded p-3 text-left transition-colors ${
                            isViewable ? (isCurrentlyPreviewed ? "border border-(--primary-w20) bg-(--primary-w10)" : "cursor-pointer bg-(--secondary-w10) hover:bg-(--primary-w10)") : "cursor-not-allowed bg-(--secondary-w10) opacity-60"
                        }`}
                    >
                        <div className="flex min-w-0 flex-1 items-center gap-2">
                            <FileText className="size-4 flex-shrink-0 text-(--secondary-text-wMain)" />
                            <span className={`truncate text-sm ${isViewable ? (isCurrentlyPreviewed ? "font-medium text-(--primary-wMain)" : "group-hover:text-(--primary-wMain)") : ""}`} title={filename}>
                                {filename}
                            </span>
                        </div>
                        {isViewable &&
                            (isCurrentlyPreviewed ? <ChevronLeft className="size-4 text-(--primary-wMain) transition-colors" /> : <ChevronRight className="size-4 text-(--secondary-text-wMain) transition-colors group-hover:text-(--primary-wMain)" />)}
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
        try {
            const date = new Date(task.scheduleExpression);
            return date.toLocaleString();
        } catch {
            return task.scheduleExpression;
        }
    }
    return task.scheduleExpression;
};

export const ExecutionDetail: React.FC<ExecutionDetailProps> = ({ execution, task, previewArtifact, onPreviewArtifact, onGoToChat }) => {
    if (!execution) {
        return (
            <div className="flex h-full items-center justify-center">
                <p className="text-(--secondary-text-wMain)">Select an execution to view details</p>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="mx-auto max-w-4xl space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Execution Details</h2>
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => onGoToChat(execution.id)}>
                            <MessageCircle className="mr-1 h-4 w-4" />
                            Go to Chat
                        </Button>
                        {getStatusBadge(execution.status)}
                    </div>
                </div>

                {/* Execution Metadata */}
                <div className="grid grid-cols-2 gap-4 rounded bg-(--secondary-w10) p-4">
                    <div>
                        <Label className="text-xs text-(--secondary-text-wMain)">Started</Label>
                        <div className="mt-1 text-sm">{execution.startedAt ? formatEpochTimestamp(execution.startedAt) : "Pending"}</div>
                    </div>
                    {execution.completedAt && (
                        <div>
                            <Label className="text-xs text-(--secondary-text-wMain)">Completed</Label>
                            <div className="mt-1 text-sm">{formatEpochTimestamp(execution.completedAt)}</div>
                        </div>
                    )}
                    {execution.durationMs && (
                        <div>
                            <Label className="text-xs text-(--secondary-text-wMain)">Duration</Label>
                            <div className="mt-1 text-sm">{formatDuration(execution.durationMs)}</div>
                        </div>
                    )}
                    {execution.retryCount > 0 && (
                        <div>
                            <Label className="text-xs text-(--secondary-text-wMain)">Retries</Label>
                            <div className="mt-1 text-sm">{execution.retryCount}</div>
                        </div>
                    )}
                </div>

                {/* Error Message */}
                {execution.errorMessage && (
                    <div className="space-y-2">
                        <Label className="text-(--color-secondaryText-wMain)">Error</Label>
                        <div className="rounded bg-(--color-error-w20) p-3 text-sm break-words whitespace-pre-wrap text-(--color-error-wMain)">{execution.errorMessage}</div>
                    </div>
                )}

                {/* Agent Response */}
                <div className="space-y-2">
                    <Label className="text-(--color-secondaryText-wMain)">Response (Summary)</Label>
                    {renderResponse(execution)}
                    <p className="text-xs text-(--secondary-text-wMain)">
                        This is a truncated summary.{" "}
                        <button className="underline hover:text-(--primary-text-wMain)" onClick={() => onGoToChat(execution.id)}>
                            Go to Chat
                        </button>{" "}
                        for the full response with inline artifacts.
                    </p>
                </div>

                {/* Artifacts */}
                {((execution.artifacts && execution.artifacts.length > 0) || (execution.resultSummary?.artifacts && execution.resultSummary.artifacts.length > 0)) && (
                    <div className="space-y-2">
                        <Label className="text-(--color-secondaryText-wMain)">Artifacts ({(execution.artifacts?.length || 0) + (execution.resultSummary?.artifacts?.length || 0)})</Label>
                        {renderArtifacts(execution, previewArtifact, onPreviewArtifact)}
                    </div>
                )}

                {/* Task Configuration */}
                <div className="space-y-4 border-t pt-4">
                    <h3 className="text-sm font-semibold">Task Configuration</h3>

                    <div className="space-y-2">
                        <Label className="text-xs text-(--secondary-text-wMain)">Agent</Label>
                        <div className="text-sm">{task.targetAgentName}</div>
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs text-(--secondary-text-wMain)">Schedule</Label>
                        <div className="text-sm">{formatScheduleExpression(task)}</div>
                    </div>

                    {task.taskMessage && task.taskMessage.length > 0 && (
                        <div className="space-y-2">
                            <Label className="text-xs text-(--secondary-text-wMain)">Message</Label>
                            <div className="rounded bg-(--secondary-w10) p-3 text-sm break-words whitespace-pre-wrap">{task.taskMessage.map((part: { text?: string }) => part.text).join("\n")}</div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
