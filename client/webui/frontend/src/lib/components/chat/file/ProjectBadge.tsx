import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";
import { cn } from "@/lib/utils";

export const ProjectBadge = ({ text = "Unknown Project", className }: { text?: string; className?: string }) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="default" className={cn("max-w-[120px] min-w-[24px] shrink", className)}>
                    <span className="block truncate font-semibold">{text}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-[480px]">{text}</TooltipContent>
        </Tooltip>
    );
};
