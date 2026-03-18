import { Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/lib/components/ui";

export interface CompactionNotificationData {
    type: "compaction_notification";
    summary: string;
    is_background: boolean;
}

interface CompactionNotificationProps {
    data: CompactionNotificationData;
}

export function CompactionNotification({ data }: CompactionNotificationProps) {
    const title = data.is_background ? "Conversation history automatically summarized" : "Your conversation was summarized";

    const description = data.is_background ? "Older messages were summarized to stay within context limits." : "Your older messages were summarized to keep things running smoothly. All important context is preserved.";

    return (
        <div className={cn("my-2 rounded-lg border border-(--secondary-w20) bg-(--secondary-w5) px-4 py-1", "text-sm text-(--secondary-text-wMain)")}>
            <Accordion type="single" collapsible>
                <AccordionItem value="summary" className="border-b-0">
                    <AccordionTrigger className="py-3 hover:no-underline">
                        <div className="flex items-center gap-2">
                            <Info className="size-4 shrink-0 text-(--brand-wMain)" />
                            <span className="font-medium text-(--primary-text-wMain)">{title}</span>
                        </div>
                    </AccordionTrigger>
                    <AccordionContent>
                        <div className="space-y-2 pl-6">
                            <p className="text-(--secondary-text-wMain)">{description}</p>
                            <div className="rounded-md bg-(--secondary-w10) p-3 text-(--secondary-text-wMain) italic">{data.summary}</div>
                        </div>
                    </AccordionContent>
                </AccordionItem>
            </Accordion>
        </div>
    );
}
