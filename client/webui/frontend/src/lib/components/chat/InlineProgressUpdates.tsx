/**
 * Inline Progress Updates Component
 *
 * Displays a vertical timeline of progress updates inline within the AI response message.
 * During streaming: shows full timeline with dots, spinner, and connecting line.
 * After completion: collapses into "Timeline >" that can be expanded to see the full history.
 */

import React, { useState, useEffect, useRef } from "react";
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

/** Maximum number of updates to show before collapsing the list */
const COLLAPSE_THRESHOLD = 10;

export const InlineProgressUpdates: React.FC<InlineProgressUpdatesProps> = ({ updates, isActive = false, onViewWorkflow }) => {
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

    if (!updates || updates.length === 0) {
        return null;
    }

    // Deduplicate consecutive identical updates (by text), but never deduplicate thinking items
    const deduped = updates.filter((update, index) => update.type === "thinking" || index === 0 || update.text !== updates[index - 1].text);

    const shouldCollapseList = deduped.length > COLLAPSE_THRESHOLD;
    const visibleUpdates = shouldCollapseList && !isListExpanded ? [deduped[0], ...deduped.slice(-2)] : deduped;
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

    // Collapsed state: show "Timeline >"
    if (!isTimelineOpen) {
        return (
            <div className="mb-3 ml-[9px] flex items-center gap-2 pl-5">
                <button type="button" className="flex items-center gap-1 text-sm text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)" onClick={() => setIsTimelineOpen(true)}>
                    <span className="font-medium">Timeline</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                </button>
            </div>
        );
    }

    return (
        <div className="mb-3 ml-[9px] pl-5">
            {/* Collapse header when task is complete */}
            {!isActive && (
                <div className="mb-1">
                    <button type="button" className="flex items-center gap-1 text-sm text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)" onClick={() => setIsTimelineOpen(false)}>
                        <span className="font-medium">Timeline</span>
                        <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                </div>
            )}

            {/* Timeline items wrapper - line is relative to this container only */}
            <div className="relative">
                {/* Vertical connecting line - stops before the last dot center */}
                {visibleUpdates.length > 1 && (
                    <div
                        className="absolute left-[-12px] z-0 w-[2px] rounded-full opacity-30"
                        style={{
                            top: "21px",
                            /* End line at the top of the last dot, not through it */
                            bottom: isActive ? "28px" : "21px",
                            backgroundColor: "currentColor",
                        }}
                    />
                )}

                {visibleUpdates.map((update, index) => {
                    const isLast = index === visibleUpdates.length - 1;
                    const isThinking = update.type === "thinking";
                    const isThinkingExpanded = expandedThinkingIds.has(index);
                    const isActiveStep = isLast && isActive;

                    // Show expand button after first item when list is collapsed
                    const showExpandButton = shouldCollapseList && !isListExpanded && index === 0;

                    return (
                        <React.Fragment key={`${update.timestamp}-${index}`}>
                            <div className="relative py-3">
                                {/* Dot or spinner indicator */}
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
                                            <div className="mt-2 rounded-lg px-3 py-2">
                                                <div className="max-h-96 overflow-y-auto text-sm text-(--secondary-text-wMain) opacity-70">
                                                    <MarkdownWrapper content={update.expandableContent} />
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    /* Regular status text */
                                    <span className={`text-sm leading-relaxed ${isActiveStep ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>
                                        {update.type === "artifact" && <span className="font-medium">Artifact: </span>}
                                        {update.type === "tool_call" && <span className="font-medium">Tool: </span>}
                                        {update.type === "delegation" && <span className="font-medium">Agent: </span>}
                                        {update.text}
                                    </span>
                                )}
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
                        </React.Fragment>
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

            {/* View Workflow button during active streaming (when no header is shown) */}
            {isActive && onViewWorkflow && (
                <div className="mt-1">
                    <ViewWorkflowButton onClick={onViewWorkflow} />
                </div>
            )}
        </div>
    );
};

export default InlineProgressUpdates;
