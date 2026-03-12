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
import type { A2UISurface, MessageFE } from "@/lib/types";

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

interface AnswerEntry {
    question: string;
    answer: string;
}

function ResponseSummary({ icon, entries }: { icon: React.ReactNode; entries: AnswerEntry[] }) {
    return (
        <div className="flex w-full gap-2 rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm">
            <div className="mt-0.5 shrink-0">{icon}</div>
            <div className="flex flex-col gap-1.5">
                {entries.map((entry, i) => (
                    <div key={i}>
                        <span className="text-xs text-muted-foreground/70">{entry.question}</span>
                        <div className="font-medium text-foreground">{entry.answer}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

/** Extract literalString from an A2UI text value. */
function lit(val: unknown): string {
    if (typeof val === "string") return val;
    if (val && typeof val === "object" && "literalString" in val) return String((val as { literalString: string }).literalString);
    return "";
}

/**
 * Build a structured summary from the surface + submitted answers.
 * Returns an array of {question, answer} entries with full question text.
 */
function buildAnswerEntries(surface: A2UISurface, context: Record<string, unknown>): AnswerEntry[] {
    const answers = context.answers as Record<string, unknown> | undefined;
    const otherText = context.other_text as Record<string, string> | undefined;
    if (!answers) return [];

    // Build component index.
    const compById = new Map<string, Record<string, unknown>>();
    for (const c of surface.components) {
        if (c.id) compById.set(c.id, c);
    }

    const entries: AnswerEntry[] = [];
    const keys = Object.keys(answers).sort(); // q0, q1, q2, ...

    for (const qKey of keys) {
        const raw = answers[qKey];
        const other = otherText?.[qKey] ?? "";

        // Resolve the display value.
        let displayValue: string;
        if (Array.isArray(raw)) {
            const selected = (raw as string[]).filter(v => v !== "__other__");
            if ((raw as string[]).includes("__other__") && other) selected.push(other);
            displayValue = selected.join(", ");
        } else if (raw === "__other__" && other) {
            displayValue = other;
        } else {
            displayValue = String(raw ?? "");
        }

        if (!displayValue) continue;

        // Use the full question label text.
        const labelComp = compById.get(`${qKey}-label`);
        const question = labelComp ? lit(labelComp.text) : qKey;

        entries.push({ question, answer: displayValue });
    }

    return entries;
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
                let responseText: string;
                if (action.eventName === "cancel") {
                    responseText = action.completionText;
                } else {
                    const entries = buildAnswerEntries(req.surface, action.context);
                    responseText = entries.length > 0 ? JSON.stringify(entries) : action.completionText;
                }
                updateMessage({ responded: true, responseText });
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
        const icon = <CheckCircle className="size-4 text-[var(--color-success-wMain)]" />;
        // Try to parse structured entries (JSON array); fall back to plain text.
        let entries: AnswerEntry[] | null = null;
        if (req.responseText?.startsWith("[")) {
            try {
                entries = JSON.parse(req.responseText) as AnswerEntry[];
            } catch { /* fall through to plain text */ }
        }
        if (entries && entries.length > 0) {
            return <ResponseSummary icon={icon} entries={entries} />;
        }
        return <StatusBanner icon={icon} text={req.responseText || "Response submitted"} />;
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
