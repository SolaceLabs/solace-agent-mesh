/**
 * UserInputMessage — Renders a HIL (Human-in-the-Loop) surface in the chat.
 *
 * Uses the generic A2UI renderer. The renderer doesn't know or care whether
 * this is a tool approval, question form, or any other surface type — it just
 * renders whatever the backend sent.
 */

import { useState, useCallback } from "react";
import { CheckCircle, Clock, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { useChatContext } from "@/lib/hooks";
import type { MessageFE } from "@/lib/types";

import { A2UISurfaceRenderer } from "./A2UIRenderer";
import type { SurfaceAction } from "./types";

function StatusBanner({ icon, text }: { icon: React.ReactNode; text: string }) {
    return (
        <div className="flex w-full items-center gap-2 rounded-lg border bg-card px-4 py-2.5 text-sm text-muted-foreground shadow-sm">
            {icon}
            {text}
        </div>
    );
}

export function UserInputMessage({ message }: { message: MessageFE }) {
    const req = message.userInputRequest;
    const { setMessages } = useChatContext();
    const [isSubmitting, setIsSubmitting] = useState(false);

    const updateMessage = useCallback(
        (update: Partial<NonNullable<MessageFE["userInputRequest"]>>) => {
            setMessages((prev: MessageFE[]) =>
                prev.map(msg =>
                    msg.metadata?.messageId === message.metadata?.messageId && msg.userInputRequest
                        ? { ...msg, userInputRequest: { ...msg.userInputRequest, ...update } }
                        : msg,
                ),
            );
        },
        [setMessages, message.metadata?.messageId],
    );

    const handleAction = useCallback(
        async (action: SurfaceAction) => {
            if (!req) return;
            setIsSubmitting(true);
            try {
                if (action.eventName === "cancel") {
                    await api.webui.post("/api/v1/user-input/respond", {
                        task_id: req.taskId,
                        agent_name: req.agentName,
                        request_id: req.requestId,
                        status: "cancelled",
                        data: {},
                    });
                } else {
                    // "submit" — send the action context as data.
                    await api.webui.post("/api/v1/user-input/respond", {
                        task_id: req.taskId,
                        agent_name: req.agentName,
                        request_id: req.requestId,
                        status: "answered",
                        data: action.context,
                    });
                }
                updateMessage({ responded: true, responseText: action.completionText });
            } catch (err) {
                console.error("Failed to submit HIL response:", err);
            } finally {
                setIsSubmitting(false);
            }
        },
        [req, updateMessage],
    );

    if (!req) return null;

    if (req.responded) {
        return <StatusBanner icon={<CheckCircle className="size-4 text-[var(--color-success-wMain)]" />} text={req.responseText || "Response submitted"} />;
    }
    if (req.timedOut) {
        return <StatusBanner icon={<Clock className="size-4" />} text="Request timed out" />;
    }

    return (
        <A2UISurfaceRenderer
            surface={req.surface}
            onAction={handleAction}
            disabled={isSubmitting}
            expiresAt={req.expiresAt}
        />
    );
}

export function CancelledBanner() {
    return (
        <div className="flex w-full items-center gap-2 rounded-lg border bg-card px-4 py-2.5 text-sm text-muted-foreground shadow-sm">
            <XCircle className="size-4" />
            Request was cancelled
        </div>
    );
}

export function TimedOutBanner() {
    return (
        <div className="flex w-full items-center gap-2 rounded-lg border bg-card px-4 py-2.5 text-sm text-muted-foreground shadow-sm">
            <Clock className="size-4" />
            Request timed out
        </div>
    );
}
