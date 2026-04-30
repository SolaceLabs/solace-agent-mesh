/**
 * Inline Progress Updates Component
 *
 * Displays a vertical timeline of progress updates inline within the AI response message.
 * During streaming: shows full timeline with dots, spinner, and connecting line.
 * After completion: collapses into "Activity Timeline >" that can be expanded to see the full history.
 * The "Show Full Activity" workflow button is displayed next to the header in all states.
 */

import { useState, useEffect, useRef, Fragment } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { MarkdownWrapper } from "@/lib/components";
import { cn } from "@/lib/utils";
import type { ProgressUpdate } from "@/lib/types";

interface InlineProgressUpdatesProps {
    /** Array of progress update objects accumulated during the task */
    updates: ProgressUpdate[];
    /** Whether the task is still in progress (shows spinner on last item) */
    isActive?: boolean;
    /** Callback to view the workflow/activity panel */
    onViewWorkflow?: () => void;
}

/** Maximum number of updates to show before collapsing the list */
const COLLAPSE_THRESHOLD = 10;

export const InlineProgressUpdates = ({ updates, isActive = false, onViewWorkflow }: InlineProgressUpdatesProps) => {
    const [isTimelineOpen, setIsTimelineOpen] = useState(true);
    const [isListExpanded, setIsListExpanded] = useState(false);
    const [expandedThinkingIds, setExpandedThinkingIds] = useState<Set<number>>(new Set());
    const hasAutoCollapsed = useRef(false);

    // Auto-collapse timeline when task completes
    useEffect(() => {
        if (!isActive && !hasAutoCollapsed.current && updates.length > 0) {
            hasAutoCollapsed.current = true;
            setIsTimelineOpen(false);
        }
    }, [isActive, updates.length]);

    // No updates yet — the inline breathing indicator under the message provides feedback.
    if (!updates || updates.length === 0) return null;

    // Deduplicate consecutive identical updates (by text), but never deduplicate thinking items
    const deduped = updates.filter((update, index) => update.type === "thinking" || index === 0 || update.text !== updates[index - 1].text);

    const shouldCollapseList = deduped.length > COLLAPSE_THRESHOLD;
    const visibleIndices = shouldCollapseList && !isListExpanded ? [0, ...Array.from({ length: 2 }, (_, i) => deduped.length - 2 + i)] : deduped.map((_, i) => i);
    const visibleUpdates = visibleIndices.map(i => deduped[i]);
    const hiddenCount = shouldCollapseList && !isListExpanded ? Math.max(0, deduped.length - visibleUpdates.length) : 0;

    const toggleThinking = (dedupedIndex: number) => {
        setExpandedThinkingIds(prev => {
            const next = new Set(prev);
            if (next.has(dedupedIndex)) {
                next.delete(dedupedIndex);
            } else {
                next.add(dedupedIndex);
            }
            return next;
        });
    };

    // Collapsed state: show "< Activity Timeline"
    if (!isTimelineOpen) {
        return (
            <div className="mb-3 flex items-center gap-2">
                <Button variant="ghost" className="flex items-center gap-1 text-sm text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)" onClick={() => setIsTimelineOpen(true)}>
                    <ChevronRight className="h-3.5 w-3.5" />
                    <span className="font-medium">Activity Timeline</span>
                </Button>
                {onViewWorkflow && <ViewWorkflowButton onClick={onViewWorkflow} text="Show Full Activity" />}
            </div>
        );
    }

    return (
        <div className="mb-3">
            {/* Header with title and workflow button */}
            <div className="mb-1 flex items-center gap-1">
                {!isActive ? (
                    <Button variant="ghost" className="flex items-center gap-1 text-sm text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)" onClick={() => setIsTimelineOpen(false)}>
                        <ChevronDown className="h-3.5 w-3.5" />
                        <span className="font-medium">Activity Timeline</span>
                    </Button>
                ) : (
                    <span className="px-2 py-1 text-sm font-medium text-(--secondary-text-wMain)">Activity Timeline</span>
                )}
                {onViewWorkflow && <ViewWorkflowButton onClick={onViewWorkflow} text="Show Full Activity" />}
            </div>

            {/* Timeline items wrapper - uses flex layout for guaranteed dot/line alignment */}
            <div className="relative">
                {/* Vertical connecting line - positioned in the center of the 20px dot column */}
                {visibleUpdates.length > 1 && <div className={cn("absolute top-[21px] left-[9px] z-0 w-[2px] rounded-full bg-current opacity-30", isActive ? "bottom-[33px]" : "bottom-[21px]")} />}

                {visibleUpdates.map((update, index) => {
                    const dedupedIndex = visibleIndices[index];
                    const isLast = index === visibleUpdates.length - 1;
                    const isThinking = update.type === "thinking";
                    const isThinkingExpanded = expandedThinkingIds.has(dedupedIndex);
                    const isActiveStep = isLast && isActive;

                    // Show expand button after first item when list is collapsed
                    const showExpandButton = shouldCollapseList && !isListExpanded && index === 0;

                    return (
                        <Fragment key={`${update.timestamp}-${dedupedIndex}`}>
                            <div
                                className="flex items-start gap-3 py-2"
                                style={{
                                    animation: "progressSlideIn 0.3s ease-out both",
                                    animationDelay: `${Math.min(index * 50, 200)}ms`,
                                }}
                            >
                                {/* Dot or spinner indicator - fixed 20px wide column, centered */}
                                <div className="relative z-10 flex h-5 w-5 flex-shrink-0 items-center justify-center">
                                    {isActiveStep ? <Loader2 className="h-[14px] w-[14px] animate-spin text-(--primary-wMain)" /> : <div className="h-[10px] w-[10px] rounded-full bg-(--success-wMain)" />}
                                </div>

                                <div className="min-w-0 flex-1">
                                    {isThinking ? (
                                        /* Thinking/Reasoning item - collapsible */
                                        <div>
                                            <button
                                                type="button"
                                                className="flex items-center gap-1 text-sm leading-relaxed text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)"
                                                onClick={() => toggleThinking(dedupedIndex)}
                                            >
                                                <span className="font-medium">{update.text}</span>
                                                {isThinkingExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                                            </button>

                                            {/* Expandable thinking content */}
                                            {isThinkingExpanded && update.expandableContent && (
                                                <div className="mt-2 rounded-lg px-3 py-2">
                                                    <div className="max-h-96 overflow-y-auto text-sm text-(--secondary-text-wMain) opacity-70">
                                                        <MarkdownWrapper content={update.expandableContent} />
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        /* Regular status text */
                                        <span className={`text-sm leading-relaxed ${isActiveStep ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>{update.text}</span>
                                    )}
                                </div>
                            </div>

                            {/* Expand button between first and last items when list is collapsed */}
                            {showExpandButton && (
                                <div className="py-0.5">
                                    <Button variant="ghost" size="sm" className="h-6 gap-1 px-1 text-xs text-(--secondary-text-wMain) hover:text-(--primary-text-wMain)" onClick={() => setIsListExpanded(true)}>
                                        <ChevronDown className="h-3 w-3" />
                                        {hiddenCount} more step{hiddenCount > 1 ? "s" : ""}
                                    </Button>
                                </div>
                            )}
                        </Fragment>
                    );
                })}
            </div>

            {/* Collapse list button */}
            {shouldCollapseList && isListExpanded && (
                <div className="py-0.5">
                    <Button variant="ghost" size="sm" className="h-6 gap-1 px-1 text-xs text-(--secondary-text-wMain) hover:text-(--primary-text-wMain)" onClick={() => setIsListExpanded(false)}>
                        <ChevronUp className="h-3 w-3" />
                        Show less
                    </Button>
                </div>
            )}
        </div>
    );
};

export default InlineProgressUpdates;
