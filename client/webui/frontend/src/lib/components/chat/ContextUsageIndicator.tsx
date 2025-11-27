import React, { useState, useEffect, useMemo, useRef } from "react";
import { RefreshCw, Sparkles, Loader2, ArrowUp, ArrowDown } from "lucide-react";

import { Button } from "@/lib/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";
import { Progress } from "@/lib/components/ui/progress";
import { MessageBanner } from "@/lib/components/common";
import { getSessionUsage } from "@/lib/api/token-usage-api";
import { compressAndBranchSession } from "@/lib/api/sessions-api";
import type { SessionTokenUsage } from "@/lib/types/token-usage";
import { getModelContextLimit, formatTokenCount, calculateContextPercentage, getUsageColor, getUsageBgColor } from "@/lib/utils/modelContextLimits";
import { useChatContext } from "@/lib/hooks";

interface ContextUsageIndicatorProps {
    sessionId: string;
    onRefresh?: () => void;
    messageCount?: number;
}

const CompressionIcon = ({ className }: { className?: string }) => (
    <svg width="16" height="20" viewBox="0 0 16 20" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
        <path d="M8 1V6M8 6L5.5 3.5M8 6L10.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M2 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M2 12H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 2" />
        <path d="M8 19V14M8 14L5.5 16.5M8 14L10.5 16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

export const ContextUsageIndicator: React.FC<ContextUsageIndicatorProps> = ({ sessionId, onRefresh, messageCount = 0 }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [sessionUsage, setSessionUsage] = useState<SessionTokenUsage | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isCompressing, setIsCompressing] = useState(false);
    const [compressionError, setCompressionError] = useState<string | null>(null);
    const [compressionSuccess, setCompressionSuccess] = useState<string | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const { handleSwitchSession, selectedAgentName, agents } = useChatContext();

    // Fetch session usage
    const fetchSessionUsage = React.useCallback(async () => {
        if (!sessionId) return;

        setIsLoading(true);
        setError(null);
        try {
            const data = await getSessionUsage(sessionId);
            setSessionUsage(data);
        } catch {
            // Handle fetch errors
            setError("Failed to load");
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    // Initial fetch and refresh on sessionId change
    useEffect(() => {
        fetchSessionUsage();
    }, [sessionId, fetchSessionUsage]);

    // Auto-refresh every 3 seconds to catch new token usage
    useEffect(() => {
        if (!sessionId) return;

        const interval = setInterval(() => {
            fetchSessionUsage();
        }, 3000);

        return () => clearInterval(interval);
    }, [sessionId, fetchSessionUsage]);

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

    // Calculate context usage metrics
    const contextMetrics = useMemo(() => {
        // Get the currently selected agent
        const selectedAgent = agents.find(agent => agent.name === selectedAgentName);

        // Try to extract model from agent's capabilities/extensions
        let agentModel: string | null = null;
        if (selectedAgent?.capabilities?.extensions) {
            // Look for LLM model extension (this is a placeholder - actual extension URI may vary)
            const llmExtension = selectedAgent.capabilities.extensions.find((ext: { uri?: string; params?: { model?: string } }) => ext.uri?.includes("llm") || ext.uri?.includes("model"));
            if (llmExtension?.params?.model) {
                agentModel = llmExtension.params.model as string;
            }
        }

        // Extract model from session usage data as fallback
        const models = sessionUsage?.modelBreakdown ? Object.keys(sessionUsage.modelBreakdown) : [];

        // Filter out compression models and prioritize known LLM models
        const llmModels = models.filter(m => !m.toLowerCase().includes("compression") && !m.toLowerCase().includes("summary"));

        // Priority: 1) Agent's configured model, 2) Most recent LLM model from usage, 3) Default
        const primaryModel = agentModel || (llmModels.length > 0 ? llmModels[0] : models.length > 0 ? models[0] : "claude-sonnet-4-5");

        console.log("[ContextUsageIndicator] Model selection:", {
            selectedAgentName,
            agentModel,
            allModels: models,
            llmModels,
            selectedModel: primaryModel,
            modelBreakdown: sessionUsage?.modelBreakdown,
        });

        const contextLimit = getModelContextLimit(primaryModel);
        const currentContextTokens = sessionUsage?.currentContextTokens || 0;
        const percentage = calculateContextPercentage(currentContextTokens, contextLimit);
        const cost = sessionUsage?.costUsd || "$0.0000";
        // Accumulated totals for detailed breakdown display
        const totalTokens = sessionUsage?.totalTokens || 0;
        const promptTokens = sessionUsage?.promptTokens || 0;
        const completionTokens = sessionUsage?.completionTokens || 0;
        const cachedTokens = sessionUsage?.cachedTokens || 0;

        return {
            // Current context window usage (for progress bar and percentage)
            currentContextTokens,
            contextLimit,
            percentage,
            cost,
            // Accumulated totals (for detailed breakdown)
            totalTokens,
            promptTokens,
            completionTokens,
            cachedTokens,
            formattedCurrentContext: formatTokenCount(currentContextTokens),
            formattedLimit: formatTokenCount(contextLimit),
        };
    }, [sessionUsage, selectedAgentName, agents]);

    const colorClass = getUsageColor(contextMetrics.percentage);
    const bgColorClass = getUsageBgColor(contextMetrics.percentage);

    // Determine if compression button should be shown
    // Show when: 15+ messages OR 70%+ token usage
    const shouldShowCompressionButton = useMemo(() => {
        const MESSAGE_THRESHOLD = 15;
        const TOKEN_PERCENTAGE_THRESHOLD = 70;

        return messageCount >= MESSAGE_THRESHOLD || contextMetrics.percentage >= TOKEN_PERCENTAGE_THRESHOLD;
    }, [messageCount, contextMetrics.percentage]);

    const handleRefresh = () => {
        fetchSessionUsage();
        onRefresh?.();
    };

    const handleToggle = () => {
        setIsExpanded(!isExpanded);
    };

    const handleCompress = async () => {
        setIsCompressing(true);
        setCompressionError(null);
        setCompressionSuccess(null);

        try {
            const result = await compressAndBranchSession(sessionId, {});

            setCompressionSuccess(`Compressed ${result.compressedMessageCount} messages. Switching to new session...`);

            // Switch to the new session after a brief delay
            setTimeout(async () => {
                await handleSwitchSession(result.newSessionId);

                // Notify SessionList to refresh
                window.dispatchEvent(new CustomEvent("new-chat-session"));
            }, 1500);
        } catch (error) {
            console.error("Failed to compress session:", error);
            setCompressionError(error instanceof Error ? error.message : "Failed to compress session");
        } finally {
            setIsCompressing(false);
        }
    };

    if (!sessionId) {
        return null;
    }

    return (
        <div ref={containerRef} className="inline-block">
            <div className={`rounded-lg border shadow-lg ${bgColorClass} backdrop-blur-sm transition-all duration-200 ${isExpanded ? "w-64" : "w-auto"}`}>
                {/* Compact View - Mini Progress Bar */}
                {!isExpanded && (
                    <Tooltip delayDuration={300}>
                        <TooltipTrigger asChild>
                            <div className="cursor-pointer p-2" onClick={handleToggle}>
                                <div className="flex items-center gap-2">
                                    <div className="w-28 space-y-1">
                                        <Progress value={contextMetrics.percentage} className="h-1.5" />
                                        <div className={`text-center font-mono text-[10px] ${colorClass}`}>
                                            {contextMetrics.formattedCurrentContext}/{contextMetrics.formattedLimit}
                                        </div>
                                    </div>
                                    {(shouldShowCompressionButton || isCompressing) && (
                                        <Tooltip delayDuration={300}>
                                            <TooltipTrigger asChild>
                                                <div
                                                    className="text-muted-foreground hover:text-foreground animate-pulse cursor-pointer p-1"
                                                    onClick={e => {
                                                        e.stopPropagation();
                                                        if (!isCompressing) {
                                                            handleCompress();
                                                        }
                                                    }}
                                                >
                                                    {isCompressing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CompressionIcon className="h-4 w-4" />}
                                                </div>
                                            </TooltipTrigger>
                                            <TooltipContent side="top">
                                                <p>{isCompressing ? "Compressing..." : "Compress & Continue"}</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    )}
                                </div>
                            </div>
                        </TooltipTrigger>
                        <TooltipContent side="left">
                            <p className="font-semibold">Context Window Usage</p>
                            <p className="text-xs">
                                {contextMetrics.formattedCurrentContext} / {contextMetrics.formattedLimit} tokens ({contextMetrics.percentage}%)
                            </p>
                            <p className="text-xs">Cost: {contextMetrics.cost}</p>
                        </TooltipContent>
                    </Tooltip>
                )}

                {/* Expanded View */}
                {isExpanded && (
                    <div className="space-y-3 p-3">
                        {/* Header with refresh */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold">Context Window Usage</span>
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={handleRefresh} disabled={isLoading}>
                                <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
                            </Button>
                        </div>

                        {error ? (
                            <div className="text-xs text-red-600 dark:text-red-400">{error}</div>
                        ) : (
                            <>
                                {/* Progress Bar */}
                                <div className="space-y-1">
                                    <Progress value={contextMetrics.percentage} className="h-2" />
                                    <div className="text-muted-foreground flex justify-between text-xs">
                                        <span>{contextMetrics.formattedCurrentContext} used</span>
                                        <span>{contextMetrics.formattedLimit} limit</span>
                                    </div>
                                </div>

                                {/* Metrics */}
                                <div className="space-y-2 text-xs">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Estimated Cost:</span>
                                        <span className="font-mono font-semibold">{contextMetrics.cost}</span>
                                    </div>

                                    {/* Token Type Breakdown */}
                                    <div className="flex items-center justify-between border-t pt-2">
                                        <span className="text-muted-foreground">Tokens</span>
                                        <div className="flex items-center gap-3 font-mono text-xs">
                                            <span className="flex items-center gap-1" title="Prompt Tokens">
                                                <ArrowUp className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(contextMetrics.promptTokens)}
                                            </span>
                                            <span className="flex items-center gap-1" title="Completion Tokens">
                                                <ArrowDown className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(contextMetrics.completionTokens)}
                                            </span>
                                            {contextMetrics.cachedTokens > 0 && (
                                                <span className="text-muted-foreground flex items-center gap-1" title="Cached Tokens">
                                                    (Cached: {formatTokenCount(contextMetrics.cachedTokens)})
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Compression Section */}
                                {shouldShowCompressionButton && (
                                    <div className="space-y-2 border-t pt-3">
                                        {compressionSuccess && <MessageBanner variant="success" message={compressionSuccess} dismissible onDismiss={() => setCompressionSuccess(null)} />}
                                        {compressionError && <MessageBanner variant="error" message={compressionError} dismissible onDismiss={() => setCompressionError(null)} />}
                                        <Button variant="outline" size="sm" className="w-full" onClick={handleCompress} disabled={isCompressing}>
                                            {isCompressing ? (
                                                <>
                                                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                                    Compressing...
                                                </>
                                            ) : (
                                                <>
                                                    <Sparkles className="mr-2 h-3 w-3" />
                                                    Compress & Continue
                                                </>
                                            )}
                                        </Button>
                                        <p className="text-muted-foreground mt-1 text-center text-xs">Create a summary and start fresh</p>
                                    </div>
                                )}

                                {/* Warning Messages */}
                                {contextMetrics.percentage >= 90 && <div className="rounded bg-red-50 p-2 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">⚠️ Approaching context limit! Consider compressing the conversation.</div>}
                                {contextMetrics.percentage >= 75 && contextMetrics.percentage < 90 && (
                                    <div className="rounded bg-orange-50 p-2 text-xs text-orange-600 dark:bg-orange-900/20 dark:text-orange-400">⚠️ Context usage is high. Consider compressing soon.</div>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
