/**
 * ThinkingBlock Component
 *
 * Displays LLM thinking/reasoning content in a collapsible block above the main AI response.
 * Similar to how Claude.ai shows extended thinking — collapsed by default once thinking
 * is complete, expandable on click to reveal the full reasoning process.
 *
 * Supports streaming: shows a pulsing "Thinking..." indicator while thinking tokens
 * are still arriving, then transitions to a static collapsed state.
 */

import React, { useState, useEffect, useRef } from "react";
import { Brain, ChevronDown, ChevronUp } from "lucide-react";
import { MarkdownWrapper } from "@/lib/components";

interface ThinkingBlockProps {
    /** The accumulated thinking/reasoning text */
    content: string;
    /** Whether the thinking phase is complete */
    isComplete: boolean;
}

export const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ content, isComplete }) => {
    // Auto-collapse when thinking completes and main response starts
    const [isExpanded, setIsExpanded] = useState(true);
    const hasAutoCollapsed = useRef(false);

    useEffect(() => {
        // Auto-collapse once thinking is complete (only once)
        if (isComplete && !hasAutoCollapsed.current) {
            hasAutoCollapsed.current = true;
            setIsExpanded(false);
        }
    }, [isComplete]);

    const charCount = content.length;
    const isThinking = !isComplete;

    return (
        <div className="mb-3 rounded-lg border border-(--border-wMain) bg-(--secondary-bg-wMain)/50">
            {/* Header — always visible, clickable to toggle */}
            <button type="button" className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-(--secondary-bg-wMain)" onClick={() => setIsExpanded(!isExpanded)}>
                <Brain className={`h-4 w-4 shrink-0 ${isThinking ? "animate-pulse text-(--primary-wMain)" : "text-(--secondary-text-wMain)"}`} />
                <span className={`font-medium ${isThinking ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>{isThinking ? "Thinking..." : "Thinking"}</span>
                {isComplete && <span className="text-xs text-(--secondary-text-wMain)">({charCount.toLocaleString()} chars)</span>}
                <span className="ml-auto shrink-0">{isExpanded ? <ChevronUp className="h-3.5 w-3.5 text-(--secondary-text-wMain)" /> : <ChevronDown className="h-3.5 w-3.5 text-(--secondary-text-wMain)" />}</span>
            </button>

            {/* Content — collapsible */}
            {isExpanded && content && (
                <div className="border-t border-(--border-wMain) px-3 py-2">
                    <div className="max-h-96 overflow-y-auto text-sm text-(--secondary-text-wMain)">
                        <MarkdownWrapper content={content} />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ThinkingBlock;
