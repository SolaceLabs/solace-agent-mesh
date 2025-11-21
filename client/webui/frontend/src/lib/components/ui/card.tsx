import * as React from "react";

import { cn } from "@/lib/utils";

interface CardProps extends React.ComponentProps<"div"> {
    noPadding?: boolean;
}

function Card({ className, noPadding, ...props }: CardProps) {
    return (
        <div
            data-slot="card"
            className={cn("bg-card text-card-foreground flex flex-col gap-6 rounded-lg border shadow-[0_4px_6px_-1px_rgba(0,0,0,0.15)] dark:shadow-[0_4px_6px_-1px_rgba(255,255,255,0.1)]", !noPadding && "py-6", className)}
            {...props}
        />
    );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-header" className={cn("@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-title" className={cn("leading-none font-semibold", className)} {...props} />;
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="card-description" className={cn("text-muted-foreground text-sm", className)} {...props} />;
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
