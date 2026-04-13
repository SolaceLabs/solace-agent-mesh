import React from "react";
import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { formatEpochTimestamp, formatDuration } from "@/lib/utils/format";

interface ExecutionListProps {
    executions: TaskExecution[];
    selectedExecution: TaskExecution | null;
    onSelect: (execution: TaskExecution) => void;
    isLoading: boolean;
}

const getStatusBadge = (status: string) => {
    const statusConfig = {
        completed: { bg: "bg-(--color-success-w20)", text: "text-(--color-success-wMain)", label: "Completed" },
        failed: { bg: "bg-(--color-error-w20)", text: "text-(--color-error-wMain)", label: "Failed" },
        running: { bg: "bg-(--color-info-w20)", text: "text-(--color-info-wMain)", label: "Running" },
        timeout: { bg: "bg-(--color-warning-w20)", text: "text-(--color-warning-wMain)", label: "Timeout" },
    };
    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.failed;
    return <span className={`rounded-full px-2 py-0.5 text-xs ${config.bg} ${config.text}`}>{config.label}</span>;
};

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
                                    <div className="mb-2 flex items-center justify-between">
                                        {getStatusBadge(execution.status)}
                                        <span className="text-xs text-(--secondary-text-wMain)">{execution.durationMs ? formatDuration(execution.durationMs) : "-"}</span>
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

export { getStatusBadge };
