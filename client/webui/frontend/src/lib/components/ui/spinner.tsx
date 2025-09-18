import React from "react";
import { cn } from "@/lib/utils";
import { cva } from "class-variance-authority";
import type { VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";

const spinnerVariants = cva("flex-col items-center justify-center", {
    variants: {
        show: {
            true: "flex",
            false: "hidden",
        },
    },
    defaultVariants: {
        show: true,
    },
});

const loaderVariants = cva("animate-spin", {
    variants: {
        size: {
            small: "size-4",
            medium: "size-8",
            large: "size-12",
        },
        variant: {
            primary: "text-[var(--color-brand-wMain)]", // #00C895 (brand main color)
            secondary: "text-[var(--color-primary-wMain)]", // #015B82 (primary main)
            muted: "text-[var(--color-secondary-text-wMain)] dark:text-[var(--color-secondary-text-w50)]", // Muted text colors
            foreground: "text-foreground", // Standard foreground color
        },
    },
    defaultVariants: {
        size: "medium",
        variant: "primary",
    },
});

interface SpinnerContentProps extends VariantProps<typeof spinnerVariants>, VariantProps<typeof loaderVariants> {
    className?: string;
    children?: React.ReactNode;
}

export function Spinner({ size, show, children, className, variant }: SpinnerContentProps) {
    return (
        <span className={spinnerVariants({ show })}>
            <Loader2 className={cn(loaderVariants({ size, variant }), className)} />
            {children}
        </span>
    );
}
