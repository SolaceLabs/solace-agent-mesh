import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: ComponentProps<"input">) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
                // Layout & Sizing
                "flex h-9 w-full min-w-0",

                // Border & Background
                "border-input rounded-xs border bg-transparent",

                // Spacing
                "px-3 py-1",

                // Typography
                "text-base md:text-sm",

                // Visual Effects
                "shadow-xs transition-[color,box-shadow] outline-none",

                // Placeholder & Selection
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
            {...props}
        />
    );
}

export { Input };
