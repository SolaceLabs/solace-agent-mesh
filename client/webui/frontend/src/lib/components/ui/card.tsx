import * as React from "react";

import { cn } from "@/lib/utils";
import { clickableNodeProps } from "@/lib/components/utils/nodeInteraction";

interface CardProps extends React.ComponentProps<"div"> {
    noPadding?: boolean;
    onCardSelect?: () => void;
    isCardSelected?: boolean;
}

function Card({ className, noPadding, onCardSelect, isCardSelected, ...props }: CardProps) {
    const selectableProps = onCardSelect ? clickableNodeProps(onCardSelect) : {};

    return (
        <div
            data-slot="card"
            className={cn(
                "card-surface flex flex-col gap-5 rounded-lg bg-(--background-w10) text-(--primary-text-wMain)",
                !noPadding && "py-6",
                onCardSelect && "card-surface-hover cursor-pointer transition-all outline-none hover:bg-(--primary-w10) focus-visible:border-(--brand-wMain)",
                isCardSelected && "border-(--brand-wMain)",
                className
            )}
            {...props}
            {...selectableProps}
            {...(onCardSelect && { "aria-selected": isCardSelected ?? false })}
        />
    );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-header" className={cn("@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start px-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-title" className={cn("leading-none font-semibold", className)} {...props} />;
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-description" className={cn("text-sm text-(--primary-text-wMain)", className)} {...props} />;
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-action" className={cn("col-start-2 row-span-2 row-start-1 self-start justify-self-end", className)} {...props} />;
}

interface CardContentProps extends React.ComponentProps<"div"> {
    noPadding?: boolean;
}

function CardContent({ className, noPadding, ...props }: CardContentProps) {
    return <div data-slot="card-content" className={cn(!noPadding && "px-6", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-footer" className={cn("flex items-center px-6 [.border-t]:pt-6", className)} {...props} />;
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent };
