import { useMemo, type JSX } from "react";
import { Download } from "lucide-react";

import { Badge, Button } from "@/lib/components/ui";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import { getErrorMessage } from "@/lib/utils/api";

import type { MessageFE, TextPart, VisualizedTask } from "@/lib/types";

import { LoadingMessageRow } from "../chat";
import { downloadBlob } from "@/lib/utils";
import { api } from "@/lib/api";

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
    const { messages, addNotification, displayError } = useChatContext();
    const { configFeatureEnablement } = useConfigContext();
    const taskLoggingEnabled = configFeatureEnablement?.taskLogging ?? false;

    const taskStatus = useMemo(() => {
        const loadingMessage = messages.find(message => message.isStatusBubble);

        return task ? getTaskStatus(task, loadingMessage) : null;
    }, [messages, task]);

    const handleDownloadStim = async () => {
        try {
            const response = await api.webui.get(`/api/v1/tasks/${task.taskId}`, { fullResponse: true });
            if (!response.ok) {
                throw new Error(`Failed to download task log: ${response.statusText}`);
            }
            const blob = await response.blob();
            downloadBlob(blob, `${task.taskId}.stim`);
            addNotification("Task log downloaded", "success");
        } catch (error) {
            displayError({ title: "Failed to Download Task Log", error: getErrorMessage(error, "An unknown error occurred while downloading the task log.") });
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
                    <Button variant="ghost" size="icon" onClick={handleDownloadStim} tooltip="Download Task Log (.stim)" disabled={!task.taskId}>
                        <Download />
                    </Button>
                )}
            </div>
        </div>
    ) : null;
};
