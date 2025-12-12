/**
 * Usage Overview Card Component
 * Displays current month usage summary with quota status
 */

import React, { useEffect, useState } from "react";
import { getCurrentUsage, getQuotaStatus, formatNumber } from "../../api/token-usage-api";
import type { CurrentUsage, QuotaStatus } from "../../types/token-usage";

export const UsageOverviewCard: React.FC = () => {
    const [usage, setUsage] = useState<CurrentUsage | null>(null);
    const [quota, setQuota] = useState<QuotaStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            setError(null);
            const [usageData, quotaData] = await Promise.all([getCurrentUsage(), getQuotaStatus()]);
            setUsage(usageData);
            setQuota(quotaData);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load usage data");
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                <div className="animate-pulse">
                    <div className="mb-4 h-4 w-1/4 rounded bg-gray-200 dark:bg-gray-700"></div>
                    <div className="mb-2 h-8 w-1/2 rounded bg-gray-200 dark:bg-gray-700"></div>
                    <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700"></div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                <div className="text-red-600 dark:text-red-400">
                    <p className="font-semibold">Error loading usage data</p>
                    <p className="text-sm">{error}</p>
                </div>
            </div>
        );
    }

    if (!usage || !quota) {
        return null;
    }

    const usagePercentage = quota.usagePercentage || 0;
    const getStatusColor = () => {
        if (usagePercentage >= 90) return "bg-red-500";
        if (usagePercentage >= 75) return "bg-orange-500";
        if (usagePercentage >= 50) return "bg-yellow-500";
        return "bg-green-500";
    };

    const getTextColor = () => {
        if (usagePercentage >= 90) return "text-red-600 dark:text-red-400";
        if (usagePercentage >= 75) return "text-orange-600 dark:text-orange-400";
        if (usagePercentage >= 50) return "text-yellow-600 dark:text-yellow-400";
        return "text-green-600 dark:text-green-400";
    };

    return (
        <div className="rounded-xl border border-gray-200 bg-white p-8 dark:border-gray-700 dark:bg-gray-800">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h3 className="mb-1 text-sm font-medium text-gray-500 dark:text-gray-400">Current Usage</h3>
                    <p className="text-3xl font-bold text-gray-900 dark:text-white">{usage.costUsd}</p>
                </div>
                <div className="text-right">
                    <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">{usage.month}</p>
                    <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${getTextColor()} bg-opacity-10`}>{usagePercentage.toFixed(1)}% used</span>
                </div>
            </div>

            {/* Progress Bar */}
            <div className="mb-6">
                <div className="h-3 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                    <div className={`h-3 rounded-full ${getStatusColor()} transition-all duration-500 ease-out`} style={{ width: `${Math.min(usagePercentage, 100)}%` }}></div>
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-medium">${((quota.currentUsage || 0) / 1_000_000).toFixed(2)} used</span>
                    <span className="font-medium">${((quota.remaining || 0) / 1_000_000).toFixed(2)} remaining</span>
                </div>
            </div>

            {/* Usage Breakdown - Tokens and Cost */}
            <div className="mb-6 grid grid-cols-3 gap-6">
                <div className="text-center">
                    <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">Prompt</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{formatNumber(usage.promptTokens || 0)}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">${((usage.promptUsage || 0) / 1_000_000).toFixed(4)}</p>
                </div>
                <div className="border-x border-gray-200 text-center dark:border-gray-700">
                    <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">Completion</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{formatNumber(usage.completionTokens || 0)}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">${((usage.completionUsage || 0) / 1_000_000).toFixed(4)}</p>
                </div>
                <div className="text-center">
                    <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">Cached</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{formatNumber(usage.cachedTokens || 0)}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">${((usage.cachedUsage || 0) / 1_000_000).toFixed(4)}</p>
                </div>
            </div>

            {/* Account Info */}
            <div className="border-t border-gray-200 pt-6 dark:border-gray-700">
                <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Account Type</span>
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800 capitalize dark:bg-blue-900/30 dark:text-blue-300">{quota.accountType}</span>
                </div>
            </div>

            {/* Warning Message */}
            {usagePercentage >= 90 && (
                <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
                    <p className="flex items-start text-sm text-red-800 dark:text-red-200">
                        <span className="mr-2">⚠️</span>
                        <span>You're approaching your monthly quota limit. Consider upgrading your plan or reducing usage.</span>
                    </p>
                </div>
            )}
        </div>
    );
};

export default UsageOverviewCard;
