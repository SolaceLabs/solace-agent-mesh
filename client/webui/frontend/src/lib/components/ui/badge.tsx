import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

const CLASS_NAMES_BY_TYPE = {
    error: "bg-(--error-w10) text-(--error-wMain) border-(--error-wMain)",
    warning: "bg-(--warning-w10) text-(--warning-wMain) border-(--warning-wMain)",
    info: "bg-(--info-w10) text-(--info-wMain) border-(--info-w10)",
    success: "bg-(--success-w10) text-(--success-wMain) border-(--success-w10)",
};

const badgeVariants = cva(`inline-flex items-center justify-center rounded-lg border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none transition-[color,box-shadow] overflow-hidden`, {
    variants: {
        variant: {
            default: "bg-(--secondary-w20) border-transparent",
            secondary: "border-transparent [a&]:hover:bg-(--secondary-w10)",
            destructive: "border-transparent",
            outline: "text-(--primary-text-wMain)",
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

function Badge({
    className,
    variant,
    type,
    asChild = false,
    tooltip = "",
    tooltipSide,
    ...props
}: React.ComponentProps<"span"> &
    VariantProps<typeof badgeVariants> & {
        asChild?: boolean;
        tooltip?: string;
        tooltipSide?: "top" | "right" | "bottom" | "left";
    }) {
    const Comp = asChild ? Slot : "span";
    const BadgeComponent = <Comp data-slot="badge" className={cn(badgeVariants({ variant, type }), className)} {...props} />;

    if (tooltip) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{BadgeComponent}</TooltipTrigger>
                <TooltipContent side={tooltipSide}>{tooltip}</TooltipContent>
            </Tooltip>
        );
    }

    return BadgeComponent;
}

export { Badge };
