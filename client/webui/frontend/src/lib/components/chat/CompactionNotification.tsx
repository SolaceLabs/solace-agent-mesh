import { AccordionCard } from "@/lib/components/ui/accordion-card";

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
        <AccordionCard
            value="summary"
            trigger={
                <div className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                    <span className="text-sm font-medium text-(--primary-text-wMain)">{title}</span>
                    <span className="text-sm text-(--secondary-text-wMain)">{description}</span>
                </div>
            }
            className="my-2"
        >
            <div className="pt-3">
                <div className="rounded-md bg-(--secondary-w10) p-3 text-sm text-(--secondary-text-wMain) italic">{data.summary}</div>
            </div>
        </AccordionCard>
    );
}
