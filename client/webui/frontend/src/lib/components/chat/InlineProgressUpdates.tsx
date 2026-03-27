/**
 * Inline Progress Updates Component
 *
 * Displays a vertical timeline of progress updates inline within the AI response message.
 * Each update appears as a bullet point with a colored dot and connecting vertical line,
 * showing status updates, tool calls, artifact creation, and agent delegation events.
 */

import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/lib/components/ui";
import type { ProgressUpdate } from "@/lib/types";

interface InlineProgressUpdatesProps {
    /** Array of progress update objects accumulated during the task */
    updates: ProgressUpdate[];
    /** Whether the task is still in progress (shows pulse animation on last item) */
    isActive?: boolean;
}

/** Maximum number of updates to show before collapsing */
const COLLAPSE_THRESHOLD = 3;

export const InlineProgressUpdates: React.FC<InlineProgressUpdatesProps> = ({ updates, isActive = false }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!updates || updates.length === 0) {
        return null;
    }

    // Deduplicate consecutive identical updates (by text)
    const deduped = updates.filter((update, index) => index === 0 || update.text !== updates[index - 1].text);

    const shouldCollapse = deduped.length > COLLAPSE_THRESHOLD;
    const visibleUpdates = shouldCollapse && !isExpanded ? [deduped[0], ...deduped.slice(-2)] : deduped;
    const hiddenCount = deduped.length - COLLAPSE_THRESHOLD;

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

                    // Show expand button after first item when collapsed
                    const showExpandButton = shouldCollapse && !isExpanded && index === 0;

                    // Determine dot color based on update type and state
                    const dotColor = isLast && isActive ? "animate-pulse bg-(--primary-wMain)" : "bg-(--success-wMain)";

                    return (
                        <React.Fragment key={`${update.timestamp}-${index}`}>
                            <div className="relative flex items-start py-3">
                                {/* Dot indicator - centered on the vertical line */}
                                <div className={`absolute top-[16px] left-[-17px] z-10 h-[10px] w-[10px] rounded-full ${dotColor}`} />

                                {/* Status text */}
                                <span className={`text-sm leading-relaxed ${isLast && isActive ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>
                                    {update.type === "artifact" && <span className="font-medium">Artifact: </span>}
                                    {update.type === "tool_call" && <span className="font-medium">Tool: </span>}
                                    {update.type === "delegation" && <span className="font-medium">Agent: </span>}
                                    {update.text}
                                </span>
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
        </div>
    );
};

export default InlineProgressUpdates;
