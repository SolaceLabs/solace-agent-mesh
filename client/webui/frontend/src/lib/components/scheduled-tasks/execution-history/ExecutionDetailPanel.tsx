import React from "react";
import { Loader2 } from "lucide-react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/lib/components/ui";
import { MarkdownWrapper } from "@/lib/components";
import { useExecutionArtifacts } from "@/lib/api/scheduled-tasks";
import { ExecutionArtifactsView, ExecutionInlineArtifacts } from "@/lib/components/scheduled-tasks/ExecutionArtifactsView";
import { formatDuration, formatEpochTimestampShort } from "@/lib/utils/format";
import { getStatusBadge, IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { Metric } from "./helpers";

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

    const outputBody = (
        <div className="space-y-4 text-sm break-words">
            {fullText ? (
                <MarkdownWrapper content={fullText} className="text-sm" />
            ) : execution.errorMessage ? (
                <div className="whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</div>
            ) : (
                <div className="text-(--secondary-text-wMain) italic">No output yet.</div>
            )}
            {hasArtifacts && <ExecutionInlineArtifacts executionId={execution.id} />}
        </div>
    );

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
                    <TabsList>
                        <TabsTrigger value="output">Output</TabsTrigger>
                        <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
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
