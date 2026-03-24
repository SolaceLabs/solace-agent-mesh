import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

const commonTextStyles = "text-(--primary-wMain) enabled:hover:text-(--primary-w90) enabled:active:text-(--primary-w100) enabled:hover:bg-(--primary-w10) enabled:active:bg-(--primary-w20)";

const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm font-semibold transition-all disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 cursor-pointer disabled:cursor-not-allowed",
    {
        variants: {
            variant: {
                default: "text-(--primary-text-w10) bg-(--primary-wMain) enabled:hover:bg-(--primary-w90) enabled:active:bg-(--primary-w100)",
                destructive: "text-(--error-wMain) bg-(--error-w10) enabled:hover:bg-(--error-w20)", //deprecated
                outline: commonTextStyles + " border border-(--primary-wMain)",
                secondary: commonTextStyles,
                ghost: commonTextStyles,
                link: "text-(--primary-wMain) enabled:active:text-(--primary-w100) underline-offset-4 enabled:hover:underline",
            },
            size: {
                default: "h-9 px-5 py-2 has-[>svg]:px-3",
                sm: "h-8 rounded-sm gap-1.5 px-3 has-[>svg]:px-2.5",
                lg: "h-10 rounded-sm px-6 has-[>svg]:px-4",
                icon: "size-9",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
);

export type ButtonProps = React.ComponentProps<"button"> &
    VariantProps<typeof buttonVariants> & {
        asChild?: boolean;
        tooltip?: string;
        tooltipSide?: "top" | "right" | "bottom" | "left";
        testid?: string;
    };

function Button({ className, variant, size, asChild = false, tooltip = "", tooltipSide, testid = "", ...props }: ButtonProps) {
    const Comp = asChild ? Slot : "button";
    const buttonProps = tooltip ? { ...props, "aria-label": tooltip } : props;
    const ButtonComponent = <Comp data-slot="button" data-testid={testid || tooltip || props.title} className={cn(buttonVariants({ variant, size, className }))} {...buttonProps} />;

    if (tooltip) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{ButtonComponent}</TooltipTrigger>
                <TooltipContent side={tooltipSide}>{tooltip}</TooltipContent>
            </Tooltip>
        );
    }

    return ButtonComponent;
}

// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants };
