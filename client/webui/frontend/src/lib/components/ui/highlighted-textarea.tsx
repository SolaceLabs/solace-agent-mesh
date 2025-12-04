import * as React from "react";
import { cn } from "@/lib/utils";

interface HighlightedTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    /** Pattern to highlight - defaults to {{variable}} pattern */
    highlightPattern?: RegExp;
    /** CSS class for highlighted text */
    highlightClassName?: string;
}

/**
 * A textarea component with syntax highlighting for template variables.
 * Uses an overlay technique where a transparent textarea sits on top of
 * a highlighted backdrop div that mirrors the textarea content.
 */
const HighlightedTextarea = React.forwardRef<HTMLTextAreaElement, HighlightedTextareaProps>(({ className, value, highlightPattern = /(\{\{[^}]+\}\})/g, highlightClassName = "bg-primary/20 text-primary rounded px-0.5", ...props }, ref) => {
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

    // Highlight variables in the text
    const highlightText = React.useCallback(
        (text: string) => {
            if (!text) return null;

            const parts = text.split(highlightPattern);
            return parts.map((part, index) => {
                if (part.match(highlightPattern)) {
                    return (
                        <mark key={index} className={highlightClassName}>
                            {part}
                        </mark>
                    );
                }
                return <span key={index}>{part}</span>;
            });
        },
        [highlightPattern, highlightClassName]
    );

    const textValue = typeof value === "string" ? value : "";

    return (
        <div className="relative">
            {/* Backdrop with highlighted content */}
            <div
                ref={backdropRef}
                className={cn("pointer-events-none absolute inset-0 overflow-hidden break-words whitespace-pre-wrap", "rounded-md border border-transparent px-3 py-2", "font-mono text-sm", className)}
                style={{
                    // Match textarea styling exactly
                    lineHeight: "1.5",
                    wordWrap: "break-word",
                    overflowWrap: "break-word",
                }}
                aria-hidden="true"
            >
                {highlightText(textValue)}
                {/* Add extra space at the end to match textarea behavior */}
                <br />
            </div>

            {/* Transparent textarea on top for editing */}
            <textarea
                ref={textareaRef}
                className={cn(
                    "relative z-10 flex min-h-[80px] w-full rounded-md border bg-transparent px-3 py-2",
                    "placeholder:opacity-75 disabled:cursor-not-allowed disabled:opacity-50",
                    "caret-foreground font-mono text-sm",
                    // Make text transparent so backdrop shows through, but keep caret visible
                    "text-transparent",
                    className
                )}
                style={{
                    // Ensure consistent styling with backdrop
                    lineHeight: "1.5",
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
});

HighlightedTextarea.displayName = "HighlightedTextarea";

export { HighlightedTextarea };
export type { HighlightedTextareaProps };
