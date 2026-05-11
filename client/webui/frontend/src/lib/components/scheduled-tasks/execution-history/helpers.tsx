import React from "react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { MarkdownWrapper } from "@/lib/components";
import { formatEpochTimestampShort } from "@/lib/utils/format";

export const PAGE_SIZE = 10;

/** Display name for an execution — its scheduled time formatted as
 *  "YYYY-MM-DD HH:MM:SS". Falls back to the ID prefix when no scheduled
 *  timestamp is available. */
export function executionDisplayName(ex: TaskExecution): string {
    if (ex.scheduledFor) return formatEpochTimestampShort(ex.scheduledFor);
    return ex.id.slice(0, 8);
}

/** Label for an execution in the history table / breadcrumbs — completed
 *  time if available, falling back to started / scheduled. */
export const formatExecutionLabel = (ex: TaskExecution): string => {
    const ts = ex.completedAt ?? ex.startedAt ?? ex.scheduledFor;
    return ts ? formatEpochTimestampShort(ts) : "—";
};

// Spell out a duration with the two largest non-zero units, properly pluralized
// (e.g. "30 seconds", "1 minute", "2 hours 5 minutes"). Used in the history
// table where the verbose form reads more naturally than "30s" or "2h 5m".
export function formatDurationVerbose(ms: number): string {
    if (ms < 0 || !isFinite(ms)) return "—";
    if (ms < 1000) return `${Math.round(ms)} ms`;
    const totalSeconds = Math.round(ms / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts: string[] = [];
    const push = (n: number, unit: string) => {
        if (n > 0) parts.push(`${n} ${unit}${n === 1 ? "" : "s"}`);
    };
    push(days, "day");
    push(hours, "hour");
    push(minutes, "minute");
    push(seconds, "second");
    if (parts.length === 0) return "0 seconds";
    return parts.slice(0, 2).join(" ");
}

export const Metric: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <div>
        <div className="mb-1 text-xs text-(--secondary-text-wMain)">{label}</div>
        <div className="text-sm">{children}</div>
    </div>
);

/**
 * Render the agent's response inside a scrollable bordered box. The Latest
 * Execution panel uses the truncated snippet from result_summary.agent_response;
 * the per-execution detail panel uses the untruncated agent_response_full.
 */
export const renderOutput = (execution: TaskExecution, full: boolean) => {
    const text = full ? execution.resultSummary?.agentResponseFull || execution.resultSummary?.agentResponse : execution.resultSummary?.agentResponse;
    const fallback = execution.resultSummary?.messages?.find(m => m.role === "agent")?.text || "";
    const content = text || fallback;
    return (
        <div className="max-h-[16rem] overflow-y-auto rounded-md border bg-(--background-w10) p-4 text-sm break-words">
            {content ? (
                <MarkdownWrapper content={content} className="text-sm" />
            ) : execution.errorMessage ? (
                <span className="whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</span>
            ) : (
                <span className="text-(--secondary-text-wMain) italic">No output yet.</span>
            )}
        </div>
    );
};
