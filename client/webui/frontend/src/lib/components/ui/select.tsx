import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";

import { cn } from "@/lib/utils";

function Select({ disabled, readonly, ...props }: React.ComponentProps<typeof SelectPrimitive.Root> & { readonly?: boolean }) {
    return <SelectPrimitive.Root disabled={disabled || readonly} aria-readonly={readonly} data-slot="select" {...props} />;
}

function SelectGroup({ ...props }: React.ComponentProps<typeof SelectPrimitive.Group>) {
    return <SelectPrimitive.Group data-slot="select-group" {...props} />;
}

function SelectValue({ ...props }: React.ComponentProps<typeof SelectPrimitive.Value>) {
    return <SelectPrimitive.Value data-slot="select-value" {...props} />;
}

function SelectTrigger({
    className,
    size = "default",
    invalid,
    readonly,
    children,
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
    size?: "sm" | "default";
    invalid?: boolean;
    readonly?: boolean;
}) {
    return (
        <SelectPrimitive.Trigger
            data-slot="select-trigger"
            data-size={size}
            aria-invalid={invalid}
            aria-readonly={readonly}
            className={cn(
                // Layout & Sizing
                "flex w-fit items-center justify-between gap-2",

                // Border & Background
                "border-input rounded-xs border bg-transparent",

                // Spacing
                "px-3 py-2",

                // Typography
                "text-sm",

                // Visual Effects
                "shadow-xs transition-colors outline-none",

                // Placeholder
                "data-[placeholder]:text-placeholder",

                // Focus State
                "focus-visible:border-[var(--color-brand-wMain)]",

                // Disabled/Readonly State
                readonly ? "cursor-default opacity-80" : "disabled:cursor-not-allowed disabled:opacity-50",

                // Invalid/Error State
                "aria-invalid:border-[var(--color-error-w100)]",

                // Select Value Styling
                "*:data-[slot=select-value]:text-left",
                "*:data-[slot=select-value]:min-w-0",
                "*:data-[slot=select-value]:flex-1",
                "*:data-[slot=select-value]:overflow-hidden",
                "*:data-[slot=select-value]:text-ellipsis",
                "*:data-[slot=select-value]:whitespace-nowrap",
                "*:data-[slot=select-value]:block",

                // Icon Styling
                "[&_svg]:pointer-events-none [&_svg]:shrink-0",
                "[&_svg:not([class*='size-'])]:size-4",
                className
            )}
            {...props}
        >
            {children}
            <SelectPrimitive.Icon asChild>
                <ChevronDownIcon className="size-4 opacity-50" />
            </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
    );
}

function SelectContent({ className, children, position = "popper", ...props }: React.ComponentProps<typeof SelectPrimitive.Content>) {
    return (
        <SelectPrimitive.Portal>
            <SelectPrimitive.Content
                data-slot="select-content"
                className={cn(
                    // Layout & Sizing
                    "relative z-50 min-w-[8rem]",
                    "max-h-(--radix-select-content-available-height)",
                    "origin-(--radix-select-content-transform-origin)",

                    // Border & Background
                    "bg-background rounded-sm border",

                    // Overflow
                    "overflow-x-hidden overflow-y-auto",

                    // Animations - Open State
                    "data-[state=open]:animate-in",
                    "data-[state=open]:fade-in-0",
                    "data-[state=open]:zoom-in-95",

                    // Animations - Close State
                    "data-[state=closed]:animate-out",
                    "data-[state=closed]:fade-out-0",
                    "data-[state=closed]:zoom-out-95",

                    // Slide Animations by Position
                    "data-[side=bottom]:slide-in-from-top-2",
                    "data-[side=left]:slide-in-from-right-2",
                    "data-[side=right]:slide-in-from-left-2",
                    "data-[side=top]:slide-in-from-bottom-2",

                    // Popper Position Offsets
                    position === "popper" && ["data-[side=bottom]:translate-y-1", "data-[side=left]:-translate-x-1", "data-[side=right]:translate-x-1", "data-[side=top]:-translate-y-1"],

                    className
                )}
                position={position}
                {...props}
            >
                <SelectScrollUpButton />
                <SelectPrimitive.Viewport className={cn("p-1", position === "popper" && ["h-[var(--radix-select-trigger-height)]", "w-full", "min-w-[var(--radix-select-trigger-width)]", "scroll-my-1"])}>{children}</SelectPrimitive.Viewport>
                <SelectScrollDownButton />
            </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
    );
}

function SelectLabel({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Label>) {
    return <SelectPrimitive.Label data-slot="select-label" className={cn("px-2 py-1.5 text-xs", className)} {...props} />;
}

function SelectItem({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Item>) {
    return (
        <SelectPrimitive.Item
            data-slot="select-item"
            className={cn(
                // Layout & Sizing
                "relative flex w-full items-center gap-2",

                // Spacing
                "py-1.5 pr-8 pl-2",

                // Typography
                "text-sm",

                // Behavior
                "cursor-default select-none",

                // Hover State
                "hover:bg-[var(--color-primary-w10)] hover:text-[var(--color-primary-text-w60)]",
                "dark:hover:bg-[var(--color-primary-w60)] dark:hover:text-[var(--color-primary-text-w10)]",

                // Disabled State
                "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",

                // Icon Styling
                "[&_svg:not([class*='text-'])]:text-muted-foreground",
                "[&_svg]:pointer-events-none [&_svg]:shrink-0",
                "[&_svg:not([class*='size-'])]:size-4",

                // Span Styling
                "*:[span]:last:flex *:[span]:last:items-center *:[span]:last:gap-2",

                className
            )}
            {...props}
        >
            <span className="absolute right-2 flex size-3.5 items-center justify-center">
                <SelectPrimitive.ItemIndicator>
                    <CheckIcon className="size-4" />
                </SelectPrimitive.ItemIndicator>
            </span>
            <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
        </SelectPrimitive.Item>
    );
}

function SelectSeparator({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.Separator>) {
    return <SelectPrimitive.Separator data-slot="select-separator" className={cn("bg-border pointer-events-none -mx-1 my-1 h-px", className)} {...props} />;
}

function SelectScrollUpButton({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.ScrollUpButton>) {
    return (
        <SelectPrimitive.ScrollUpButton data-slot="select-scroll-up-button" className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}>
            <ChevronUpIcon className="size-4" />
        </SelectPrimitive.ScrollUpButton>
    );
}

function SelectScrollDownButton({ className, ...props }: React.ComponentProps<typeof SelectPrimitive.ScrollDownButton>) {
    return (
        <SelectPrimitive.ScrollDownButton data-slot="select-scroll-down-button" className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}>
            <ChevronDownIcon className="size-4" />
        </SelectPrimitive.ScrollDownButton>
    );
}

export { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectScrollDownButton, SelectScrollUpButton, SelectSeparator, SelectTrigger, SelectValue };
