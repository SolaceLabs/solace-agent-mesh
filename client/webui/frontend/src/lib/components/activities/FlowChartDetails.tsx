import { useMemo, type JSX } from "react";

import { Badge } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

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
    const { messages } = useChatContext();
    const taskStatus = useMemo(() => {
        const loadingMessage = messages.find(message => message.isStatusBubble);

        return task ? getTaskStatus(task, loadingMessage) : null;
    }, [messages, task]);

    return task ? (
        <div className="grid grid-cols-[auto_1fr] grid-rows-[32px_32px] gap-x-8 border-b p-4 leading-[32px]">
            <div className="text-muted-foreground">User</div>
            <div className="truncate" title={task.initialRequestText}>
                {task.initialRequestText}
            </div>
            <div className="text-muted-foreground">Status</div>
            <div className="truncate">{taskStatus}</div>
        </div>
    ) : null;
};
