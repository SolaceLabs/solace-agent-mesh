import React, { useEffect, useLayoutEffect, useState } from "react";
import { Loader2, MessageSquare } from "lucide-react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { Button } from "@/lib/components/ui";
import { formatDuration, formatEpochTimestampShort } from "@/lib/utils/format";
import { getStatusBadge, IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { Metric, executionDisplayName } from "./helpers";
import { ExecutionOutput } from "./ExecutionOutput";

interface LatestExecutionPanelProps {
    execution: TaskExecution | null;
    onGoToChat: (executionId: string) => void;
    /** Called when the user clicks "Show more" on a truncated snippet. */
    onShowFullOutput: (executionId: string) => void;
}

/**
 * Detect whether `node`'s rendered height exceeds its clientHeight — i.e.
 * `line-clamp` (or `overflow: hidden`) is actually cutting content off.
 * Re-checks on resize so the "Show more" affordance appears/disappears as
 * the box width changes.
 */
function useIsOverflowing(node: HTMLElement | null): boolean {
    const [overflowing, setOverflowing] = useState(false);

    useLayoutEffect(() => {
        if (!node) {
            setOverflowing(false);
            return;
        }
        const check = () => setOverflowing(node.scrollHeight > node.clientHeight + 1);
        check();
        const observer = new ResizeObserver(check);
        observer.observe(node);
        return () => observer.disconnect();
    }, [node]);

    return overflowing;
}

export const LatestExecutionPanel: React.FC<LatestExecutionPanelProps> = ({ execution, onGoToChat, onShowFullOutput }) => {
    if (!execution) {
        return <div className="rounded-md border bg-(--background-w10) p-6 text-sm text-(--secondary-text-wMain) italic">No executions yet.</div>;
    }

    const isInFlight = IN_PROGRESS_STATUSES.has(execution.status);
    const completedAt = execution.completedAt ? formatEpochTimestampShort(execution.completedAt) : "—";
    const duration = execution.durationMs ? formatDuration(execution.durationMs) : "—";

    return (
        <section className="space-y-4">
            <div className="-mt-6 -ml-8 flex items-start justify-between gap-8 border-b py-3 pl-8">
                <div className="min-w-0 flex-shrink-0">
                    <div className="text-xs text-(--secondary-text-wMain)">Latest Execution</div>
                    <div className="truncate text-base font-semibold" title={executionDisplayName(execution)}>
                        {executionDisplayName(execution)}
                    </div>
                </div>
                <div className="flex flex-1 items-center gap-8">
                    <Metric label="Status">{getStatusBadge(execution.status)}</Metric>
                    <Metric label="Completed On">{completedAt}</Metric>
                    <Metric label="Duration">{isInFlight ? <Loader2 className="h-4 w-4 animate-spin text-(--brand-wMain)" /> : duration}</Metric>
                </div>
                <Button onClick={() => onGoToChat(execution.id)} disabled={isInFlight && !execution.startedAt}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    View Chat Output
                </Button>
            </div>

            <div>
                <div className="mb-2 text-sm font-semibold">Output Summary</div>
                <OutputSummary execution={execution} onShowFullOutput={onShowFullOutput} />
            </div>
        </section>
    );
};

/**
 * The clamped snippet box plus a "Show more" link rendered only when the
 * content actually overflows its 6-line clamp. The full reader lives on the
 * per-execution detail view; the link opens that view via the parent's
 * URL-driven selection handler.
 */
const OutputSummary: React.FC<{ execution: TaskExecution; onShowFullOutput: (id: string) => void }> = ({ execution, onShowFullOutput }) => {
    const snippetText = execution.resultSummary?.agentResponse || execution.resultSummary?.agentResponseFull || "";
    const [contentNode, setContentNode] = useState<HTMLDivElement | null>(null);
    const overflowing = useIsOverflowing(contentNode);

    // Force a re-check after the inner content mounts/changes (text length or
    // streaming updates can flip overflow state without a resize event).
    const stringSignature = `${snippetText.length}:${execution.id}`;
    useEffect(() => {
        // Trigger a re-measure by reading scrollHeight on the next frame.
        if (!contentNode) return;
        const id = requestAnimationFrame(() => {
            // ResizeObserver doesn't fire on content-only changes; nudge the
            // state by re-reading the latest dimensions.
            contentNode.dispatchEvent(new Event("transitionend"));
        });
        return () => cancelAnimationFrame(id);
    }, [contentNode, stringSignature]);

    if (!snippetText && execution.errorMessage) {
        return (
            <div className="rounded-md border bg-(--background-w10) p-4">
                <span className="line-clamp-6 whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</span>
            </div>
        );
    }
    if (!snippetText) {
        return (
            <div className="rounded-md border bg-(--background-w10) p-4">
                <span className="text-(--secondary-text-wMain) italic">No output yet.</span>
            </div>
        );
    }

    return (
        <div className="rounded-md border bg-(--background-w10) p-4">
            <div ref={setContentNode} className="line-clamp-6 text-sm break-words [&_p]:my-0">
                <ExecutionOutput executionId={execution.id} text={snippetText} hideArtifacts ragData={execution.resultSummary?.ragData} />
            </div>
            {overflowing && (
                <button type="button" onClick={() => onShowFullOutput(execution.id)} className="mt-2 text-xs font-medium text-(--brand-wMain) hover:underline">
                    Show more
                </button>
            )}
        </div>
    );
};
