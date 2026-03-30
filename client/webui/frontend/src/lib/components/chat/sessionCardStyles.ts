import { cva } from "class-variance-authority";

/** Full-page card variant (RecentChatsPage) */
export const sessionCardStyles = cva(["group", "relative", "rounded-lg", "border", "p-4", "transition-colors"], {
    variants: {
        active: {
            true: "border-(--brand-w60) bg-(--secondary-w10)",
            false: "hover:bg-(--primary-w10)",
        },
        size: {
            default: "h-[75px]",
        },
    },
    defaultVariants: { active: false, size: "default" },
});

/** Inline row variant (SessionList side panel) */
export const sessionRowStyles = cva(["flex", "items-center", "gap-2", "rounded-xs", "px-2", "py-2"], {
    variants: {
        active: {
            true: "bg-(--secondary-w10)",
            false: "hover:bg-(--primary-w10)",
        },
    },
    defaultVariants: { active: false },
});

/** Session title text with animation variants */
export const sessionTitleStyles = cva(["truncate", "text-sm", "transition-opacity", "duration-300"], {
    variants: {
        active: {
            true: "font-bold text-(--primary-text-wMain)",
            false: "font-medium text-(--primary-text-wMain)",
        },
        animation: {
            pulseGenerate: "animate-pulse-slow",
            pulseWait: "animate-pulse opacity-50",
            none: "opacity-100",
        },
    },
    defaultVariants: { active: false, animation: "none" },
});
