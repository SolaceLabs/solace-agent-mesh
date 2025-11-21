import React, { useState, useEffect, useMemo, useRef } from "react";
import { RefreshCw, Sparkles, Loader2 } from "lucide-react";

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

const STORAGE_KEY = "context-indicator-position";
const DEFAULT_POSITION = { x: 16, y: 80 }; // right-4 (16px), bottom-20 (80px)

export const ContextUsageIndicator: React.FC<ContextUsageIndicatorProps> = ({ sessionId, onRefresh, messageCount = 0 }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [sessionUsage, setSessionUsage] = useState<SessionTokenUsage | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [position, setPosition] = useState(DEFAULT_POSITION);
    const [isDragging, setIsDragging] = useState(false);
    const [isCompressing, setIsCompressing] = useState(false);
    const [compressionError, setCompressionError] = useState<string | null>(null);
    const [compressionSuccess, setCompressionSuccess] = useState<string | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const dragStartPos = useRef({ x: 0, y: 0 });
    const dragOffset = useRef({ x: 0, y: 0 });
    const { handleSwitchSession } = useChatContext();

    // Load position from localStorage
    useEffect(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                setPosition(parsed);
            } catch {
                // Ignore invalid JSON, use default position
            }
        }
    }, []);

    // Save position to localStorage
    const savePosition = (newPosition: { x: number; y: number }) => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newPosition));
        setPosition(newPosition);
    };

    // Drag handlers
    const handleMouseDown = (e: React.MouseEvent) => {
        if (isExpanded) return; // Don't drag when expanded

        setIsDragging(true);
        dragStartPos.current = { x: e.clientX, y: e.clientY };
        dragOffset.current = { x: position.x, y: position.y };
        e.preventDefault();
    };

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging) return;

            const deltaX = dragStartPos.current.x - e.clientX;
            const deltaY = dragStartPos.current.y - e.clientY;

            const newX = dragOffset.current.x + deltaX;
            const newY = dragOffset.current.y + deltaY;

            // Constrain to viewport
            const maxX = window.innerWidth - 150;
            const maxY = window.innerHeight - 100;

            setPosition({
                x: Math.max(16, Math.min(newX, maxX)),
                y: Math.max(16, Math.min(newY, maxY)),
            });
        };

        const handleMouseUp = () => {
            if (isDragging) {
                setIsDragging(false);
                savePosition(position);
            }
        };

        if (isDragging) {
            document.addEventListener("mousemove", handleMouseMove);
            document.addEventListener("mouseup", handleMouseUp);
            return () => {
                document.removeEventListener("mousemove", handleMouseMove);
                document.removeEventListener("mouseup", handleMouseUp);
            };
        }
    }, [isDragging, position]);

    // Fetch session usage
    const fetchSessionUsage = async () => {
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
    };

    // Initial fetch and refresh on sessionId change
    useEffect(() => {
        fetchSessionUsage();
    }, [sessionId]);

    // Auto-refresh every 3 seconds to catch new token usage
    useEffect(() => {
        if (!sessionId) return;

        const interval = setInterval(() => {
            fetchSessionUsage();
        }, 3000);

        return () => clearInterval(interval);
    }, [sessionId]);

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
        // Extract model from session usage data (first model in breakdown)
        const models = sessionUsage?.modelBreakdown ? Object.keys(sessionUsage.modelBreakdown) : [];
        const primaryModel = models.length > 0 ? models[0] : "gpt-4";

        const contextLimit = getModelContextLimit(primaryModel);
        const usedTokens = sessionUsage?.totalTokens || 0;
        const percentage = calculateContextPercentage(usedTokens, contextLimit);
        const cost = sessionUsage?.costUsd || "$0.0000";
        const promptTokens = sessionUsage?.promptTokens || 0;
        const completionTokens = sessionUsage?.completionTokens || 0;
        const cachedTokens = sessionUsage?.cachedTokens || 0;

        return {
            usedTokens,
            contextLimit,
            percentage,
            cost,
            promptTokens,
            completionTokens,
            cachedTokens,
            formattedUsed: formatTokenCount(usedTokens),
            formattedLimit: formatTokenCount(contextLimit),
        };
    }, [sessionUsage]);

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
        <div
            ref={containerRef}
            className="fixed z-50"
            style={{
                right: `${position.x}px`,
                bottom: `${position.y}px`,
                cursor: isDragging ? "grabbing" : isExpanded ? "default" : "grab",
            }}
        >
            <div className={`rounded-lg border shadow-lg ${bgColorClass} backdrop-blur-sm transition-all duration-200 ${isExpanded ? "w-64" : "w-auto"}`}>
                {/* Compact View - Mini Progress Bar */}
                {!isExpanded && (
                    <Tooltip delayDuration={300}>
                        <TooltipTrigger asChild>
                            <div className="p-2" onClick={handleToggle} onMouseDown={handleMouseDown}>
                                <div className="w-28 space-y-1">
                                    <Progress value={contextMetrics.percentage} className="h-1.5" />
                                    <div className={`text-center font-mono text-[10px] ${colorClass}`}>
                                        {contextMetrics.formattedUsed}/{contextMetrics.formattedLimit}
                                    </div>
                                </div>
                            </div>
                        </TooltipTrigger>
                        <TooltipContent side="left">
                            <p className="font-semibold">Context Window</p>
                            <p className="text-xs">
                                {contextMetrics.formattedUsed} / {contextMetrics.formattedLimit} tokens ({contextMetrics.percentage}%)
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
                            <span className="text-sm font-semibold">Context Window</span>
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
                                        <span>{contextMetrics.formattedUsed} used</span>
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
                                    <div className="space-y-1 border-t pt-2">
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Prompt:</span>
                                            <span className="font-mono">{formatTokenCount(contextMetrics.promptTokens)}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Completion:</span>
                                            <span className="font-mono">{formatTokenCount(contextMetrics.completionTokens)}</span>
                                        </div>
                                        {contextMetrics.cachedTokens > 0 && (
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">Cached:</span>
                                                <span className="font-mono">{formatTokenCount(contextMetrics.cachedTokens)}</span>
                                            </div>
                                        )}
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
