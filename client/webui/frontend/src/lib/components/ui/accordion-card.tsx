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
    className?: string;
}

export function AccordionCard({ value, icon, trigger, children, standalone = true, className }: AccordionCardProps) {
    const card = (
        <div className={cn("overflow-hidden rounded-[4px] border bg-(--background-w10)", className)}>
            <AccordionItem value={value} className="border-none">
                <AccordionTrigger className="cursor-pointer items-center gap-2 p-4 hover:no-underline [&>svg:last-child]:hidden [&[data-state=open]>svg:first-child]:rotate-90">
                    <ChevronRight className="h-4 w-4 shrink-0 self-center text-(--primary-wMain) transition-transform duration-200" />
                    {icon}
                    {trigger}
                </AccordionTrigger>
                <AccordionContent className="border-t px-4 pb-3">{children}</AccordionContent>
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
