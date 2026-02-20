import * as React from "react";
import { cn } from "@/lib/utils";

interface LifecycleBadgeProps {
    className?: string;
    children?: React.ReactNode;
    variant?: "default" | "transparent";
}

/**
 * Shared badge component for features, eg. EXPERIMENTAL, BETA
 * Used in navigation buttons and tab headers
 *
 * @param variant - "default" uses colored background (for navigation), "transparent" uses transparent background (for tabs)
 */
export const LifecycleBadge = ({ className, children = "EXPERIMENTAL", variant = "default" }: LifecycleBadgeProps) => {
    const isTransparent = variant === "transparent";

    return (
        <span
            className={cn(
                "border-border inline-flex shrink-0 items-center justify-center rounded-sm border-solid bg-transparent px-1 py-0.5 text-[10px] uppercase",
                isTransparent ? "text-muted-foreground border-2" : "border-muted-foreground border",
                className
            )}
        >
            {children}
        </span>
    );
};
