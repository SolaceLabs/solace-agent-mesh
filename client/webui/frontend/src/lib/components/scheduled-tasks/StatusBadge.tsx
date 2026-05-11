import React from "react";

export const IN_PROGRESS_STATUSES: ReadonlySet<string> = new Set(["pending", "running"]);

export const STATUS_LABELS: Record<string, string> = {
    completed: "Completed",
    failed: "Failed",
    pending: "Pending",
    running: "Running",
    timeout: "Timeout",
};

// Pill-style badge used for both execution statuses (completed/failed/pending/
// running/timeout) and task statuses (active/paused/error). Reused everywhere
// a status pill is rendered so all three render identical pills.
export const getStatusBadge = (status: string) => {
    const statusConfig = {
        // Execution statuses
        completed: { bg: "bg-(--success-w20)", text: "text-(--success-wMain)", label: "Completed" },
        failed: { bg: "bg-(--error-w20)", text: "text-(--error-wMain)", label: "Failed" },
        pending: { bg: "bg-(--info-w20)", text: "text-(--info-wMain)", label: "Pending" },
        running: { bg: "bg-(--info-w20)", text: "text-(--info-wMain)", label: "Running" },
        timeout: { bg: "bg-(--warning-w20)", text: "text-(--warning-wMain)", label: "Timeout" },
        cancelled: { bg: "bg-(--secondary-w20)", text: "text-(--secondary-text-wMain)", label: "Cancelled" },
        skipped: { bg: "bg-(--secondary-w20)", text: "text-(--secondary-text-wMain)", label: "Skipped" },
        // Task lifecycle statuses
        active: { bg: "bg-(--success-w20)", text: "text-(--success-wMain)", label: "Active" },
        paused: { bg: "bg-(--secondary-w20)", text: "text-(--secondary-text-wMain)", label: "Paused" },
        error: { bg: "bg-(--error-w20)", text: "text-(--error-wMain)", label: "Error" },
    };
    // Truly unknown statuses get a neutral pill with the raw value so they
    // don't masquerade as failures (and surface the unexpected value for
    // debugging) instead of silently mislabeling them.
    const config = statusConfig[status as keyof typeof statusConfig] ?? { bg: "bg-(--secondary-w20)", text: "text-(--secondary-text-wMain)", label: status };
    return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.bg} ${config.text}`}>{config.label}</span>;
};

interface StatusBadgeProps {
    status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => getStatusBadge(status);
