import React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => {
    return (
        <textarea
            className={cn(
                // Layout & Sizing
                "flex min-h-[80px] w-full min-w-0",

                // Border & Background
                "border-input rounded-xs border bg-transparent",

                // Spacing
                "px-3 py-2",

                // Typography
                "text-base md:text-sm",

                // Visual Effects
                "shadow-xs transition-[color,box-shadow] outline-none",

                // Placeholder
                "placeholder:text-placeholder",

                // Focus State
                "focus-visible:border-[var(--color-brand-wMain)]",

                // Disabled State
                "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",

                // Readonly State
                "read-only:cursor-default read-only:opacity-80",

                // Invalid/Error State
                "aria-invalid:border-[var(--color-error-w100)]",
                className
            )}
            ref={ref}
            {...props}
        />
    );
});
Textarea.displayName = "Textarea";

export { Textarea };
