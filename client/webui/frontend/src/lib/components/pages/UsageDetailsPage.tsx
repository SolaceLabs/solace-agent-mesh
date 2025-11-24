/**
 * Usage Details Page
 * Comprehensive view of token usage and quota information
 */

import React, { useEffect, useState } from "react";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { UsageOverviewCard } from "../usage/UsageOverviewCard";
import { getCurrentUsage, getUsageHistory, getTransactions } from "../../api/token-usage-api";
import type { CurrentUsage, MonthlyUsageHistory, TransactionsResponse } from "../../types/token-usage";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from "recharts";

interface UsageDetailsPageProps {
    onBack?: () => void;
}

export const UsageDetailsPage: React.FC<UsageDetailsPageProps> = ({ onBack }) => {
    const [currentUsage, setCurrentUsage] = useState<CurrentUsage | null>(null);
    const [history, setHistory] = useState<MonthlyUsageHistory[]>([]);
    const [transactions, setTransactions] = useState<TransactionsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showAllHistory, setShowAllHistory] = useState(false);
    const [showAllTransactions, setShowAllTransactions] = useState(false);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            setError(null);
            const [usage, hist, trans] = await Promise.all([getCurrentUsage(), getUsageHistory(6), getTransactions({ limit: 10 })]);
            console.log("Usage data loaded:", { usage, hist, trans });
            setCurrentUsage(usage);
            setHistory(hist);
            setTransactions(trans);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load usage data");
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="text-gray-500 dark:text-gray-400">Loading usage data...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6">
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
                    <p className="text-red-800 dark:text-red-200">{error}</p>
                    <Button onClick={loadData} className="mt-4" variant="outline">
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Retry
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto bg-gray-50 dark:bg-gray-900">
            <div className="mx-auto max-w-7xl space-y-8 p-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        {onBack && (
                            <Button onClick={onBack} variant="ghost" size="sm" className="hover:bg-gray-200 dark:hover:bg-gray-800">
                                <ArrowLeft className="h-4 w-4" />
                            </Button>
                        )}
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Token Usage</h1>
                            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Monitor your usage and costs</p>
                        </div>
                    </div>
                    <Button onClick={loadData} variant="outline" size="sm" className="gap-2">
                        <RefreshCw className="h-4 w-4" />
                        Refresh
                    </Button>
                </div>

                {/* Current Usage Overview */}
                <UsageOverviewCard />

                {/* Two Column Layout for History and Models */}
                <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
                    {/* Usage History */}
                    {history.length > 0 && (
                        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                            <div className="mb-6 flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Usage History</h2>
                                {history.length > 3 && (
                                    <button onClick={() => setShowAllHistory(!showAllHistory)} className="text-sm text-blue-600 hover:underline dark:text-blue-400">
                                        {showAllHistory ? "Show All (${history.length})" : "Show Less"}
                                    </button>
                                )}
                            </div>
                            <div className="h-80">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart
                                        data={(showAllHistory ? history : history.slice(0, 3)).map(month => ({
                                            month: month.month,
                                            tokens: (month.totalUsage || 0) / 1_000_000,
                                            cost: parseFloat(month.costUsd?.replace("$", "") || "0"),
                                        }))}
                                        margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                                        <XAxis dataKey="month" angle={-45} textAnchor="end" height={80} className="text-xs text-gray-600 dark:text-gray-400" tick={{ fill: "currentColor" }} />
                                        <YAxis
                                            yAxisId="left"
                                            orientation="left"
                                            className="text-xs text-gray-600 dark:text-gray-400"
                                            tick={{ fill: "currentColor" }}
                                            label={{ value: "Tokens (M)", angle: -90, position: "insideLeft", className: "text-gray-600 dark:text-gray-400" }}
                                        />
                                        <YAxis
                                            yAxisId="right"
                                            orientation="right"
                                            className="text-xs text-gray-600 dark:text-gray-400"
                                            tick={{ fill: "currentColor" }}
                                            label={{ value: "Cost ($)", angle: 90, position: "insideRight", className: "text-gray-600 dark:text-gray-400" }}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: "rgb(31 41 55)",
                                                border: "1px solid rgb(75 85 99)",
                                                borderRadius: "0.5rem",
                                                color: "rgb(243 244 246)",
                                            }}
                                            formatter={(value: number, name: string) => {
                                                if (name === "tokens") {
                                                    return [`${value.toFixed(2)}M tokens`, "Tokens"];
                                                }
                                                return [`$${value.toFixed(4)}`, "Cost"];
                                            }}
                                            labelStyle={{ color: "rgb(243 244 246)", fontWeight: "bold" }}
                                        />
                                        <Legend wrapperStyle={{ paddingTop: "20px" }} iconType="rect" formatter={(value: string) => (value === "tokens" ? "Tokens (M)" : "Cost ($)")} />
                                        <Bar yAxisId="left" dataKey="tokens" fill="#3b82f6" radius={[8, 8, 0, 0]} name="tokens" />
                                        <Bar yAxisId="right" dataKey="cost" fill="#10b981" radius={[8, 8, 0, 0]} name="cost" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {/* Model Breakdown */}
                    {currentUsage && currentUsage.usageByModel && Object.keys(currentUsage.usageByModel).length > 0 && (
                        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                            <h2 className="mb-6 text-lg font-semibold text-gray-900 dark:text-white">Usage by Model</h2>
                            <div className="h-80">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={Object.entries(currentUsage.usageByModel || {})
                                                .sort(([, a], [, b]) => (b as number) - (a as number))
                                                .map(([model, usage]) => {
                                                    const usageNum = (usage as number) || 0;
                                                    const totalUsage = currentUsage?.totalUsage || 1;
                                                    const percentage = (usageNum / totalUsage) * 100;
                                                    return {
                                                        name: model,
                                                        value: usageNum,
                                                        percentage: percentage,
                                                        displayValue: `${(usageNum / 1000).toFixed(0)}K`,
                                                    };
                                                })}
                                            cx="50%"
                                            cy="50%"
                                            labelLine={true}
                                            label={({ name, percentage }) => `${name}: ${percentage.toFixed(1)}%`}
                                            outerRadius={100}
                                            innerRadius={50}
                                            fill="#8884d8"
                                            dataKey="value"
                                            animationBegin={0}
                                            animationDuration={800}
                                        >
                                            {Object.entries(currentUsage.usageByModel || {})
                                                .sort(([, a], [, b]) => (b as number) - (a as number))
                                                .map((_, index) => {
                                                    const colors = [
                                                        "#3b82f6", // blue-500
                                                        "#10b981", // green-500
                                                        "#f59e0b", // amber-500
                                                        "#ef4444", // red-500
                                                        "#8b5cf6", // violet-500
                                                        "#ec4899", // pink-500
                                                        "#06b6d4", // cyan-500
                                                        "#84cc16", // lime-500
                                                    ];
                                                    return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                                                })}
                                        </Pie>
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: "rgb(31 41 55)",
                                                border: "1px solid rgb(75 85 99)",
                                                borderRadius: "0.5rem",
                                                color: "rgb(243 244 246)",
                                            }}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            formatter={(value: number, name: string, props: any) => {
                                                const percentage = props.payload.percentage;
                                                return [`${(value / 1000).toFixed(0)}K tokens (${percentage.toFixed(1)}%)`, name];
                                            }}
                                            labelStyle={{ color: "rgb(243 244 246)", fontWeight: "bold" }}
                                        />
                                        <Legend
                                            verticalAlign="bottom"
                                            height={36}
                                            iconType="circle"
                                            wrapperStyle={{ paddingTop: "20px" }}
                                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                            formatter={(value: string, entry: any) => {
                                                const percentage = entry.payload.percentage;
                                                return `${value} (${percentage.toFixed(1)}%)`;
                                            }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}
                </div>

                {/* Recent Transactions */}
                {transactions && transactions.transactions.length > 0 && (
                    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
                        <div className="flex items-center justify-between border-b border-gray-200 p-6 dark:border-gray-700">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Transactions</h2>
                            {transactions.transactions.length > 5 && (
                                <button onClick={() => setShowAllTransactions(!showAllTransactions)} className="text-sm text-blue-600 hover:underline dark:text-blue-400">
                                    {showAllTransactions ? "Show Less" : `Show All (${transactions.total})`}
                                </button>
                            )}
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-gray-50 dark:bg-gray-900/50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">Date</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">Model</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">Type</th>
                                        <th className="px-6 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">Tokens</th>
                                        <th className="px-6 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">Cost</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                    {(showAllTransactions ? transactions.transactions : transactions.transactions.slice(0, 5)).map(tx => (
                                        <tr key={tx.id} className="transition-colors hover:bg-gray-50 dark:hover:bg-gray-900/30">
                                            <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300">{tx.createdAt ? new Date(tx.createdAt).toLocaleDateString() : "N/A"}</td>
                                            <td className="px-6 py-4 text-sm font-medium text-gray-700 dark:text-gray-300">{tx.model || "N/A"}</td>
                                            <td className="px-6 py-4">
                                                <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800 capitalize dark:bg-gray-700 dark:text-gray-200">
                                                    {tx.transactionType || "unknown"}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-right font-mono text-sm text-gray-700 dark:text-gray-300">{(tx.rawTokens || 0).toLocaleString()}</td>
                                            <td className="px-6 py-4 text-right text-sm font-semibold text-gray-900 dark:text-white">{tx.costUsd || "$0.0000"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default UsageDetailsPage;
