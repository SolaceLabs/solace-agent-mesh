import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./accordion";

interface AccordionCardProps {
    value: string;
    icon?: React.ReactNode;
    trigger: React.ReactNode;
    children: React.ReactNode;
    /** When true (default), wraps in its own Accordion. Set false when used inside a parent Accordion. */
    standalone?: boolean;
    /** Visual variant. "default" has border and background; "borderless" removes them. */
    variant?: "default" | "borderless";
    className?: string;
}

export function AccordionCard({ value, icon, trigger, children, standalone = true, variant = "default", className }: AccordionCardProps) {
    const isBorderless = variant === "borderless";

    const card = (
        <div className={cn(!isBorderless && "overflow-hidden rounded-[4px] border bg-(--background-w10)", className)}>
            <AccordionItem value={value} className="border-none">
                <AccordionTrigger className={cn("cursor-pointer items-center justify-start gap-2 hover:no-underline [&>svg:last-child]:hidden [&[data-state=open]>svg:first-child]:rotate-90", isBorderless ? "py-0" : "p-4")}>
                    <ChevronRight className={cn("h-4 w-4 shrink-0 self-center transition-transform duration-200", isBorderless ? "text-(--secondary-text-wMain)" : "text-(--primary-wMain)")} />
                    {icon}
                    {trigger}
                </AccordionTrigger>
                <AccordionContent className={cn(isBorderless ? "pt-4 pb-0" : "border-t px-4 pb-3")}>{children}</AccordionContent>
            </AccordionItem>
        </div>
    );

    if (standalone) {
        return (
            <Accordion type="single" collapsible>
                {card}
            </Accordion>
        );
    }

    return card;
}
