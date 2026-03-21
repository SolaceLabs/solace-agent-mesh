import { useState, useEffect, useMemo, useRef, useCallback } from "react";
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
    if (percentage >= 90) return "text-(--error-wMain)";
    if (percentage >= 75) return "text-(--warning-wMain)";
    if (percentage >= 50) return "text-(--warning-w70)";
    return "text-(--success-wMain)";
}

const CompressionIcon = ({ className }: { className?: string }) => (
    <svg width="16" height="20" viewBox="0 0 16 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
        <path d="M8 1V6M8 6L5.5 3.5M8 6L10.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M2 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M2 12H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M8 19V14M8 14L5.5 16.5M8 14L10.5 16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

export function ContextUsageIndicator({ sessionId, onCompacted, messageCount = 0 }: ContextUsageIndicatorProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [usage, setUsage] = useState<ContextUsage | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isCompacting, setIsCompacting] = useState(false);
    const [compactError, setCompactError] = useState<string | null>(null);
    const [compactSuccess, setCompactSuccess] = useState<string | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const compactingRef = useRef(false);
    const { selectedAgentName } = useChatContext();

    const fetchUsage = useCallback(async () => {
        if (!sessionId) return;
        setIsLoading(true);
        try {
            const data = await getSessionContextUsage(sessionId, undefined, selectedAgentName || undefined);
            setUsage(data);
        } catch (err) {
            if (process.env.NODE_ENV === "development") {
                console.warn("ContextUsageIndicator: failed to fetch usage", err);
            }
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, selectedAgentName]);

    // Fetch on mount and whenever a new message arrives (messageCount changes).
    // No polling needed — token counts only change when messages are sent/received.
    useEffect(() => {
        fetchUsage();
    }, [fetchUsage, messageCount]);

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
    const formattedCurrent = formatTokenCount(usage?.currentContextTokens ?? 0);
    const formattedLimit = formatTokenCount(usage?.maxInputTokens ?? 0);

    // Show compress button when 15+ messages OR 70%+ token usage
    const shouldShowCompressButton = useMemo(() => messageCount >= 15 || pct >= 70, [messageCount, pct]);

    const handleCompress = async () => {
        if (compactingRef.current) return;
        compactingRef.current = true;
        setIsCompacting(true);
        setCompactError(null);
        setCompactSuccess(null);
        try {
            const result = await compactSession(sessionId);
            setCompactSuccess(`Compacted ${result.eventsCompacted} events. ${result.remainingTokens > 0 ? `${formatTokenCount(result.remainingTokens)} tokens remaining.` : ""}`);
            await fetchUsage();
            onCompacted?.();
        } catch (err) {
            setCompactError(err instanceof Error ? err.message : "Failed to compact session");
        } finally {
            compactingRef.current = false;
            setIsCompacting(false);
        }
    };

    if (!sessionId) return null;
    if (!usage) return null; // Still loading or API failed — hide silently

    return (
        <div ref={containerRef} className="relative inline-block">
            {/* Expanded panel — floats above the toolbar via absolute positioning */}
            {isExpanded && (
                <div className="absolute right-0 bottom-full z-50 mb-1 w-64 rounded-lg border bg-(--background-wMain) shadow-lg">
                    <div className="space-y-3 p-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold">Context Window Usage</span>
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={fetchUsage} disabled={isLoading}>
                                <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
                            </Button>
                        </div>

                        <div className="space-y-1">
                            <Progress value={pct} className="h-2" />
                            <div className="text-muted-foreground flex justify-between text-xs">
                                <span>{formattedCurrent} used</span>
                                <span>{formattedLimit} limit</span>
                            </div>
                        </div>

                        <div className="space-y-2 text-xs">
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

                        {shouldShowCompressButton && (
                            <div className="space-y-2 border-t pt-3">
                                {compactSuccess && <div className="rounded bg-(--success-w10) p-2 text-xs text-(--success-wMain)">{compactSuccess}</div>}
                                {compactError && <div className="rounded bg-(--error-w10) p-2 text-xs text-(--error-wMain)">{compactError}</div>}
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

                        {pct >= 90 && <div className="rounded bg-(--error-w10) p-2 text-xs text-(--error-wMain)">Approaching context limit! Consider compacting the conversation.</div>}
                        {pct >= 75 && pct < 90 && <div className="rounded bg-(--warning-w10) p-2 text-xs text-(--warning-wMain)">Context usage is high. Consider compacting soon.</div>}
                    </div>
                </div>
            )}

            {/* Compact trigger — always visible in the toolbar, never changes size */}
            <div className="rounded-lg border bg-(--background-wMain)">
                <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                        <div className="cursor-pointer p-2" onClick={() => setIsExpanded(prev => !prev)}>
                            <div className="flex items-center gap-2">
                                <div className="w-28 space-y-1">
                                    <Progress value={pct} className="h-1.5" />
                                    <div className={`text-center font-mono text-[10px] ${colorClass}`}>
                                        {formattedCurrent}/{formattedLimit}
                                    </div>
                                </div>
                                {(shouldShowCompressButton || isCompacting) && (
                                    <div
                                        className="text-muted-foreground hover:text-foreground cursor-pointer p-1"
                                        title={isCompacting ? "Compacting..." : "Compact conversation"}
                                        onClick={e => {
                                            e.stopPropagation();
                                            if (!isCompacting) handleCompress();
                                        }}
                                    >
                                        {isCompacting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CompressionIcon className="h-4 w-4" />}
                                    </div>
                                )}
                            </div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                        <p className="font-semibold">Context Window Usage</p>
                        <p className="text-xs">
                            {formattedCurrent} / {formattedLimit} tokens ({pct}%)
                        </p>
                    </TooltipContent>
                </Tooltip>
            </div>
        </div>
    );
}
