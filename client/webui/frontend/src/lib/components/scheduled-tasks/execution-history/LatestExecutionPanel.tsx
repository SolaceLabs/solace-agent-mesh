import React from "react";
import { Loader2, MessageSquare } from "lucide-react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { Button } from "@/lib/components/ui";
import { formatDuration, formatEpochTimestampShort } from "@/lib/utils/format";
import { getStatusBadge, IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { Metric, executionDisplayName, renderOutput } from "./helpers";

interface LatestExecutionPanelProps {
    execution: TaskExecution | null;
    onGoToChat: (executionId: string) => void;
}

export const LatestExecutionPanel: React.FC<LatestExecutionPanelProps> = ({ execution, onGoToChat }) => {
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
                {renderOutput(execution, false)}
            </div>
        </section>
    );
};
