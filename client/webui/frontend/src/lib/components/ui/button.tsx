import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

const commonTextStyles = "text-[var(--color-primary-wMain)] enabled:hover:text-[var(--color-primary-w60)] dark:text-[var(--color-primary-w10)] dark:enabled:hover:text-[var(--color-white)]";
const commonButtonStyles = commonTextStyles + " enabled:hover:bg-[var(--color-primary-w10)] dark:enabled:hover:bg-[var(--color-primary-w60)]";

const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm font-semibold transition-all disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 cursor-pointer disabled:cursor-not-allowed",
    {
        variants: {
            variant: {
                default: "text-[var(--color-primary-w10)] bg-[var(--color-primary-wMain)] enabled:hover:text-[var(--color-white)] enabled:hover:bg-[var(--color-primary-w100)] dark:enabled:hover:bg-[var(--color-primary-w60)]",
                destructive: "text-[var(--color-white)] bg-[var(--color-error-wMain)] enabled:hover:bg-[var(--color-error-w70)]",
                outline: commonButtonStyles + " border border-1 border-[var(--color-primary-wMain)]",
                secondary: commonButtonStyles,
                ghost: commonButtonStyles,
                link: commonTextStyles + " underline-offset-4 enabled:hover:underline",
            },
            size: {
                default: "h-9 px-5 py-2 has-[>svg]:px-3",
                sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
                lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
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
