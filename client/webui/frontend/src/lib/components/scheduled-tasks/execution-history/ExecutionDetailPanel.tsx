import React from "react";
import { Loader2 } from "lucide-react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/lib/components/ui";
import { useExecutionArtifacts } from "@/lib/api/scheduled-tasks";
import { ExecutionArtifactsView } from "@/lib/components/scheduled-tasks/ExecutionArtifactsView";
import { formatDuration, formatEpochTimestampShort } from "@/lib/utils/format";
import { getStatusBadge, IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { Metric } from "./helpers";
import { ExecutionOutput } from "./ExecutionOutput";

interface ExecutionDetailPanelProps {
    execution: TaskExecution;
    activeTab: "output" | "artifacts";
    onTabChange: (tab: "output" | "artifacts") => void;
}

export const ExecutionDetailPanel: React.FC<ExecutionDetailPanelProps> = ({ execution, activeTab, onTabChange }) => {
    const { data: artifacts } = useExecutionArtifacts(execution.id);
    const hasArtifacts = (artifacts?.length ?? 0) > 0;

    const isInFlight = IN_PROGRESS_STATUSES.has(execution.status);
    const startedAt = execution.startedAt ? formatEpochTimestampShort(execution.startedAt) : "—";
    const completedAt = execution.completedAt ? formatEpochTimestampShort(execution.completedAt) : "—";
    const duration = execution.durationMs ? formatDuration(execution.durationMs) : "—";

    const metrics = (
        <>
            <Metric label="Status">{getStatusBadge(execution.status)}</Metric>
            <Metric label="Started On">{startedAt}</Metric>
            <Metric label="Completed On">{completedAt}</Metric>
            <Metric label="Duration">{isInFlight ? <Loader2 className="h-4 w-4 animate-spin text-(--brand-wMain)" /> : duration}</Metric>
        </>
    );

    const fullText = execution.resultSummary?.agentResponseFull || execution.resultSummary?.agentResponse || execution.resultSummary?.messages?.find(m => m.role === "agent")?.text || "";

    // Render through ExecutionOutput so `«artifact_return:NAME»` markers in the
    // agent's response inline their artifact card in textual position —
    // matching the chat-page view of the same execution. Artifacts the agent
    // emitted markers for appear inline in flow with the prose; the Artifacts
    // tab next to this one stays as the canonical full list. (The same card
    // appearing in both places is intentional — the inline one is "this is
    // where the agent referred to the file"; the tab is "here are every
    // file produced by this run".)
    const outputBody = !fullText && execution.errorMessage ? <div className="text-sm whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</div> : <ExecutionOutput executionId={execution.id} text={fullText} />;

    if (!hasArtifacts) {
        return (
            <section className="space-y-4">
                <div className="-mt-6 -ml-8 flex items-center gap-8 border-b py-3 pl-8">
                    <div className="flex flex-1 items-center gap-8">{metrics}</div>
                </div>
                {outputBody}
            </section>
        );
    }

    return (
        <section className="space-y-4">
            <Tabs value={activeTab} onValueChange={value => onTabChange(value as "output" | "artifacts")}>
                <div className="-mt-6 -ml-8 flex items-center gap-8 border-b py-3 pl-8">
                    {/* Match the chat side-panel's Files/Activity tab look: a
                        segmented bordered pair with shared edges. Keeps the
                        visual language consistent across the app's tabbed
                        surfaces. */}
                    <TabsList className="flex bg-transparent p-0">
                        <TabsTrigger value="output" title="Output" className="relative rounded-none rounded-l-md px-3 data-[state=active]:z-10">
                            Output
                        </TabsTrigger>
                        <TabsTrigger value="artifacts" title="Artifacts" className="relative rounded-none rounded-r-md border-l-0 px-3 data-[state=active]:z-10">
                            Artifacts
                        </TabsTrigger>
                    </TabsList>
                    <div className="flex flex-1 items-center gap-8">{metrics}</div>
                </div>
                <TabsContent value="output" className="mt-4">
                    {outputBody}
                </TabsContent>
                <TabsContent value="artifacts" className="mt-4">
                    <ExecutionArtifactsView executionId={execution.id} />
                </TabsContent>
            </Tabs>
        </section>
    );
};
