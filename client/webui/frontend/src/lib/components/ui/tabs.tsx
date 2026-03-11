import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
    return <TabsPrimitive.Root data-slot="tabs" className={cn("flex flex-col gap-2", className)} {...props} />;
}

function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
    return <TabsPrimitive.List data-slot="tabs-list" className={cn("inline-flex h-9 w-fit items-center justify-center rounded-lg bg-(--secondary-w10) p-[3px] text-(--secondary-text-wMain)", className)} {...props} />;
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
    return (
        <TabsPrimitive.Trigger
            data-slot="tabs-trigger"
            data-testid={props.value}
            aria-label={props.value}
            title={props.title}
            className={cn(
                "inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1 text-sm font-medium whitespace-nowrap text-(--primary-text-wMain) transition-[color,box-shadow,background-color] hover:bg-(--primary-w10) disabled:pointer-events-none disabled:text-(--secondary-text-wMain) data-[state=active]:bg-(--secondary-w10) data-[state=active]:font-semibold data-[state=active]:text-(--primary-wMain) data-[state=active]:shadow-sm [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
                className
            )}
            {...props}
        />
    );
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
    return <TabsPrimitive.Content data-slot="tabs-content" className={cn("flex-1 outline-none", className)} {...props} />;
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
