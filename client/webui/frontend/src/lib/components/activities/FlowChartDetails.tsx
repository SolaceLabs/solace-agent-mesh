import { useMemo, type JSX } from "react";
import { Download } from "lucide-react";

import { Badge, Button } from "@/lib/components/ui";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";

import type { MessageFE, TextPart, VisualizedTask } from "@/lib/types";

import { LoadingMessageRow } from "../chat";

const getStatusBadge = (status: string, type: "info" | "error" | "success") => {
    return (
        <Badge type={type} className={`rounded-full border-none`}>
            <span className="text-xs font-semibold" title={status}>
                {status}
            </span>
        </Badge>
    );
};

const getTaskStatus = (task: VisualizedTask, loadingMessage: MessageFE | undefined): string | JSX.Element => {
    // Prioritize the specific status text from the visualizer if available
    if (task.currentStatusText) {
        return (
            <div title={task.currentStatusText}>
                <LoadingMessageRow statusText={task.currentStatusText} />
            </div>
        );
    }

    const loadingMessageText = loadingMessage?.parts
        ?.filter(p => p.kind === "text")
        .map(p => (p as TextPart).text)
        .join("");

    // Fallback to the overall task status
    switch (task.status) {
        case "submitted":
        case "working":
            return (
                <div title={loadingMessageText || task.status}>
                    <LoadingMessageRow statusText={loadingMessageText || task.status} />
                </div>
            );
        case "input-required":
            return getStatusBadge("Input Required", "info");
        case "completed":
            return getStatusBadge("Completed", "success");
        case "canceled":
            return getStatusBadge("Canceled", "info");
        case "failed":
            return getStatusBadge("Failed", "error");
        default:
            return getStatusBadge("Unknown", "info");
    }
};

export const FlowChartDetails: React.FC<{ task: VisualizedTask }> = ({ task }) => {
    const { messages, addNotification } = useChatContext();
    const { configServerUrl, configFeatureEnablement } = useConfigContext();
    const apiPrefix = useMemo(() => `${configServerUrl}/api/v1`, [configServerUrl]);
    const taskLoggingEnabled = configFeatureEnablement?.taskLogging ?? false;

    const taskStatus = useMemo(() => {
        const loadingMessage = messages.find(message => message.isStatusBubble);

        return task ? getTaskStatus(task, loadingMessage) : null;
    }, [messages, task]);

    const handleDownloadStim = async () => {
        if (!task.taskId) {
            addNotification("Task ID is missing, cannot download.", "error");
            return;
        }

        try {
            const response = await authenticatedFetch(`${apiPrefix}/tasks/${task.taskId}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: `Failed to download: ${response.statusText}` }));
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
            }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${task.taskId}.stim`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            addNotification("Task log download started.", "success");
        } catch (error) {
            console.error("Failed to download .stim file:", error);
            addNotification(`Failed to download task log: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
        }
    };

    return task ? (
        <div className="grid grid-cols-[auto_1fr_auto] grid-rows-[32px_32px] items-center gap-x-8 border-b p-4">
            <div className="text-muted-foreground">User</div>
            <div className="truncate" title={task.initialRequestText}>
                {task.initialRequestText}
            </div>
            {/* Empty cell for alignment */}
            <div />

            <div className="text-muted-foreground">Status</div>
            <div className="truncate">{taskStatus}</div>

            <div>
                {taskLoggingEnabled && (
                    <Button variant="ghost" size="icon" onClick={handleDownloadStim} tooltip="Download Task Log (.stim)">
                        <Download className="size-4" />
                    </Button>
                )}
            </div>
        </div>
    ) : null;
};
