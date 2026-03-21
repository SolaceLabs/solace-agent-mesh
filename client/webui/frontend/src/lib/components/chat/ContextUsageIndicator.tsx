import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { RefreshCw, Sparkles, Loader2, ArrowUp, ArrowDown } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger, Progress } from "@/lib/components/ui";
import { getSessionContextUsage, compactSession } from "@/lib/api/sessions";
import type { ContextUsage } from "@/lib/types";
import { useChatContext } from "@/lib/hooks";

interface ContextUsageIndicatorProps {
    sessionId: string;
    onCompacted?: () => void;
    messageCount?: number;
}

function formatTokenCount(tokens: number): string {
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
    if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
    return tokens.toString();
}

function getUsageColor(percentage: number): string {
    if (percentage >= 90) return "text-red-600 dark:text-red-400";
    if (percentage >= 75) return "text-orange-600 dark:text-orange-400";
    if (percentage >= 50) return "text-yellow-600 dark:text-yellow-400";
    return "text-green-600 dark:text-green-400";
}

function getUsageBgColor(percentage: number): string {
    if (percentage >= 90) return "bg-red-100 dark:bg-red-900/20";
    if (percentage >= 75) return "bg-orange-100 dark:bg-orange-900/20";
    if (percentage >= 50) return "bg-yellow-100 dark:bg-yellow-900/20";
    return "bg-gray-100 dark:bg-gray-800/50";
}

const CompressionIcon = ({ className }: { className?: string }) => (
    <svg width="16" height="20" viewBox="0 0 16 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
        <path d="M8 1V6M8 6L5.5 3.5M8 6L10.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M2 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M2 12H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M8 19V14M8 14L5.5 16.5M8 14L10.5 16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

export const ContextUsageIndicator: React.FC<ContextUsageIndicatorProps> = ({ sessionId, onCompacted, messageCount = 0 }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [usage, setUsage] = useState<ContextUsage | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isCompacting, setIsCompacting] = useState(false);
    const [compactError, setCompactError] = useState<string | null>(null);
    const [compactSuccess, setCompactSuccess] = useState<string | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const { selectedAgentName } = useChatContext();

    const fetchUsage = useCallback(async () => {
        if (!sessionId) return;
        setIsLoading(true);
        setError(null);
        try {
            const data = await getSessionContextUsage(sessionId, undefined, selectedAgentName || undefined);
            setUsage(data);
        } catch {
            setError("Failed to load");
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, selectedAgentName]);

    // Initial fetch and refresh on sessionId change
    useEffect(() => {
        fetchUsage();
    }, [fetchUsage]);

    // Auto-refresh every 5 seconds
    useEffect(() => {
        if (!sessionId) return;
        const interval = setInterval(fetchUsage, 5000);
        return () => clearInterval(interval);
    }, [sessionId, fetchUsage]);

    // Click outside to collapse
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsExpanded(false);
            }
        };
        if (isExpanded) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [isExpanded]);

    const pct = usage?.usagePercentage ?? 0;
    const colorClass = getUsageColor(pct);
    const bgColorClass = getUsageBgColor(pct);
    const formattedCurrent = formatTokenCount(usage?.currentContextTokens ?? 0);
    const formattedLimit = formatTokenCount(usage?.maxInputTokens ?? 0);

    // Show compress button when 15+ messages OR 70%+ token usage
    const shouldShowCompressButton = useMemo(() => messageCount >= 15 || pct >= 70, [messageCount, pct]);

    const handleCompress = async () => {
        setIsCompacting(true);
        setCompactError(null);
        setCompactSuccess(null);
        try {
            const result = await compactSession(sessionId);
            setCompactSuccess(`Compacted ${result.eventsCompacted} events. ${result.remainingTokens > 0 ? `${formatTokenCount(result.remainingTokens)} tokens remaining.` : ""}`);
            // Refresh usage data
            await fetchUsage();
            onCompacted?.();
        } catch (err) {
            setCompactError(err instanceof Error ? err.message : "Failed to compact session");
        } finally {
            setIsCompacting(false);
        }
    };

    if (!sessionId || !usage) return null;

    return (
        <div ref={containerRef} className="inline-block">
            <div className={`rounded-lg border shadow-lg ${bgColorClass} backdrop-blur-sm transition-all duration-200 ${isExpanded ? "w-64" : "w-auto"}`}>
                {/* Compact View */}
                {!isExpanded && (
                    <Tooltip delayDuration={300}>
                        <TooltipTrigger asChild>
                            <div className="cursor-pointer p-2" onClick={() => setIsExpanded(true)}>
                                <div className="flex items-center gap-2">
                                    <div className="w-28 space-y-1">
                                        <Progress value={pct} className="h-1.5" />
                                        <div className={`text-center font-mono text-[10px] ${colorClass}`}>
                                            {formattedCurrent}/{formattedLimit}
                                        </div>
                                    </div>
                                    {(shouldShowCompressButton || isCompacting) && (
                                        <Tooltip delayDuration={300}>
                                            <TooltipTrigger asChild>
                                                <div
                                                    className="text-muted-foreground hover:text-foreground animate-pulse cursor-pointer p-1"
                                                    onClick={e => {
                                                        e.stopPropagation();
                                                        if (!isCompacting) handleCompress();
                                                    }}
                                                >
                                                    {isCompacting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CompressionIcon className="h-4 w-4" />}
                                                </div>
                                            </TooltipTrigger>
                                            <TooltipContent side="top">
                                                <p>{isCompacting ? "Compacting..." : "Compact conversation"}</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    )}
                                </div>
                            </div>
                        </TooltipTrigger>
                        <TooltipContent side="left">
                            <p className="font-semibold">Context Window Usage</p>
                            <p className="text-xs">
                                {formattedCurrent} / {formattedLimit} tokens ({pct}%)
                            </p>
                        </TooltipContent>
                    </Tooltip>
                )}

                {/* Expanded View */}
                {isExpanded && (
                    <div className="space-y-3 p-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold">Context Window Usage</span>
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={fetchUsage} disabled={isLoading}>
                                <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
                            </Button>
                        </div>

                        {error ? (
                            <div className="text-xs text-red-600 dark:text-red-400">{error}</div>
                        ) : (
                            <>
                                <div className="space-y-1">
                                    <Progress value={pct} className="h-2" />
                                    <div className="text-muted-foreground flex justify-between text-xs">
                                        <span>{formattedCurrent} used</span>
                                        <span>{formattedLimit} limit</span>
                                    </div>
                                </div>

                                <div className="space-y-2 text-xs">
                                    {/* Token Breakdown: Sent vs Received */}
                                    <div className="flex items-center justify-between border-t pt-2">
                                        <span className="text-muted-foreground">Tokens</span>
                                        <div className="flex items-center gap-3 font-mono text-xs">
                                            <span className="flex items-center gap-1" title="Sent (prompt tokens)">
                                                <ArrowUp className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(usage.promptTokens)}
                                            </span>
                                            <span className="flex items-center gap-1" title="Received (completion tokens)">
                                                <ArrowDown className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(usage.completionTokens)}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Model:</span>
                                        <span className="font-mono font-semibold">{usage.model}</span>
                                    </div>
                                    <div className="flex items-center justify-between border-t pt-2">
                                        <span className="text-muted-foreground">Events</span>
                                        <span className="font-mono">{usage.totalEvents}</span>
                                    </div>
                                    {usage.hasCompaction && (
                                        <div className="text-muted-foreground flex items-center gap-1">
                                            <CompressionIcon className="h-3 w-3" />
                                            <span>Previously compacted</span>
                                        </div>
                                    )}
                                </div>

                                {/* Compression Section */}
                                {shouldShowCompressButton && (
                                    <div className="space-y-2 border-t pt-3">
                                        {compactSuccess && <div className="rounded bg-green-50 p-2 text-xs text-green-700 dark:bg-green-900/20 dark:text-green-300">{compactSuccess}</div>}
                                        {compactError && <div className="rounded bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{compactError}</div>}
                                        <Button variant="outline" size="sm" className="w-full" onClick={handleCompress} disabled={isCompacting}>
                                            {isCompacting ? (
                                                <>
                                                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                                    Compacting...
                                                </>
                                            ) : (
                                                <>
                                                    <Sparkles className="mr-2 h-3 w-3" />
                                                    Compact Conversation
                                                </>
                                            )}
                                        </Button>
                                        <p className="text-muted-foreground mt-1 text-center text-xs">Summarize older messages to free context space</p>
                                    </div>
                                )}

                                {/* Warning Messages */}
                                {pct >= 90 && <div className="rounded bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">Approaching context limit! Consider compacting the conversation.</div>}
                                {pct >= 75 && pct < 90 && <div className="rounded bg-orange-50 p-2 text-xs text-orange-600 dark:bg-orange-900/20 dark:text-orange-400">Context usage is high. Consider compacting soon.</div>}
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
