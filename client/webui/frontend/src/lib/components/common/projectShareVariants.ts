import { cva } from "class-variance-authority";

// Icon button for remove/close actions
export const classForIconButton = cva(["h-8", "w-8", "p-0", "text-[var(--muted-foreground)]", "hover:text-[var(--foreground)]"]);

// Empty state / no results message
export const classForEmptyMessage = cva(["text-center", "text-sm", "text-[var(--muted-foreground)]"], {
    variants: {
        size: {
            default: "py-8",
            compact: "p-4",
        },
    },
    defaultVariants: { size: "default" },
});
