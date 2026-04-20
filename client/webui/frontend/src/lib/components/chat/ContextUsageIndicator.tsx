import { useState, useEffect, useMemo, useRef } from "react";
import { Sparkles, Loader2, ArrowUp, ArrowDown, MessageSquare } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Button, Tooltip, TooltipContent, TooltipTrigger, Progress } from "@/lib/components/ui";
import { ConfirmationDialog } from "@/lib/components/common";
import { useSessionContextUsage, useCompactSession, sessionKeys } from "@/lib/api/sessions";
import { useChatContext } from "@/lib/hooks";

// Thresholds that surface the "Summarize Conversation" button and toolbar icon.
// Either condition is enough — early in the session (high message count, low
// tokens) we still want to offer compaction; mid-session with few messages but
// lots of context we also want to offer it.
const COMPACT_BUTTON_MIN_MESSAGES = 20;
const COMPACT_BUTTON_MIN_USAGE_PCT = 20;

interface ContextUsageIndicatorProps {
    sessionId: string;
    onCompacted?: () => void;
    messageCount?: number;
}

function formatModelName(model: string): string {
    // Strip LiteLLM provider prefix (e.g. "openai/vertex-claude-4-5-sonnet" → "vertex-claude-4-5-sonnet")
    const slashIdx = model.lastIndexOf("/");
    return slashIdx >= 0 ? model.slice(slashIdx + 1) : model;
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
    const [compactError, setCompactError] = useState<string | null>(null);
    const [compactSuccess, setCompactSuccess] = useState<string | null>(null);
    const [showCompactConfirm, setShowCompactConfirm] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const { selectedAgentName, isResponding } = useChatContext();
    const queryClient = useQueryClient();

    const { data: usage, refetch: refetchUsage } = useSessionContextUsage(sessionId, selectedAgentName || undefined);
    const compactMutation = useCompactSession(sessionId);
    const isCompacting = compactMutation.isPending;

    // Refetch on mount and whenever a new message arrives (messageCount changes).
    useEffect(() => {
        if (sessionId) refetchUsage();
    }, [sessionId, messageCount, refetchUsage]);

    // When the AI finishes responding (isResponding: true → false), poll until
    // the backend reflects the new task's token usage. The TaskLoggerService
    // writes total_input_tokens asynchronously after the task completes, so the
    // first fetch may still return stale data. We retry up to 4 times with
    // increasing delays (500ms, 1s, 2s, 4s) and stop as soon as totalTasks
    // increases. Capture the baseline task count only on the false→true
    // transition so mid-stream refetches don't inflate it.
    const prevRespondingRef = useRef(false);
    const baselineTaskCountRef = useRef(0);
    useEffect(() => {
        if (isResponding && !prevRespondingRef.current) {
            baselineTaskCountRef.current = usage?.totalTasks ?? 0;
        }
        if (prevRespondingRef.current && !isResponding) {
            const expectedTasks = baselineTaskCountRef.current + 1;
            let attempt = 0;
            let cancelled = false;

            const poll = async () => {
                while (!cancelled && attempt < 4) {
                    const delay = 500 * Math.pow(2, attempt); // 500, 1000, 2000, 4000
                    attempt++;
                    await new Promise(r => setTimeout(r, delay));
                    if (cancelled) return;
                    const result = await refetchUsage();
                    if (result.data && result.data.totalTasks >= expectedTasks) return;
                }
            };
            poll();
            prevRespondingRef.current = isResponding;
            return () => {
                cancelled = true;
            };
        }
        prevRespondingRef.current = isResponding;
        // Intentionally exclude usage?.totalTasks: it's mutated by the poll's
        // own refetchUsage() calls. Including it would re-run the effect on
        // every intermediate refetch, trip the cleanup (cancelled = true),
        // and abort the poll before the new task's token data arrives. The
        // loop reads the latest count via result.data.totalTasks directly.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isResponding, refetchUsage]);

    // Click outside to collapse. Only collapse — do NOT clear banners here:
    // ConfirmationDialog is portaled (outside containerRef), so clicking its
    // "Compact" button looks like an outside click and would wipe the banner
    // before handleCompress finishes. Banners are instead cleared on the
    // explicit dismiss buttons and at the start of each compaction attempt.
    // We also ignore mousedowns that originate inside any portal-rendered
    // dialog content to avoid collapsing the panel when the user interacts
    // with the confirmation dialog.
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as Node | null;
            if (!target) return;
            if (containerRef.current && containerRef.current.contains(target)) return;
            // Ignore clicks inside any Radix/portaled dialog so the panel
            // stays expanded while the confirmation flow runs.
            if (target instanceof Element && target.closest('[role="dialog"], [role="alertdialog"]')) {
                return;
            }
            setIsExpanded(false);
        };
        if (isExpanded) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [isExpanded]);

    // Auto-dismiss compaction success message after 5 seconds
    useEffect(() => {
        if (!compactSuccess) return;
        const timer = setTimeout(() => setCompactSuccess(null), 5000);
        return () => clearTimeout(timer);
    }, [compactSuccess]);

    // Auto-dismiss compaction error message after 8 seconds
    useEffect(() => {
        if (!compactError) return;
        const timer = setTimeout(() => setCompactError(null), 8000);
        return () => clearTimeout(timer);
    }, [compactError]);

    const pct = usage?.usagePercentage ?? 0;
    const colorClass = getUsageColor(pct);
    const formattedCurrent = formatTokenCount(usage?.currentContextTokens ?? 0);
    const formattedLimit = usage?.maxInputTokens ? formatTokenCount(usage.maxInputTokens) : null;

    // Show compress button when 15+ messages OR 2%+ token usage
    const shouldShowCompressButton = useMemo(() => messageCount >= COMPACT_BUTTON_MIN_MESSAGES || pct >= COMPACT_BUTTON_MIN_USAGE_PCT, [messageCount, pct]);

    const requestCompress = () => {
        if (isCompacting) return;
        setShowCompactConfirm(true);
    };

    const handleCompress = async () => {
        if (isCompacting) return;
        setCompactError(null);
        setCompactSuccess(null);
        try {
            const result = await compactMutation.mutateAsync(undefined);
            setCompactSuccess(`Compacted ${result.eventsCompacted} events. ${result.remainingTokens > 0 ? `${formatTokenCount(result.remainingTokens)} tokens remaining.` : ""}`);
            // Auto-expand the panel so the user sees the success/summary message
            setIsExpanded(true);

            // Backend persists both the compaction_notification chat task and
            // a synthetic compaction-cost task row. The mutation's onSuccess
            // invalidates chat-tasks + context-usage queries so the normal
            // pipeline renders the notification and the indicator reflects the
            // post-compaction drop — no frontend message injection needed.
            await queryClient.invalidateQueries({ queryKey: sessionKeys.chatTasks(sessionId) });
            onCompacted?.();
        } catch (err) {
            setCompactError(err instanceof Error ? err.message : "Failed to compact session");
        }
    };

    if (!sessionId) return null;
    if (!usage) return null; // Still loading or API failed — hide silently
    // Hide when the model's context limit is unknown (LiteLLM has no info) —
    // showing a progress bar against a made-up 200K limit would be misleading.
    if (usage.maxInputTokens == null) return null;

    return (
        <div ref={containerRef} className="relative inline-block">
            {/* Expanded panel — floats above the toolbar via absolute positioning */}
            {isExpanded && (
                <div className="absolute right-0 bottom-full z-50 mb-1 w-64 rounded-lg border bg-(--background-w10) text-(--primary-text-wMain) shadow-lg">
                    <div className="space-y-3 p-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold">Context Window Usage</span>
                        </div>

                        <div className="space-y-1">
                            <Progress value={pct} className="h-2" />
                            <div className="text-muted-foreground flex justify-between text-xs">
                                <span>{formattedCurrent} used</span>
                                {formattedLimit && <span>{formattedLimit} limit</span>}
                            </div>
                        </div>

                        <div className="space-y-2 text-xs">
                            <div className="flex items-center justify-between border-t pt-2">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span className="text-muted-foreground">Session total</span>
                                    </TooltipTrigger>
                                    <TooltipContent>Cumulative tokens sent and received across this agent's tasks in the session</TooltipContent>
                                </Tooltip>
                                <div className="flex items-center gap-3 font-mono text-xs">
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span className="flex items-center gap-1">
                                                <ArrowUp className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(usage.promptTokens)}
                                            </span>
                                        </TooltipTrigger>
                                        <TooltipContent>Total sent (prompt tokens)</TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <span className="flex items-center gap-1">
                                                <ArrowDown className="text-muted-foreground h-3 w-3" />
                                                {formatTokenCount(usage.completionTokens)}
                                            </span>
                                        </TooltipTrigger>
                                        <TooltipContent>Total received (completion tokens)</TooltipContent>
                                    </Tooltip>
                                </div>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-muted-foreground shrink-0">Model:</span>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span className="min-w-0 truncate font-mono font-semibold">{formatModelName(usage.model)}</span>
                                    </TooltipTrigger>
                                    <TooltipContent className="max-w-xs break-all">{usage.model}</TooltipContent>
                                </Tooltip>
                            </div>
                            <div className="flex items-center justify-between border-t pt-2">
                                <span className="text-muted-foreground flex items-center gap-1">
                                    <MessageSquare className="h-3 w-3" />
                                    Messages
                                </span>
                                <span className="font-mono">{usage.totalMessages}</span>
                            </div>
                        </div>

                        {shouldShowCompressButton && (
                            <div className="space-y-2 border-t pt-3">
                                {compactSuccess && (
                                    <div className="flex items-start justify-between gap-1 rounded bg-(--success-w10) p-2 text-xs text-(--success-wMain)">
                                        <span>{compactSuccess}</span>
                                        <button className="shrink-0 opacity-60 hover:opacity-100" onClick={() => setCompactSuccess(null)} aria-label="Dismiss">
                                            ✕
                                        </button>
                                    </div>
                                )}
                                {compactError && (
                                    <div className="flex items-start justify-between gap-1 rounded bg-(--error-w10) p-2 text-xs text-(--error-wMain)">
                                        <span>{compactError}</span>
                                        <button className="shrink-0 opacity-60 hover:opacity-100" onClick={() => setCompactError(null)} aria-label="Dismiss">
                                            ✕
                                        </button>
                                    </div>
                                )}
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button variant="outline" size="sm" className="w-full" onClick={requestCompress} disabled={isCompacting}>
                                            {isCompacting ? (
                                                <>
                                                    <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                                    Summarizing...
                                                </>
                                            ) : (
                                                <>
                                                    <Sparkles className="mr-2 h-3 w-3" />
                                                    Summarize Conversation
                                                </>
                                            )}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Summarize older messages to free context space</TooltipContent>
                                </Tooltip>
                            </div>
                        )}

                        {pct >= 90 && <div className="rounded bg-(--error-w10) p-2 text-xs text-(--error-wMain)">Approaching context limit! Consider compacting the conversation.</div>}
                        {pct >= 75 && pct < 90 && <div className="rounded bg-(--warning-w10) p-2 text-xs text-(--warning-wMain)">Context usage is high. Consider compacting soon.</div>}
                    </div>
                </div>
            )}

            {/* Compact trigger — always visible in the toolbar, never changes size */}
            <div className="rounded-lg border bg-(--background-w10)">
                <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                        <div className="cursor-pointer p-2" onClick={() => setIsExpanded(prev => !prev)}>
                            <div className="flex items-center gap-2">
                                <div className="w-36 space-y-1">
                                    <Progress value={pct} className="h-1.5" />
                                    <div className={`text-center font-mono text-[10px] ${colorClass}`}>Context Usage: {pct}%</div>
                                </div>
                                {(shouldShowCompressButton || isCompacting) && (
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div
                                                className="text-muted-foreground hover:text-foreground cursor-pointer p-1"
                                                onClick={e => {
                                                    e.stopPropagation();
                                                    if (!isCompacting) requestCompress();
                                                }}
                                            >
                                                {isCompacting ? <Loader2 className="h-4 w-4 animate-spin text-(--primary-wMain)" /> : <CompressionIcon className="h-4 w-4" />}
                                            </div>
                                        </TooltipTrigger>
                                        <TooltipContent side="top">{isCompacting ? "Compacting..." : "Compact conversation"}</TooltipContent>
                                    </Tooltip>
                                )}
                            </div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                        <p className="font-semibold">Context Window Usage</p>
                        <p className="text-xs">{formattedLimit ? `${formattedCurrent} / ${formattedLimit} tokens (${pct}%)` : `${formattedCurrent} tokens used`}</p>
                    </TooltipContent>
                </Tooltip>
            </div>

            <ConfirmationDialog
                open={showCompactConfirm}
                onOpenChange={setShowCompactConfirm}
                title="Compact conversation?"
                description="Older messages will be summarized so the agent has more room for new context. Your chat history stays visible here, but on the next turn the agent will work from the summary instead of the full original messages. This cannot be undone."
                actionLabels={{ confirm: "Compact", cancel: "Cancel" }}
                isLoading={isCompacting}
                onConfirm={handleCompress}
            />
        </div>
    );
}
