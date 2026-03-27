/**
 * Inline Progress Updates Component
 *
 * Displays a vertical timeline of progress updates inline within the AI response message.
 * Each update appears as a bullet point with a colored dot and connecting vertical line,
 * showing status updates, tool calls, artifact creation, agent delegation, and reasoning.
 *
 * "Thinking" type items render as collapsible steps with expandable reasoning content.
 */

import React, { useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { MarkdownWrapper } from "@/lib/components";
import type { ProgressUpdate } from "@/lib/types";

interface InlineProgressUpdatesProps {
    /** Array of progress update objects accumulated during the task */
    updates: ProgressUpdate[];
    /** Whether the task is still in progress (shows spinner on last item) */
    isActive?: boolean;
    /** Callback to view the workflow/activity panel */
    onViewWorkflow?: () => void;
}

/** Maximum number of updates to show before collapsing */
const COLLAPSE_THRESHOLD = 5;

export const InlineProgressUpdates: React.FC<InlineProgressUpdatesProps> = ({ updates, isActive = false, onViewWorkflow }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [expandedThinkingIds, setExpandedThinkingIds] = useState<Set<number>>(new Set());

    if (!updates || updates.length === 0) {
        return null;
    }

    // Deduplicate consecutive identical updates (by text), but never deduplicate thinking items
    const deduped = updates.filter((update, index) => update.type === "thinking" || index === 0 || update.text !== updates[index - 1].text);

    const shouldCollapse = deduped.length > COLLAPSE_THRESHOLD;
    const visibleUpdates = shouldCollapse && !isExpanded ? [deduped[0], ...deduped.slice(-2)] : deduped;
    const hiddenCount = deduped.length - COLLAPSE_THRESHOLD;

    const toggleThinking = (index: number) => {
        setExpandedThinkingIds(prev => {
            const next = new Set(prev);
            if (next.has(index)) {
                next.delete(index);
            } else {
                next.add(index);
            }
            return next;
        });
    };

    return (
        <div className="mb-3 ml-[9px] pl-5">
            {/* Timeline items wrapper - line is relative to this container only */}
            <div className="relative">
                {/* Vertical connecting line - runs from first dot center to last dot center */}
                {visibleUpdates.length > 1 && (
                    <div
                        className="absolute left-[-12px] w-[2px] rounded-full opacity-30"
                        style={{
                            top: "21px",
                            bottom: "21px",
                            backgroundColor: "currentColor",
                        }}
                    />
                )}

                {visibleUpdates.map((update, index) => {
                    const isLast = index === visibleUpdates.length - 1;
                    const isThinking = update.type === "thinking";
                    const isThinkingExpanded = expandedThinkingIds.has(index);

                    // Show expand button after first item when collapsed
                    const showExpandButton = shouldCollapse && !isExpanded && index === 0;

                    const isActiveStep = isLast && isActive;

                    return (
                        <React.Fragment key={`${update.timestamp}-${index}`}>
                            <div className="relative py-3">
                                {/* Dot or spinner indicator - centered on the vertical line */}
                                {isActiveStep ? (
                                    <Loader2 className="absolute top-[13px] left-[-20px] z-10 h-[16px] w-[16px] animate-spin text-(--primary-wMain)" />
                                ) : (
                                    <div className="absolute top-[16px] left-[-17px] z-10 h-[10px] w-[10px] rounded-full bg-(--success-wMain)" />
                                )}

                                {isThinking ? (
                                    /* Thinking/Reasoning item - collapsible */
                                    <div>
                                        <button type="button" className="flex items-center gap-1 text-sm leading-relaxed text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)" onClick={() => toggleThinking(index)}>
                                            <span className="font-medium">{update.text}</span>
                                            {isThinkingExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                                        </button>

                                        {/* Expandable thinking content */}
                                        {isThinkingExpanded && update.expandableContent && (
                                            <div className="mt-2 rounded-lg border border-(--border-wMain) bg-(--secondary-bg-wMain)/30 px-3 py-2">
                                                <div className="max-h-96 overflow-y-auto text-sm text-(--secondary-text-wMain) opacity-70">
                                                    <MarkdownWrapper content={update.expandableContent} />
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    /* Regular status text */
                                    <span className={`text-sm leading-relaxed ${isLast && isActive ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>
                                        {update.type === "artifact" && <span className="font-medium">Artifact: </span>}
                                        {update.type === "tool_call" && <span className="font-medium">Tool: </span>}
                                        {update.type === "delegation" && <span className="font-medium">Agent: </span>}
                                        {update.text}
                                    </span>
                                )}
                            </div>

                            {/* Expand button between first and last items when collapsed */}
                            {showExpandButton && (
                                <div className="py-0.5">
                                    <Button variant="ghost" size="sm" className="h-6 gap-1 px-1 text-xs text-(--secondary-text-wMain) hover:text-(--primary-text-wMain)" onClick={() => setIsExpanded(true)}>
                                        <ChevronDown className="h-3 w-3" />
                                        {hiddenCount} more step{hiddenCount > 1 ? "s" : ""}
                                    </Button>
                                </div>
                            )}
                        </React.Fragment>
                    );
                })}
            </div>

            {/* Collapse button - outside the timeline container so line doesn't extend to it */}
            {shouldCollapse && isExpanded && (
                <div className="py-0.5">
                    <Button variant="ghost" size="sm" className="h-6 gap-1 px-1 text-xs text-(--secondary-text-wMain) hover:text-(--primary-text-wMain)" onClick={() => setIsExpanded(false)}>
                        <ChevronUp className="h-3 w-3" />
                        Show less
                    </Button>
                </div>
            )}

            {/* View Workflow button */}
            {onViewWorkflow && (
                <div className="mt-1">
                    <ViewWorkflowButton onClick={onViewWorkflow} />
                </div>
            )}
        </div>
    );
};

export default InlineProgressUpdates;
