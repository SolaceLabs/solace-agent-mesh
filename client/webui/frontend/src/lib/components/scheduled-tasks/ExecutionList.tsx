import React from "react";
import { Loader2 } from "lucide-react";
import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { formatEpochTimestamp, formatDuration } from "@/lib/utils/format";
import { IN_PROGRESS_STATUSES, STATUS_LABELS } from "./StatusBadge";

interface ExecutionListProps {
    executions: TaskExecution[];
    selectedExecution: TaskExecution | null;
    onSelect: (execution: TaskExecution) => void;
    isLoading: boolean;
}

export const ExecutionList: React.FC<ExecutionListProps> = ({ executions, selectedExecution, onSelect, isLoading }) => {
    return (
        <div className="w-[300px] overflow-y-auto border-r">
            <div className="p-4">
                <h3 className="mb-3 text-sm font-semibold text-(--secondary-text-wMain)">Executions ({executions.length})</h3>
                {isLoading ? (
                    <div className="flex items-center justify-center p-8">
                        <div className="border-primary size-6 animate-spin rounded-full border-2 border-t-transparent" />
                    </div>
                ) : executions.length === 0 ? (
                    <p className="p-4 text-center text-sm text-(--secondary-text-wMain)">No executions yet</p>
                ) : (
                    <div className="space-y-2">
                        {executions.map(execution => {
                            const isSelected = selectedExecution?.id === execution.id;

                            return (
                                <button
                                    key={execution.id}
                                    onClick={() => onSelect(execution)}
                                    className={`w-full rounded p-3 text-left transition-colors ${isSelected ? "border border-(--primary-w20) bg-(--primary-w10)" : "hover:bg-(--secondary-w20)"}`}
                                >
                                    <div className="mb-2 flex items-center justify-between gap-2">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-medium">{STATUS_LABELS[execution.status] ?? execution.status}</span>
                                            {execution.triggerType === "manual" && (
                                                <span className="rounded-full bg-(--info-w20) px-2 py-0.5 text-xs text-(--info-wMain)" title={execution.triggeredBy ? `Triggered manually by ${execution.triggeredBy}` : "Triggered manually"}>
                                                    Manual
                                                </span>
                                            )}
                                        </div>
                                        <span className="flex items-center text-xs text-(--secondary-text-wMain)">
                                            {IN_PROGRESS_STATUSES.has(execution.status) ? <Loader2 className="size-3 animate-spin text-(--brand-wMain)" aria-label="in progress" /> : execution.durationMs ? formatDuration(execution.durationMs) : "-"}
                                        </span>
                                    </div>
                                    <span className="block text-xs text-(--secondary-text-wMain)">{execution.startedAt ? formatEpochTimestamp(execution.startedAt) : "Pending"}</span>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
