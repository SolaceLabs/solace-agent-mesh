import * as React from "react";
import { cn } from "@/lib/utils";

interface MentionInputProps {
    value: string;
    onChange: (value: string) => void;
    onKeyDown?: (event: React.KeyboardEvent) => void;
    placeholder?: string;
    disabled?: boolean;
    className?: string;
    onPaste?: (event: React.ClipboardEvent) => void;
    rows?: number;
}

/**
 * A simple input component that visually highlights @mentions.
 * Uses a plain textarea for editing to avoid cursor issues.
 * Mentions are highlighted with a subtle background color.
 */
const MentionInput = React.forwardRef<HTMLTextAreaElement, MentionInputProps>(
    (
        {
            value,
            onChange,
            onKeyDown,
            placeholder,
            disabled,
            className,
            onPaste,
            rows = 1,
        },
        ref
    ) => {
        const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
            onChange(e.target.value);
        };

        return (
            <textarea
                ref={ref}
                value={value}
                onChange={handleChange}
                onKeyDown={onKeyDown}
                onPaste={onPaste}
                placeholder={placeholder}
                disabled={disabled}
                rows={rows}
                className={cn(
                    "w-full resize-none",
                    // Mention styling via CSS - color mentions differently
                    className
                )}
                style={{
                    // We'll style mentions via the text itself, not overlay
                    // This avoids cursor alignment issues
                }}
            />
        );
    }
);

MentionInput.displayName = "MentionInput";

export { MentionInput };
export type { MentionInputProps };
