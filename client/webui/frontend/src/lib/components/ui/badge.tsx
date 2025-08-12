import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const CLASS_NAMES_BY_TYPE = {
    error: "bg-[var(--color-error-w10)] text-[var(--color-error-wMain)] border-[var(--color-error-wMain)] dark:bg-[var(--color-error-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-error-w10)]",
    warning: "bg-[var(--color-warning-w10)] text-[var(--color-warning-wMain)] border-[var(--color-warning-wMain)] dark:bg-[var(--color-warning-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-warning-w10)]",
    info: "bg-[var(--color-info-w10)] text-[var(--color-info-wMain)] border-[var(--color-info-w10)] dark:bg-[var(--color-info-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-info-w10)]",
    success: "bg-[var(--color-success-w10)] text-[var(--color-success-wMain)] border-[var(--color-success-w10)] dark:bg-[var(--color-success-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-success-wMain)]",
};

const badgeVariants = cva(`inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none transition-[color,box-shadow] overflow-hidden`, {
    variants: {
        variant: {
            default: "border-transparent [a&]:hover:bg-primary/90",
            secondary: "border-transparent [a&]:hover:bg-secondary/90",
            destructive: "border-transparent [a&]:hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60",
            outline: "text-foreground [a&]:hover:bg-accent [a&]:hover:text-accent-foreground",
        },
        type: {
            error: CLASS_NAMES_BY_TYPE.error,
            warning: CLASS_NAMES_BY_TYPE.warning,
            info: CLASS_NAMES_BY_TYPE.info,
            success: CLASS_NAMES_BY_TYPE.success,
        },
    },
    defaultVariants: {
        variant: "default",
    },
});

function Badge({ className, variant, type, asChild = false, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
    const Comp = asChild ? Slot : "span";

    return <Comp data-slot="badge" className={cn(badgeVariants({ variant, type }), className)} {...props} />;
}

export { Badge };
