/**
 * Full-page view for scheduled task execution history
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { MoreHorizontal } from "lucide-react";
import type { ScheduledTask, TaskExecution, ArtifactInfo } from "@/lib/types/scheduled-tasks";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useNavigate } from "react-router-dom";
import { useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api/client";
import { useTaskExecutions } from "@/lib/api/scheduled-tasks";
import { ExecutionList } from "@/lib/components/scheduled-tasks/ExecutionList";
import { ExecutionDetail } from "@/lib/components/scheduled-tasks/ExecutionDetail";
import { ArtifactPreviewPanel } from "@/lib/components/scheduled-tasks/ArtifactPreviewPanel";

interface TaskExecutionHistoryPageProps {
    task: ScheduledTask;
    onBack: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (id: string, name: string) => void;
}

/**
 * Convert an artifact URI to an API path the browser can fetch.
 * `artifact://{session_id}/{filename}` → `/api/v1/artifacts/scheduled/{session_id}/{filename}`
 */
const resolveArtifactUri = (uri: string): string => {
    if (uri.startsWith("artifact://")) {
        const path = uri.slice("artifact://".length);
        return `/api/v1/artifacts/scheduled/${path}`;
    }
    return uri;
};

export const TaskExecutionHistoryPage: React.FC<TaskExecutionHistoryPageProps> = ({ task, onBack, onEdit, onDelete }) => {
    const navigate = useNavigate();
    const { addNotification, handleSwitchSession } = useChatContext();
    const [selectedExecution, setSelectedExecution] = useState<TaskExecution | null>(null);
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactInfo | null>(null);
    const [artifactContent, setArtifactContent] = useState<string | null>(null);
    const [artifactMimeType, setArtifactMimeType] = useState<string>("text/plain");
    const [loadingArtifact, setLoadingArtifact] = useState(false);
    const blobUrlRef = useRef<string | null>(null);
    const hasInitializedRef = useRef(false);

    // Use React Query for execution data with smart polling
    const { data, isLoading, refetch } = useTaskExecutions(task.id, 1, 100);
    const executions = data?.executions ?? [];

    // Auto-select first execution on initial load, or refresh selected
    useEffect(() => {
        if (executions.length === 0) return;

        setSelectedExecution(prev => {
            if (!prev && !hasInitializedRef.current) {
                hasInitializedRef.current = true;
                return executions[0];
            }
            if (!prev) return prev;
            const updated = executions.find((e: TaskExecution) => e.id === prev.id);
            return updated || prev;
        });
    }, [executions]);

    // Keep a ref that tracks whether any execution is active so the polling
    // effect below doesn't need `executions` in its dependency array.
    const hasActiveRef = useRef(false);
    useEffect(() => {
        hasActiveRef.current = executions.some(e => e.status === "running" || e.status === "pending");
    }, [executions]);

    // Smart polling: fast when executions are running, slow otherwise, paused when tab hidden.
    useEffect(() => {
        let timerId: ReturnType<typeof setTimeout>;

        const poll = () => {
            if (!document.hidden) {
                refetch();
            }
            timerId = setTimeout(poll, hasActiveRef.current ? 5_000 : 30_000);
        };

        timerId = setTimeout(poll, hasActiveRef.current ? 5_000 : 30_000);

        const onVisibilityChange = () => {
            if (!document.hidden) {
                refetch();
            }
        };
        document.addEventListener("visibilitychange", onVisibilityChange);

        return () => {
            clearTimeout(timerId);
            document.removeEventListener("visibilitychange", onVisibilityChange);
            if (blobUrlRef.current) {
                URL.revokeObjectURL(blobUrlRef.current);
                blobUrlRef.current = null;
            }
        };
    }, [refetch]);

    const handleGoToChat = useCallback(
        async (executionId: string) => {
            await handleSwitchSession(`scheduled_${executionId}`);
            navigate("/chat");
        },
        [handleSwitchSession, navigate]
    );

    const handlePreviewArtifact = useCallback(
        async (artifact: ArtifactInfo) => {
            // Toggle: if clicking the same artifact, close the panel
            if (previewArtifact && previewArtifact.name === artifact.name) {
                setPreviewArtifact(null);
                setArtifactContent(null);
                return;
            }

            setPreviewArtifact(artifact);
            setArtifactContent(null);
            if (blobUrlRef.current) {
                URL.revokeObjectURL(blobUrlRef.current);
                blobUrlRef.current = null;
            }

            if (artifact.uri) {
                setLoadingArtifact(true);
                try {
                    const apiPath = resolveArtifactUri(artifact.uri);
                    const response = await api.webui.get(apiPath, { fullResponse: true });

                    const contentType = response.headers?.get("content-type") || "text/plain";
                    setArtifactMimeType(contentType);
                    const isText = contentType.startsWith("text/") || contentType.includes("json") || contentType.includes("xml") || contentType.includes("javascript") || contentType.includes("csv");
                    if (isText) {
                        const content = await response.text();
                        setArtifactContent(content);
                    } else {
                        const blob = await response.blob();
                        const url = URL.createObjectURL(blob);
                        blobUrlRef.current = url;
                        setArtifactContent(url);
                    }
                } catch (error) {
                    const errorMsg = error instanceof Error ? error.message : "Failed to load artifact content";
                    addNotification(errorMsg, "warning");
                } finally {
                    setLoadingArtifact(false);
                }
            }
        },
        [previewArtifact, addNotification]
    );

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
                <ExecutionList executions={executions} selectedExecution={selectedExecution} onSelect={setSelectedExecution} isLoading={isLoading} />

                {/* Center Panel - Execution Details */}
                <div className={`flex-1 overflow-y-auto ${previewArtifact ? "border-r" : ""}`}>
                    <ExecutionDetail execution={selectedExecution} task={task} previewArtifact={previewArtifact} onPreviewArtifact={handlePreviewArtifact} onGoToChat={handleGoToChat} />
                </div>

                {/* Right Panel - Artifact Preview */}
                {previewArtifact && (
                    <ArtifactPreviewPanel artifact={previewArtifact} content={artifactContent} mimeType={artifactMimeType} isLoading={loadingArtifact} onClose={() => setPreviewArtifact(null)} resolveArtifactUri={resolveArtifactUri} />
                )}
            </div>
        </div>
    );
};
