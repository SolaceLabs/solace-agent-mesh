import * as React from "react";
import { cn } from "@/lib/utils";

interface MentionTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    /** Pattern to highlight mentions - defaults to @Name pattern */
    mentionPattern?: RegExp;
    /** CSS class for highlighted mentions */
    mentionClassName?: string;
}

/**
 * A textarea component with visual highlighting for @mentions.
 * Uses an overlay technique where a transparent textarea sits on top of
 * a highlighted backdrop div that mirrors the textarea content.
 */
const MentionTextarea = React.forwardRef<HTMLTextAreaElement, MentionTextareaProps>(
    (
        {
            className,
            value,
            mentionPattern = /@([^\s@]+(?:\s+[^\s@]+)*)/g,
            mentionClassName = "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded px-1 font-medium",
            ...props
        },
        ref
    ) => {
        const backdropRef = React.useRef<HTMLDivElement>(null);
        const textareaRef = React.useRef<HTMLTextAreaElement>(null);

        // Combine refs
        React.useImperativeHandle(ref, () => textareaRef.current!);

        // Sync scroll position between textarea and backdrop
        const handleScroll = React.useCallback(() => {
            if (backdropRef.current && textareaRef.current) {
                backdropRef.current.scrollTop = textareaRef.current.scrollTop;
                backdropRef.current.scrollLeft = textareaRef.current.scrollLeft;
            }
        }, []);

        // Highlight mentions in the text
        const highlightMentions = React.useCallback(
            (text: string) => {
                if (!text) return null;

                const parts: React.ReactNode[] = [];
                let lastIndex = 0;

                // Use matchAll to find all mentions
                const matches = Array.from(text.matchAll(mentionPattern));

                matches.forEach((match, idx) => {
                    const matchStart = match.index!;
                    const matchEnd = matchStart + match[0].length;

                    // Add text before this match
                    if (matchStart > lastIndex) {
                        parts.push(
                            <span key={`text-${idx}`}>
                                {text.substring(lastIndex, matchStart)}
                            </span>
                        );
                    }

                    // Add highlighted mention
                    parts.push(
                        <mark key={`mention-${idx}`} className={mentionClassName}>
                            {match[0]}
                        </mark>
                    );

                    lastIndex = matchEnd;
                });

                // Add remaining text after last match
                if (lastIndex < text.length) {
                    parts.push(
                        <span key="text-end">
                            {text.substring(lastIndex)}
                        </span>
                    );
                }

                return parts.length > 0 ? parts : <span>{text}</span>;
            },
            [mentionPattern, mentionClassName]
        );

        const textValue = typeof value === "string" ? value : "";

        return (
            <div className="relative">
                {/* Backdrop with highlighted mentions */}
                <div
                    ref={backdropRef}
                    className={cn(
                        "pointer-events-none absolute inset-0 overflow-hidden break-words whitespace-pre-wrap",
                        className
                    )}
                    style={{
                        // Match textarea styling exactly
                        lineHeight: "inherit",
                        wordWrap: "break-word",
                        overflowWrap: "break-word",
                        padding: "inherit",
                    }}
                    aria-hidden="true"
                >
                    {highlightMentions(textValue)}
                    {/* Add extra space at the end to match textarea behavior */}
                    <br />
                </div>

                {/* Transparent textarea on top for editing */}
                <textarea
                    ref={textareaRef}
                    className={cn(
                        "relative z-10 w-full bg-transparent",
                        "caret-foreground",
                        // Make text transparent so backdrop shows through, but keep caret visible
                        "text-transparent",
                        className
                    )}
                    style={{
                        // Ensure consistent styling with backdrop
                        lineHeight: "inherit",
                        caretColor: "var(--foreground)",
                        // WebKit specific: hide selection background to avoid double-rendering
                        WebkitTextFillColor: "transparent",
                    }}
                    value={value}
                    onScroll={handleScroll}
                    {...props}
                />
            </div>
        );
    }
);

MentionTextarea.displayName = "MentionTextarea";

export { MentionTextarea };
export type { MentionTextareaProps };
