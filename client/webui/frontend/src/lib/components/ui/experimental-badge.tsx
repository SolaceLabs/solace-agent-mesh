import * as React from "react";
import { cn } from "@/lib/utils";

interface ExperimentalBadgeProps {
    className?: string;
    children?: React.ReactNode;
    variant?: "default" | "transparent";
}

/**
 * Shared badge component for experimental features
 * Used in navigation buttons and tab headers
 * Matches the shape and style of the standard Badge component
 *
 * @param variant - "default" uses colored background (for navigation), "transparent" uses transparent background (for tabs)
 */
export const ExperimentalBadge = ({ className, children = "EXPERIMENTAL", variant = "default" }: ExperimentalBadgeProps) => {
    const isTransparent = variant === "transparent";

    return (
        <span
            className={cn(
                "inline-flex items-center justify-center rounded-lg border px-2 py-0.5 text-xs font-medium",
                "w-fit shrink-0 whitespace-nowrap uppercase",
                isTransparent ? "border-gray-400 bg-transparent text-gray-600 dark:border-gray-500 dark:text-gray-400" : "bg-(--color-secondary-w80) text-(--color-secondary-text-w10)",
                className
            )}
        >
            {children}
        </span>
    );
};
